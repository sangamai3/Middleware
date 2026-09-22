"""REST auth modes from AgentStudio."""

from sangam_mw.connectors.rest_api.auth import auth_headers, auth_params, rest_auth_type


def test_bearer_and_basic_and_query_key() -> None:
    assert rest_auth_type({"api_key": "k"}) == "bearer"
    assert "Bearer k" in auth_headers({"api_key": "k"})["Authorization"]
    headers = auth_headers({"auth_type": "basic", "username": "u", "password": "p"})
    assert headers["Authorization"].startswith("Basic ")
    params = auth_params({"auth_type": "apiKeyQuery", "api_key": "secret", "api_key_param": "key"})
    assert params == {"key": "secret"}
