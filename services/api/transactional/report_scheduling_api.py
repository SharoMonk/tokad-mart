"""Supervisor report schedules with deployment-managed recipient allowlist."""
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import ManagementReportRun, ScheduledManagementReport
from .permissions import IsPOSOperator
from .financial_dashboard_api import _date_range
from .supervisor_procurement_api import fail, parse_body, scope_for
from .report_scheduling import make_excel_report


def _allowed_emails():
    return {
        address.strip().lower()
        for address in getattr(settings, "TOKAD_REPORT_ALLOWED_EMAILS", "").split(",")
        if address.strip()
    }


def _serial(schedule):
    return {
        "id": schedule.pk, "location_code": schedule.location.code,
        "recipient_email": schedule.recipient_email,
        "frequency": schedule.frequency, "is_active": schedule.is_active,
    }


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def report_schedules(request):
    data = request.query_params if request.method == "GET" else parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    if request.method == "GET":
        schedules = list(ScheduledManagementReport.objects.filter(
            location=scope.location
        ).select_related("location").order_by("-pk")[:100])
        ids = [s.pk for s in schedules]
        runs = ManagementReportRun.objects.filter(
            schedule_id__in=ids
        ).order_by("-pk")[:100]
        return JsonResponse({
            "schedules": [_serial(s) for s in schedules],
            "runs": [{
                "id": run.pk, "schedule_id": run.schedule_id,
                "period_start": run.period_start.isoformat(),
                "period_end": run.period_end.isoformat(),
                "status": run.status, "detail": run.detail,
            } for run in runs],
        })
    email = data.get("recipient_email")
    frequency = data.get("frequency")
    if frequency not in ScheduledManagementReport.Frequency.values:
        return fail("invalid_frequency")
    if not isinstance(email, str) or len(email) > 254:
        return fail("invalid_recipient")
    try:
        validate_email(email)
    except ValidationError:
        return fail("invalid_recipient")
    if email.lower() not in _allowed_emails():
        return fail("recipient_not_approved", 403)
    schedule = ScheduledManagementReport.objects.create(
        location=scope.location, created_by=scope.operator,
        recipient_email=email.lower(), frequency=frequency,
    )
    return JsonResponse({"schedule": _serial(schedule)}, status=201)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def deactivate_schedule(request, schedule_id):
    data = parse_body(request)
    if data is None:
        return fail("invalid_request")
    scope = scope_for(request, data)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    schedule = ScheduledManagementReport.objects.filter(
        pk=schedule_id, location=scope.location, created_by=scope.operator
    ).first()
    if schedule is None:
        return fail("schedule_not_found", 404)
    if not schedule.is_active:
        return fail("already_inactive", 409)
    schedule.is_active = False
    schedule.save(update_fields=["is_active"])
    return JsonResponse({"schedule": _serial(schedule)})


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsPOSOperator])
def download_excel(request):
    scope = scope_for(request, request.query_params)
    if scope is None:
        return fail("supervisor_scope_required", 403)
    window = _date_range(request.query_params)
    if window is None:
        return fail("invalid_date_range")
    start, end = window
    content = make_excel_report(scope.location, start, end)
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="tokad-management-{start}-{end}.xlsx"'
    response["Cache-Control"] = "no-store"
    return response
