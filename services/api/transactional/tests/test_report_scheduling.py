"""Scheduling and Excel exports: authorization, allowlists, idempotent runs."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from transactional.models import (
    ManagementReportRun, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, ScheduledManagementReport,
)
from transactional.report_scheduling import execute_due_reports, make_excel_report


@pytest.fixture
def report_accounts(db):
    location = POSLocation.objects.create(code="RPT", name="Report store")
    other = POSLocation.objects.create(code="OTHER", name="Other store")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="Till")
    clients = []
    operators = []
    for name, role in [
        ("rpt-owner", POSOperator.Role.SUPERVISOR),
        ("rpt-cashier", POSOperator.Role.OPERATOR),
    ]:
        user = get_user_model().objects.create_user(name, is_staff=True)
        op = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=op, location=location)
        POSOperatorTerminal.objects.create(operator=op, terminal=terminal)
        c = Client()
        c.force_login(user)
        clients.append(c)
        operators.append(op)
    return clients, operators, location, other


def scope(**kwargs):
    return {"location_code": "RPT", "terminal_code": "T1", **kwargs}


def post(client, url, payload):
    import json
    return client.post(url, json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
@override_settings(TOKAD_REPORT_ALLOWED_EMAILS="reports@example.com")
def test_allowlisted_schedule_and_location_boundary(report_accounts):
    (owner, cashier), _, location, other = report_accounts
    url = "/api/transactional/pos/manage/report-schedules/"
    assert post(cashier, url, scope(recipient_email="reports@example.com", frequency="DAILY")).status_code == 403
    assert post(owner, url, scope(recipient_email="elsewhere@example.com", frequency="DAILY")).status_code == 403
    assert post(owner, url, scope(location_code="OTHER", recipient_email="reports@example.com", frequency="DAILY")).status_code == 403
    created = post(owner, url, scope(recipient_email="reports@example.com", frequency="DAILY"))
    assert created.status_code == 201, created.content
    id_ = created.json()["schedule"]["id"]
    assert owner.get(url, scope()).json()["schedules"][0]["id"] == id_
    stop = post(owner, f"{url}{id_}/disable/", scope())
    assert stop.status_code == 200
    assert not ScheduledManagementReport.objects.get(pk=id_).is_active


@pytest.mark.django_db
def test_workbook_is_valid_zip_and_never_injects_formula(report_accounts):
    (owner, cashier), operators, location, other = report_accounts
    today = timezone.localdate()
    data = make_excel_report(location, today, today)
    with ZipFile(BytesIO(data)) as archive:
        assert archive.testzip() is None
        xml = archive.read("xl/worksheets/sheet1.xml").decode()
        assert "Store summary" not in xml or "Completed sales" in xml
        assert "<f>" not in xml
        assert "Gross sales" in xml
    url = "/api/transactional/pos/manage/report-xlsx/"
    query = scope(start=today.isoformat(), end=today.isoformat())
    response = owner.get(url, query)
    assert response.status_code == 200
    assert response["Content-Type"].endswith("spreadsheetml.sheet")
    assert cashier.get(url, query).status_code == 403
    assert owner.get(url, scope(**{**query, "location_code": "OTHER"})).status_code == 403


@pytest.mark.django_db
@override_settings(
    TOKAD_REPORT_DELIVERY_ENABLED=True,
    TOKAD_REPORT_ALLOWED_EMAILS="reports@example.com",
    DEFAULT_FROM_EMAIL="sender@example.com",
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
)
def test_worker_records_once_and_rechecks_allowlist(report_accounts):
    (_, _), (operator, _), location, other = report_accounts
    sched = ScheduledManagementReport.objects.create(
        location=location, created_by=operator,
        recipient_email="reports@example.com", frequency="DAILY",
    )
    today = timezone.localdate()
    with patch("transactional.report_scheduling.EmailMessage.send", return_value=1) as send:
        runs = execute_due_reports(on=today)
        assert len(runs) == 1
        assert runs[0].status == "SUCCEEDED"
        assert len(execute_due_reports(on=today)) == 0
        assert send.call_count == 1
    assert ManagementReportRun.objects.get(schedule=sched).period_end == today - timedelta(days=1)


@pytest.mark.django_db
@override_settings(
    TOKAD_REPORT_DELIVERY_ENABLED=True,
    TOKAD_REPORT_ALLOWED_EMAILS="someoneelse@example.com",
    DEFAULT_FROM_EMAIL="sender@example.com",
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
)
def test_revoked_recipient_is_never_sent(report_accounts):
    (_, _), (operator, _), location, other = report_accounts
    ScheduledManagementReport.objects.create(
        location=location, created_by=operator,
        recipient_email="reports@example.com", frequency="DAILY",
    )
    with patch("transactional.report_scheduling.EmailMessage.send") as send:
        assert execute_due_reports(on=timezone.localdate()) == []
        send.assert_not_called()


@pytest.mark.django_db
@override_settings(TOKAD_REPORT_DELIVERY_ENABLED=False)
def test_worker_is_off_by_default(report_accounts):
    with pytest.raises(RuntimeError, match="TOKAD_REPORT_DELIVERY_ENABLED"):
        execute_due_reports()
