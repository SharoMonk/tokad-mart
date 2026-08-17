from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_worker_dockerfile_has_frozen_runtime_and_sigterm():
    dockerfile = (repo_root() / "Dockerfile.outbox-worker").read_text()

    assert "uv sync --frozen --no-dev" in dockerfile
    assert 'STOPSIGNAL SIGTERM' in dockerfile
    assert '"run_outbox_worker"' in dockerfile
    assert "--poll-interval" in dockerfile
    assert "--limit" in dockerfile
    assert "--lease-seconds" in dockerfile


def test_worker_dockerignore_excludes_environment_and_virtualenv():
    dockerignore = (repo_root() / ".dockerignore").read_text().splitlines()

    assert ".env" in dockerignore
    assert ".venv/" in dockerignore
    assert ".git/" in dockerignore


def test_systemd_unit_has_restart_and_graceful_shutdown_contract():
    unit = (
        repo_root()
        / "deploy"
        / "systemd"
        / "tokad-mart-outbox-worker.service"
    ).read_text()

    assert "Restart=on-failure" in unit
    assert "RestartSec=5" in unit
    assert "KillSignal=SIGTERM" in unit
    assert "TimeoutStopSec=30" in unit
    assert "EnvironmentFile=/etc/tokad-mart/api.env" in unit
    assert "ExecStart=/opt/tokad-mart/services/api/.venv/bin/python manage.py run_outbox_worker" in unit


def test_deployment_guide_documents_both_runtime_modes():
    guide = (repo_root() / "deploy" / "README.md").read_text()

    assert "dispatch_outbox_events" in guide
    assert "run_outbox_worker" in guide
    assert "docker run" in guide
    assert "systemctl enable --now tokad-mart-outbox-worker" in guide
