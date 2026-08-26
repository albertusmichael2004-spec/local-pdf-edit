from backend.main import app


def test_app_routes_are_registered():
    schema = app.openapi()
    paths = set(schema["paths"].keys())

    assert "/api/edit/compress" in paths
    assert "/api/convert/jpg-to-pdf" in paths
    assert "/api/convert/pdf-to-word" in paths
    assert "/api/security/compare-pdf-summary" in paths