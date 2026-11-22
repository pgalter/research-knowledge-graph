from knowledge_graph.openalex_client import OpenAlexClient, normalize_openalex_results


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "A Graph Paper",
                    "publication_year": 2024,
                    "cited_by_count": 4,
                    "authorships": [
                        {
                            "author": {
                                "id": "https://openalex.org/A1",
                                "display_name": "Test Author",
                                "orcid": None,
                            },
                            "institutions": [
                                {
                                    "id": "https://openalex.org/I1",
                                    "display_name": "Test University",
                                    "country_code": "FR",
                                }
                            ],
                        }
                    ],
                    "topics": [
                        {
                            "id": "https://openalex.org/T1",
                            "display_name": "Knowledge Graphs",
                        }
                    ],
                    "referenced_works": ["https://openalex.org/W2"],
                }
            ]
        }


class FakeSession:
    def __init__(self):
        self.call = None

    def get(self, url, params, timeout):
        self.call = {"url": url, "params": params, "timeout": timeout}
        return FakeResponse()


def test_search_builds_normalized_batch_and_uses_topics():
    session = FakeSession()
    client = OpenAlexClient(session=session, api_key="test-key", mailto="dev@example.com")

    dataset = client.search_works("knowledge graphs", per_page=5)

    assert dataset["works"][0]["id"] == "W1"
    assert dataset["authors"][0]["id"] == "A1"
    assert dataset["topics"][0]["id"] == "T1"
    # W2 was not in the downloaded batch, so the dangling citation is filtered out.
    assert dataset["works"][0]["references"] == []
    assert session.call["params"]["api_key"] == "test-key"
    assert "topics" in session.call["params"]["select"]


def test_normalizer_keeps_only_in_batch_citation_edges():
    records = [
        {
            "id": "https://openalex.org/W10",
            "title": "Ten",
            "publication_year": 2020,
            "cited_by_count": 0,
            "authorships": [],
            "topics": [],
            "referenced_works": ["https://openalex.org/W11", "https://openalex.org/W99"],
        },
        {
            "id": "https://openalex.org/W11",
            "title": "Eleven",
            "publication_year": 2021,
            "cited_by_count": 0,
            "authorships": [],
            "topics": [],
            "referenced_works": [],
        },
    ]

    dataset = normalize_openalex_results(records)

    assert dataset["works"][0]["references"] == ["W11"]
