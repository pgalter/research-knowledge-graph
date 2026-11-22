from copy import deepcopy

from knowledge_graph.validation import validate_dataset


def test_valid_sample_passes_all_checks(sample_payload):
    report = validate_dataset(sample_payload)

    assert report.valid is True
    assert report.counts == {
        "authors": 3,
        "institutions": 2,
        "topics": 3,
        "works": 3,
    }
    assert report.errors == []


def test_unknown_author_reference_is_rejected(sample_payload):
    payload = deepcopy(sample_payload)
    payload["works"][0]["author_ids"].append("A-MISSING")

    report = validate_dataset(payload)

    assert report.valid is False
    assert any("unknown author: A-MISSING" in error for error in report.errors)


def test_duplicate_node_id_is_rejected(sample_payload):
    payload = deepcopy(sample_payload)
    payload["authors"].append(deepcopy(payload["authors"][0]))

    report = validate_dataset(payload)

    assert report.valid is False
    assert "Duplicate author id: A-001" in report.errors


def test_negative_citation_count_is_rejected(sample_payload):
    payload = deepcopy(sample_payload)
    payload["works"][0]["citation_count"] = -1

    report = validate_dataset(payload)

    assert report.valid is False
    assert any("greater than or equal to 0" in error for error in report.errors)


def test_self_citation_is_rejected(sample_payload):
    payload = deepcopy(sample_payload)
    payload["works"][0]["references"].append("W-001")

    report = validate_dataset(payload)

    assert report.valid is False
    assert "works[W-001] cannot cite itself" in report.errors
