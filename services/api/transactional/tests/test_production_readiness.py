"""Production safety gates and DB readiness behavior."""
from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.test import Client

from transactional.readiness_api import readiness


@pytest.mark.django_db
def test_readiness_returns_ready_with_live_database():
    response = Client().get("/api/transactional/health/ready/")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.django_db
def test_readiness_does_not_disclose_database_errors():
    with patch("transactional.readiness_api.connections") as connections:
        connections.__getitem__.side_effect = OperationalError("secret database hostname")
        response = Client().get("/api/transactional/health/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"secret database hostname" not in response.content


def test_production_defaults_require_a_strong_secret_and_allowed_hosts():
    # Deployment settings must fail before serving requests with weak defaults.
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env.update({
        "DJANGO_DEBUG": "0",
        "DJANGO_SECRET_KEY": "dev-only-change-me",
        "DJANGO_ALLOWED_HOSTS": "tokad.example.com",
    })
    result = subprocess.run(
        [sys.executable, "-c", "import django; from django.conf import settings; print(settings.DEBUG)"],
        env={**env, "DJANGO_SETTINGS_MODULE": "config.settings"},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr
