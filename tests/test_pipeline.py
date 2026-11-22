import pytest

from knowledge_graph.pipeline import DataQualityError, ingest_payload


class FakeGraphStore:
    def __init__(self):
        self.schema_created = False
        self.loaded = None

    def ensure_schema(self):
        self.schema_created = True

    def load_dataset(self, dataset):
        self.loaded = dataset


def test_pipeline_validates_before_loading(sample_payload):
    store = FakeGraphStore()

    result = ingest_payload(sample_payload, store)

    assert result["status"] == "loaded"
    assert store.schema_created is True
    assert len(store.loaded.works) == 3


def test_pipeline_does_not_write_invalid_batch(sample_payload):
    sample_payload["works"][0]["author_ids"] = ["missing"]
    store = FakeGraphStore()

    with pytest.raises(DataQualityError):
        ingest_payload(sample_payload, store)

    assert store.schema_created is False
    assert store.loaded is None
