"""Schema and referential-integrity validation for graph ingestion batches."""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from knowledge_graph.models import GraphDataset


@dataclass
class ValidationReport:
    dataset: GraphDataset | None
    errors: list[str]

    @property
    def valid(self) -> bool:
        return self.dataset is not None and not self.errors

    @property
    def counts(self) -> dict[str, int]:
        if self.dataset is None:
            return {"authors": 0, "institutions": 0, "topics": 0, "works": 0}
        return {
            "authors": len(self.dataset.authors),
            "institutions": len(self.dataset.institutions),
            "topics": len(self.dataset.topics),
            "works": len(self.dataset.works),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "counts": self.counts, "errors": self.errors}


def _duplicate_ids(records: list[Any], entity_name: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        if record.id in seen:
            duplicates.add(record.id)
        seen.add(record.id)
    return [f"Duplicate {entity_name} id: {record_id}" for record_id in sorted(duplicates)]


def validate_dataset(payload: dict[str, Any]) -> ValidationReport:
    """Validate shape, uniqueness, and all graph-edge references before loading."""
    try:
        dataset = GraphDataset.model_validate(payload)
    except ValidationError as exc:
        messages = [
            f"{'/'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
            for issue in exc.errors()
        ]
        return ValidationReport(dataset=None, errors=messages)

    errors: list[str] = []
    errors.extend(_duplicate_ids(dataset.authors, "author"))
    errors.extend(_duplicate_ids(dataset.institutions, "institution"))
    errors.extend(_duplicate_ids(dataset.topics, "topic"))
    errors.extend(_duplicate_ids(dataset.works, "work"))

    author_ids = {record.id for record in dataset.authors}
    institution_ids = {record.id for record in dataset.institutions}
    topic_ids = {record.id for record in dataset.topics}
    work_ids = {record.id for record in dataset.works}

    for author in dataset.authors:
        for institution_id in author.institution_ids:
            if institution_id not in institution_ids:
                errors.append(
                    f"authors[{author.id}].institution_ids references unknown institution: "
                    f"{institution_id}"
                )

    for work in dataset.works:
        for author_id in work.author_ids:
            if author_id not in author_ids:
                errors.append(
                    f"works[{work.id}].author_ids references unknown author: {author_id}"
                )
        for topic_id in work.topic_ids:
            if topic_id not in topic_ids:
                errors.append(
                    f"works[{work.id}].topic_ids references unknown topic: {topic_id}"
                )
        for cited_work_id in work.references:
            if cited_work_id not in work_ids:
                errors.append(
                    f"works[{work.id}].references references unknown work: {cited_work_id}"
                )
            if cited_work_id == work.id:
                errors.append(f"works[{work.id}] cannot cite itself")

    return ValidationReport(dataset=dataset, errors=errors)
