"""Error-shape contract: malformed ids -> 404 ApiError, validation errors -> 422 ApiError."""
import pytest

ZERO = "00000000-0000-0000-0000-000000000000"
P = "/api/essaycards"


@pytest.mark.parametrize("path", [
    "/essays/not-a-uuid",
    "/essays/not-a-uuid/questions",
    "/essays/not-a-uuid/export",
    f"/essays/{ZERO}/sections/not-a-uuid/export",
    "/nuggets/not-a-uuid",
    "/flashcards/not-a-uuid/export",
    "/sections/not-a-uuid/examinations",
    "/essays/not-a-uuid/examinations",
])
def test_malformed_id_returns_404_api_error(client, path):
    r = client.get(P + path)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_validation_error_uses_api_error_shape_body(client):
    r = client.patch(f"{P}/sections/{ZERO}/sentence-feedback", json={})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert isinstance(err["detail"], list) and err["request_id"]


def test_validation_error_uses_api_error_shape_query(client):
    r = client.get(f"{P}/essays/{ZERO}/sections/{ZERO}/export?include_examinations=maybe")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("path", [
    "/flashcards/due?essay_id=not-a-uuid",
    "/flashcards/due?section_id=not-a-uuid",
    "/flashcards/stats?essay_id=not-a-uuid",
    "/nuggets/authoring-package?essay_id=not-a-uuid&section_id=not-a-uuid",
])
def test_malformed_id_in_query_returns_404_api_error(client, path):
    r = client.get(P + path)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_empty_id_query_param_means_not_given(client):
    assert client.get(P + "/flashcards/due?essay_id=").status_code == 200
