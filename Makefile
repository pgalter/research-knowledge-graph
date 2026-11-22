.PHONY: install test validate run-api up down ingest

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

validate:
	python -m knowledge_graph.pipeline --input data/sample_graph.json --validate-only

run-api:
	uvicorn knowledge_graph.api:app --reload

up:
	docker compose up --build -d

down:
	docker compose down

ingest:
	python -m knowledge_graph.pipeline --input data/sample_graph.json
