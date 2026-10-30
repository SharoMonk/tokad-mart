"""Report calculation, independent XLSX export, and safe schedule execution."""
from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .enterprise_reporting_api import _totals
from .models import ManagementReportRun, POSOperator, ScheduledManagementReport


HEADERS = (
    "Location", "Completed sales", "Gross sales (NGN kobo)",
    "Closed shifts", "Cashier variance (NGN kobo)", "Approved expenses (NGN kobo)",
)


def _excel_cell(value, reference, style=0):
    """Use inline strings (never formulas), escaping spreadsheet controls."""
    if type(value) is int:
        return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'
    text = str(value)
    # Excel limits cell values to 32,767 characters.
    return (f'<c r="{reference}" s="{style}" t="inlineStr"><is><t>'
            f'{escape(text[:32767])}</t></is></c>')


def _column(index):
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def make_excel_report(location, start, end):
    """Generate a real .xlsx workbook using only Python's standard library."""
    record = _totals(location, start, end)
    values = [
        HEADERS,
        (record["name"], record["completed_sales"], record["gross_sales_minor"],
         record["closed_shifts"], record["cashier_variance_minor"],
         record["approved_expenses_minor"]),
        ("Period start", start.isoformat()),
        ("Period end", end.isoformat()),
        ("Note", "Operational metrics only: not profit, settled cash, or bank balance."),
    ]
    row_xml = []
    for row_number, values_row in enumerate(values, 1):
        cells = "".join(
            _excel_cell(value, f"{_column(col)}{row_number}", 1 if row_number == 1 else 0)
            for col, value in enumerate(values_row, 1)
        )
        row_xml.append(f'<row r="{row_number}">{cells}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<cols><col min="1" max="1" width="30" customWidth="1"/>'
        '<col min="2" max="6" width="25" customWidth="1"/></cols>'
        '<sheetData>' + "".join(row_xml) + '</sheetData></worksheet>'
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>')
        archive.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        archive.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Store summary" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
        archive.writestr("xl/styles.xml",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font/><font><b/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '</styleSheet>')
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return buffer.getvalue()


def period_for(schedule, on):
    """Cron runs after the reporting period; Mondays cover the prior Mon-Sun."""
    if schedule.frequency == "DAILY":
        day = on - timedelta(days=1)
        return day, day
    if schedule.frequency == "WEEKLY" and on.weekday() == 0:
        end = on - timedelta(days=1)
        return end - timedelta(days=6), end
    return None


def execute_due_reports(on=None):
    """At-most-once delivery attempt per period; failures need manual investigation.

    Concurrent workers race on a unique (schedule, period_end) constraint.
    A delivery crash after provider acceptance remains CLAIMED rather than
    risking a duplicate automatic email.
    """
    if not getattr(settings, "TOKAD_REPORT_DELIVERY_ENABLED", False):
        raise RuntimeError("TOKAD_REPORT_DELIVERY_ENABLED is not set")
    if not settings.DEFAULT_FROM_EMAIL:
        raise RuntimeError("DEFAULT_FROM_EMAIL is required")
    backend = settings.EMAIL_BACKEND
    if "console" in backend or "filebased" in backend or "locmem" in backend or "dummy" in backend:
        raise RuntimeError("Non-delivery email backend is not supported")
    on = on or timezone.localdate()
    results = []
    for schedule in ScheduledManagementReport.objects.filter(
        is_active=True, location__is_active=True, created_by__is_active=True,
        created_by__role=POSOperator.Role.SUPERVISOR,
        created_by__user__is_active=True,
        created_by__user__is_staff=True,
    ).select_related("location", "created_by"):
        if not schedule.created_by.locations.filter(pk=schedule.location_id).exists():
            continue
        window = period_for(schedule, on)
        if window is None:
            continue
        start, end = window
        with transaction.atomic():
            run, created = ManagementReportRun.objects.get_or_create(
                schedule=schedule, period_end=end,
                defaults={"period_start": start},
            )
        if not created:
            continue
        try:
            content = make_excel_report(schedule.location, start, end)
            message = EmailMessage(
                subject=f"Tokad Mart {schedule.frequency.lower()} report: {schedule.location.code} {end}",
                body="Attached is the operational store summary. Amounts are not bank-confirmed or net profit.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[schedule.recipient_email],
            )
            message.attach(
                f"tokad-{schedule.location.code}-{start}-{end}.xlsx", content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            if message.send(fail_silently=False) != 1:
                raise RuntimeError("Email backend did not accept exactly one message")
        except Exception as exc:
            run.status = ManagementReportRun.Status.FAILED
            run.detail = type(exc).__name__[:500]
        else:
            run.status = ManagementReportRun.Status.SUCCEEDED
            run.detail = "Email backend accepted message; inbox delivery is unconfirmed"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "detail", "finished_at"])
        results.append(run)
    return results
