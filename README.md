# Research Knowledge Graph Pipeline

An end-to-end data engineering portfolio project that turns scholarly metadata into a queryable graph. It demonstrates graph modelling with **Neo4j and Cypher**, batch ingestion, data-quality validation, REST API development and testing, and optional **Apache Airflow** orchestration.

> The checked-in dataset is synthetic and exists for local demos and automated tests. The optional OpenAlex client retrieves real scholarly metadata from the OpenAlex REST API.


## What it does

1. Ingests scholarly works from a local JSON batch or searches OpenAlex.
2. Normalizes authors, institutions, topics, works, and in-batch citation references.
3. Runs schema checks and data-quality rules before writing anything to Neo4j.
4. Creates graph nodes and relationships idempotently with Cypher `MERGE` statements.
5. Exposes graph statistics, work details, and author collaboration networks through FastAPI.
6. Tests validation rules, API behavior, the OpenAlex HTTP client, and the pipeline with `pytest`.
7. Includes a Postman collection and an optional daily Airflow DAG.

## Architecture

```text
                    ┌──────────────────────────────┐
                    │  OpenAlex REST API / JSON    │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Python ingestion + normalize│
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Data quality validation      │
                    │ - Pydantic schema            │
                    │ - duplicate IDs              │
                    │ - relationship integrity     │
                    └──────────────┬───────────────┘
                                   │ valid batch only
                                   ▼
                    ┌──────────────────────────────┐
                    │ Neo4j graph database         │
                    │ Nodes + Cypher relationships │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ FastAPI read endpoints       │
                    └──────────────────────────────┘

            Optional orchestration: Apache Airflow DAG (@daily)
            Automated checks: pytest | Manual API checks: Postman
```

## Graph model

| Node label | Key properties | Relationships |
|---|---|---|
| `Author` | `id`, `name`, `orcid` | `AUTHORED` → `Work`; `AFFILIATED_WITH` → `Institution` |
| `Work` | `id`, `title`, `year`, `citation_count` | `HAS_TOPIC` → `Topic`; `CITES` → `Work` |
| `Institution` | `id`, `name`, `country_code` | Connected from `Author` |
| `Topic` | `id`, `name` | Connected from `Work` |

All node IDs have uniqueness constraints. The loader uses `MERGE`, so re-running the same batch does not duplicate nodes or relationships. Citation relationships are retained only when both works are present in the ingested batch; this prevents dangling edges without making one API request per citation.

## Tech stack

- **Python 3.10+** — ingestion, normalization, validation, and API logic
- **Neo4j 5 + Cypher** — graph persistence, constraints, and traversals
- **OpenAlex REST API + requests** — external source integration
- **Pydantic** — record/schema validation
- **FastAPI + Uvicorn** — REST API
- **pytest + HTTPX TestClient** — automated tests
- **Postman** — manual API smoke-test collection
- **Apache Airflow (optional)** — scheduled batch orchestration
- **Docker Compose** — local Neo4j and API environment

## Quick start: Docker

Prerequisites: Docker Desktop or Docker Engine with the Compose plugin.

```bash
# 1. Clone the repository and enter the project directory.
git clone https://github.com/<your-username>/research-knowledge-graph.git
cd research-knowledge-graph

# 2. Optional: set a stronger local Neo4j password.
cp .env.example .env
# Edit NEO4J_PASSWORD in .env, then export it for Compose if needed:
# set -a && source .env && set +a

# 3. Start Neo4j and the API.
docker compose up --build -d

# 4. Ingest the checked-in sample graph from your local Python environment.
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m knowledge_graph.pipeline --input data/sample_graph.json
```

The API runs at `http://localhost:8000`. Interactive OpenAPI documentation is at `http://localhost:8000/docs`; Neo4j Browser is at `http://localhost:7474`.

> If you changed the password, set the same `NEO4J_PASSWORD` in your shell before running the ingestion command. For a real deployment, use a secret manager and do not commit `.env`.

## Quick start: local Python

