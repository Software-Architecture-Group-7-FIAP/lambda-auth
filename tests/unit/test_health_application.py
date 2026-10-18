from lambda_auth.application.health import HealthApplication
from lambda_auth.application.http import HttpRequest


def test_health_check_returns_ok() -> None:
    response = HealthApplication().execute(HttpRequest(method="GET", path="/health"))

    assert response.status_code == 200
    assert response.body == {"status": "ok"}


def test_health_check_rejects_other_methods() -> None:
    response = HealthApplication().execute(HttpRequest(method="POST", path="/health"))

    assert response.status_code == 405
    assert response.body == {"error": "method_not_allowed"}
    assert response.headers["allow"] == "GET"


def test_unknown_path_returns_not_found() -> None:
    response = HealthApplication().execute(HttpRequest(method="GET", path="/unknown"))

    assert response.status_code == 404
    assert response.body == {"error": "not_found"}
