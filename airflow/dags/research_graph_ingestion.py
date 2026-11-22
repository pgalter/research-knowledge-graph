"""Optional daily Airflow DAG for loading the checked-in sample batch.

The Airflow environment must have this repository mounted and its src/ directory
on PYTHONPATH, plus the project dependencies installed.
"""

from datetime import datetime
from pathlib import Path
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def ingest_sample_batch() -> None:
    from knowledge_graph.neo4j_store import Neo4jStore
    from knowledge_graph.pipeline import ingest_payload, load_json

    store = Neo4jStore.from_env()
    try:
        ingest_payload(load_json(PROJECT_ROOT / "data" / "sample_graph.json"), store)
    finally:
        store.close()


with DAG(
    dag_id="research_knowledge_graph_batch_ingestion",
    description="Validate and load the sample research dataset into Neo4j",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["knowledge-graph", "data-quality", "neo4j"],
) as dag:
    PythonOperator(
        task_id="validate_and_load_graph_batch",
        python_callable=ingest_sample_batch,
    )