You can run only the validation/tests without Docker or a running Neo4j instance:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Validate the sample file without writing to a database.
python -m knowledge_graph.pipeline --input data/sample_graph.json --validate-only

# Run automated tests.
pytest -q
```

To run the API locally, start Neo4j separately, set `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`, then run:

```bash
uvicorn knowledge_graph.api:app --reload
```

## Ingest from OpenAlex

OpenAlex offers a REST API for works, authors, institutions, and topics. A key is optional for a small demonstration; set one through environment variables if you have one.

```bash
export OPENALEX_MAILTO="you@example.com"  # recommended for polite API use
# export OPENALEX_API_KEY="your-key"        # optional
python -m knowledge_graph.pipeline --search "knowledge graphs" --limit 20
```

The client requests `topics` rather than the legacy `concepts` field. The normalizer collects authors and affiliations from work authorships, extracts topics, and keeps citation edges only where the cited work is also in the downloaded batch.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check API and Neo4j connectivity |
| `GET` | `/graph/stats` | Count authors, institutions, topics, and works |
| `GET` | `/authors/{author_id}/network?limit=10` | Return an author's works and co-authors |
| `GET` | `/works/{work_id}` | Return work metadata, authors, topics, and institutions |

Example requests:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/graph/stats
curl "http://localhost:8000/authors/A-001/network?limit=10"
curl http://localhost:8000/works/W-001
```

Import `postman/collection.json` into Postman for manual API smoke tests. Set the `baseUrl` collection variable if the API is not running on `localhost:8000`.

## Example Cypher queries

**Find an author's co-authors:**

```cypher
MATCH (a:Author {id: 'A-001'})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(co:Author)
WHERE co.id <> a.id
RETURN co.name AS coauthor, collect(DISTINCT w.title) AS shared_works
ORDER BY coauthor;
```

**Find topics associated with a work:**

```cypher
MATCH (w:Work {id: 'W-001'})-[:HAS_TOPIC]->(t:Topic)
RETURN w.title, collect(t.name) AS topics;
```

**Traverse citation links:**

```cypher
MATCH (source:Work)-[:CITES]->(target:Work)
RETURN source.title AS citing_work, target.title AS cited_work;
```

## Data quality rules

The batch is rejected before any database write if any of these checks fail:

- Required fields and data types satisfy the Pydantic models.
- Author, institution, topic, and work IDs are unique within the batch.
- Work-to-author, work-to-topic, author-to-institution, and citation references resolve.
- Citation counts are non-negative and publication years are within the configured range.
- A work cannot cite itself.

Validation entry point: `knowledge_graph.validation.validate_dataset()`.

## Tests

```bash
pytest -q
```

Tests use a synthetic sample dataset and mocked graph/API dependencies; they do not require a live Neo4j server or call the OpenAlex network. For an additional end-to-end check, start Docker Compose, ingest the sample file, and exercise the Postman collection.

## Optional Airflow orchestration

The repository includes `airflow/dags/research_graph_ingestion.py`, which runs the sample batch daily. It expects the repository to be mounted in the Airflow environment, the project's `src/` directory on `PYTHONPATH`, and the same Neo4j environment variables configured for the task worker.

Install Airflow using the official constraints file for your Python/Airflow version rather than relying on a generic unconstrained pip install. Then place or mount the DAG in the Airflow `dags/` directory. The DAG can be changed to call `ingest_openalex_search()` for a scheduled OpenAlex search.

## Suggested next improvements

- Add incremental loading using OpenAlex `updated_date` and watermarks.
- Add a dead-letter/quarantine output for invalid records instead of rejecting the full batch.
- Add Neo4j integration tests with Testcontainers.
- Add metrics, structured logs, retries, and alerting to the scheduled pipeline.
- Add pagination and authentication/rate limiting to the API before public deployment.

## Project status

This is a learning/portfolio project. It includes local demo data, tested validation and API logic, and an optional Airflow DAG. Production deployment would require operational controls, monitoring, secrets management, and integration tests against a running Neo4j service.

## License

MIT
