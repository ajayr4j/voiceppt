from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_slides_returns_six_slides():
    response = client.get("/api/slides")
    assert response.status_code == 200
    slides = response.json()
    assert len(slides) == 6


def test_each_slide_has_required_shape():
    slides = client.get("/api/slides").json()
    for slide in slides:
        assert set(slide.keys()) == {"id", "title", "bullets"}
        assert isinstance(slide["id"], int)
        assert isinstance(slide["title"], str) and slide["title"]
        assert isinstance(slide["bullets"], list) and len(slide["bullets"]) > 0


def test_slide_ids_are_sequential_from_one():
    slides = client.get("/api/slides").json()
    assert [s["id"] for s in slides] == [1, 2, 3, 4, 5, 6]
