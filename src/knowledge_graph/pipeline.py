"""Batch ingestion entry points, usable from the CLI or Airflow."""

import argparse
import json
from pathlib import Path
from typing import Any

from knowledge_graph.models import GraphDataset
from knowledge_graph.openalex_client import OpenAlexClient
from knowledge_graph.validation import ValidationReport, validate_dataset


class DataQualityError(ValueError):
    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__("Data-quality checks failed: " + "; ".join(report.errors))


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_payload(payload: dict[str, Any]) -> tuple[GraphDataset, ValidationReport]:
    report = validate_dataset(payload)
    if not report.valid or report.dataset is None:
        raise DataQualityError(report)
    return report.dataset, report


def ingest_payload(payload: dict[str, Any], store: Any) -> dict[str, Any]:
    """Validate a complete batch, then persist it as one graph write transaction."""
    dataset, report = validate_payload(payload)
    store.ensure_schema()
    store.load_dataset(dataset)
    return {"status": "loaded", "counts": report.counts, "quality": report.as_dict()}


def ingest_openalex_search(
    search_term: str,
    store: Any,
    per_page: int = 10,
    client: OpenAlexClient | None = None,
) -> dict[str, Any]:
    openalex = client or OpenAlexClient()
    payload = openalex.search_works(search_term, per_page=per_page)
    return ingest_payload(payload, store)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load a research graph batch.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", default="data/sample_graph.json", help="JSON dataset path")
    source.add_argument("--search", help="Search OpenAlex for works matching this phrase")
    parser.add_argument("--limit", type=int, default=10, help="OpenAlex results (1-100)")
    parser.add_argument(
        "--validate-only", action="store_true", help="Run quality checks without Neo4j"
    )
    args = parser.parse_args()

    if args.search:
        payload = OpenAlexClient().search_works(args.search, per_page=args.limit)
    else:
        payload = load_json(args.input)

    dataset, report = validate_payload(payload)
    print(json.dumps({"status": "valid", "counts": report.counts}, indent=2))
    if args.validate_only:
        return

    from knowledge_graph.neo4j_store import Neo4jStore

    store = Neo4jStore.from_env()
    try:
        store.ensure_schema()
        store.load_dataset(dataset)
        print("Batch loaded successfully into Neo4j.")
    finally:
        store.close()


if __name__ == "__main__":
    main()
