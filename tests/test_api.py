from fastapi.testclient import TestClient

from knowledge_graph.api import create_app


class FakeGraphStore:
    def ping(self):
        return True

    def get_stats(self):
        return {"authors": 3, "institutions": 2, "topics": 3, "works": 3}

    def get_author_network(self, author_id):
        if author_id != "A-001":
            return None
        return {
            "author": {"id": "A-001", "name": "Alex Morgan", "orcid": None},
            "works": [
                {"id": "W-001", "title": "Graph A", "year": 2024},
                {"id": "W-003", "title": "Graph B", "year": 2025},
            ],
            "coauthors": [
                {"id": "A-002", "name": "Sam Lee"},
                {"id": "A-003", "name": "Jamie Chen"},
            ],
        }

    def get_work(self, work_id):
        if work_id != "W-001":
            return None
        return {
            "work": {"id": "W-001", "title": "Graph A", "year": 2024},
            "authors": [{"id": "A-001", "name": "Alex Morgan"}],
            "topics": [{"id": "T-001", "name": "Knowledge Graphs"}],
            "institutions": [],
        }


def test_health_endpoint():
    client = TestClient(create_app(FakeGraphStore()))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_author_network_respects_limit():
    client = TestClient(create_app(FakeGraphStore()))
    response = client.get("/authors/A-001/network?limit=1")

    assert response.status_code == 200
    assert len(response.json()["works"]) == 1
    assert len(response.json()["coauthors"]) == 1


def test_unknown_author_returns_404():
    client = TestClient(create_app(FakeGraphStore()))
    response = client.get("/authors/not-found/network")

    assert response.status_code == 404


def test_work_detail_returns_authors_and_topics():
    client = TestClient(create_app(FakeGraphStore()))
    response = client.get("/works/W-001")

    assert response.status_code == 200
    assert response.json()["work"]["id"] == "W-001"
    assert response.json()["topics"][0]["name"] == "Knowledge Graphs"
