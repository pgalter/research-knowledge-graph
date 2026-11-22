"""Small OpenAlex client and normalizer for scholarly work search results."""

from typing import Any

import requests

from knowledge_graph.config import settings

BASE_URL = "https://api.openalex.org"


def _short_id(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/").split("/")[-1]


def normalize_openalex_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert OpenAlex works into the project's normalized graph dataset.

    Citation edges are retained only when both works are in this fetched batch.
    This keeps every edge referentially valid without issuing one API request per
    cited work.
    """
    authors: dict[str, dict[str, Any]] = {}
    institutions: dict[str, dict[str, Any]] = {}
    topics: dict[str, dict[str, Any]] = {}
    works: list[dict[str, Any]] = []
    fetched_work_ids = {
        short_id
        for item in results
        if (short_id := _short_id(item.get("id"))) is not None
    }

    for item in results:
        work_id = _short_id(item.get("id"))
        if not work_id:
            continue

        work_author_ids: list[str] = []
        for authorship in item.get("authorships", []) or []:
            author_data = authorship.get("author") or {}
            author_id = _short_id(author_data.get("id"))
            if not author_id:
                continue
            author = authors.setdefault(
                author_id,
                {
                    "id": author_id,
                    "name": author_data.get("display_name") or "Unknown author",
                    "orcid": author_data.get("orcid"),
                    "institution_ids": [],
                },
            )
            work_author_ids.append(author_id)

            for institution_data in authorship.get("institutions", []) or []:
                institution_id = _short_id(institution_data.get("id"))
                if not institution_id:
                    continue
                institutions.setdefault(
                    institution_id,
                    {
                        "id": institution_id,
                        "name": institution_data.get("display_name") or "Unknown institution",
                        "country_code": institution_data.get("country_code"),
                    },
                )
                if institution_id not in author["institution_ids"]:
                    author["institution_ids"].append(institution_id)

        work_topic_ids: list[str] = []
        for topic_data in item.get("topics", []) or []:
            topic_id = _short_id(topic_data.get("id"))
            if not topic_id:
                continue
            topics.setdefault(
                topic_id,
                {
                    "id": topic_id,
                    "name": topic_data.get("display_name") or "Unknown topic",
                },
            )
            work_topic_ids.append(topic_id)

        references = [
            short_id
            for reference in (item.get("referenced_works", []) or [])
            if (short_id := _short_id(reference)) in fetched_work_ids and short_id != work_id
        ]
        works.append(
            {
                "id": work_id,
                "title": item.get("title") or "Untitled work",
                "year": item.get("publication_year") or 1900,
                "citation_count": item.get("cited_by_count") or 0,
                "author_ids": sorted(set(work_author_ids)),
                "topic_ids": sorted(set(work_topic_ids)),
                "references": sorted(set(references)),
            }
        )

    return {
        "authors": list(authors.values()),
        "institutions": list(institutions.values()),
        "topics": list(topics.values()),
        "works": works,
    }


class OpenAlexClient:
    def __init__(
        self,
        api_key: str | None = None,
        mailto: str | None = None,
        session: requests.Session | None = None,
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.openalex_api_key
        self.mailto = mailto if mailto is not None else settings.openalex_mailto
        self.session = session or requests.Session()
        self.timeout = timeout

    def search_works(self, search_term: str, per_page: int = 10) -> dict[str, Any]:
        if not search_term.strip():
            raise ValueError("search_term must not be empty")
        if not 1 <= per_page <= 100:
            raise ValueError("per_page must be between 1 and 100")

        params: dict[str, Any] = {
            "search": search_term,
            "per_page": per_page,
            "select": (
                "id,title,publication_year,cited_by_count,authorships,topics,referenced_works"
            ),
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto

        response = self.session.get(
            f"{BASE_URL}/works", params=params, timeout=self.timeout
        )
        response.raise_for_status()
        body = response.json()
        return normalize_openalex_results(body.get("results", []))
