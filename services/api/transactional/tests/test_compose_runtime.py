from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[2]


def test_compose_defines_api_worker_and_postgres_services():
    compose = (API_ROOT / "docker-compose.yml").read_text()

    assert "  postgres:" in compose
    assert "  api:" in compose
    assert "  outbox-worker:" in compose


def test_compose_uses_service_network_for_container_database_connections():
    compose = (API_ROOT / "docker-compose.yml").read_text()

    assert "POSTGRES_HOST: postgres" in compose
    assert 'POSTGRES_PORT: "5432"' in compose
    assert "condition: service_healthy" in compose


def test_compose_keeps_worker_on_existing_frozen_runtime_image():
    compose = (API_ROOT / "docker-compose.yml").read_text()

    assert "dockerfile: Dockerfile.outbox-worker" in compose
    assert '"run_outbox_worker"' in compose
    assert '"runserver"' in compose


def test_compose_preserves_host_database_port_and_persistent_volume():
    compose = (API_ROOT / "docker-compose.yml").read_text()

    assert '"${POSTGRES_PORT:-5432}:5432"' in compose
    assert "tokad_postgres_data:/var/lib/postgresql" in compose
