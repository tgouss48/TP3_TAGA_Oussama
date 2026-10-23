from maintenance_ml.api.main import app


def test_versioned_openapi_contract_exposes_product_routes():
    document = app.openapi()
    paths = document["paths"]

    assert document["info"]["version"] == "2.1.0"
    for path in ("/v1/health", "/v1/model-info", "/v1/predict", "/v1/metrics"):
        assert path in paths
    assert "PredictionRequest" in document["components"]["schemas"]
    assert "ErrorResponse" in document["components"]["schemas"]
