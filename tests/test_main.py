from main import app


def test_sync_endpoint_registrado_na_aplicacao_principal():
    assert "post" in app.openapi()["paths"]["/api/v1/sync"]
