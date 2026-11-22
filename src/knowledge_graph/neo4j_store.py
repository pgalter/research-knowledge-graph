"""Neo4j persistence and read queries for the research graph."""

from typing import Any

from knowledge_graph.config import settings
from knowledge_graph.models import GraphDataset


class Neo4jStore:
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        driver: Any | None = None,
    ) -> None:
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:  # pragma: no cover - dependency install message
                raise RuntimeError(
                    "Neo4j driver is missing. Install project dependencies with `pip install -e .`."
                ) from exc
            driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver = driver
        self.database = database

    @classmethod
    def from_env(cls) -> "Neo4jStore":
        return cls(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )

    def close(self) -> None:
        self.driver.close()

    def ping(self) -> bool:
        self.driver.verify_connectivity()
        return True

    def ensure_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT author_id IF NOT EXISTS FOR (n:Author) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (n:Institution) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (n:Topic) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT work_id IF NOT EXISTS FOR (n:Work) REQUIRE n.id IS UNIQUE",
        ]
        with self.driver.session(database=self.database) as session:
            for statement in constraints:
                session.run(statement)

    def load_dataset(self, dataset: GraphDataset) -> None:
        payload = dataset.model_dump(mode="json")
        with self.driver.session(database=self.database) as session:
            session.execute_write(self._write_dataset, payload)

    @staticmethod
    def _write_dataset(tx: Any, payload: dict[str, Any]) -> None:
        node_queries = [
            (
                """
                UNWIND $rows AS row
                MERGE (n:Author {id: row.id})
                SET n.name = row.name, n.orcid = row.orcid
                """,
                payload["authors"],
            ),
            (
                """
                UNWIND $rows AS row
                MERGE (n:Institution {id: row.id})
                SET n.name = row.name, n.country_code = row.country_code
                """,
                payload["institutions"],
            ),
            (
                """
                UNWIND $rows AS row
                MERGE (n:Topic {id: row.id})
                SET n.name = row.name
                """,
                payload["topics"],
            ),
            (
                """
                UNWIND $rows AS row
                MERGE (n:Work {id: row.id})
                SET n.title = row.title, n.year = row.year,
                    n.citation_count = row.citation_count
                """,
                payload["works"],
            ),
        ]
        for query, rows in node_queries:
            if rows:
                tx.run(query, rows=rows)

        edges = {
            "authored": [
                {"author_id": author["id"], "work_id": work["id"]}
                for work in payload["works"]
                for author in [{"id": value} for value in work["author_ids"]]
            ],
            "affiliated": [
                {"author_id": author["id"], "institution_id": institution_id}
                for author in payload["authors"]
                for institution_id in author["institution_ids"]
            ],
            "topics": [
                {"work_id": work["id"], "topic_id": topic_id}
                for work in payload["works"]
                for topic_id in work["topic_ids"]
            ],
            "citations": [
                {"work_id": work["id"], "cited_work_id": cited_id}
                for work in payload["works"]
                for cited_id in work["references"]
            ],
        }
        edge_queries = [
            (
                """
                UNWIND $rows AS row
                MATCH (a:Author {id: row.author_id})
                MATCH (w:Work {id: row.work_id})
                MERGE (a)-[:AUTHORED]->(w)
                """,
                edges["authored"],
            ),
            (
                """
                UNWIND $rows AS row
                MATCH (a:Author {id: row.author_id})
                MATCH (i:Institution {id: row.institution_id})
                MERGE (a)-[:AFFILIATED_WITH]->(i)
                """,
                edges["affiliated"],
            ),
            (
                """
                UNWIND $rows AS row
                MATCH (w:Work {id: row.work_id})
                MATCH (t:Topic {id: row.topic_id})
                MERGE (w)-[:HAS_TOPIC]->(t)
                """,
                edges["topics"],
            ),
            (
                """
                UNWIND $rows AS row
                MATCH (w:Work {id: row.work_id})
                MATCH (cited:Work {id: row.cited_work_id})
                MERGE (w)-[:CITES]->(cited)
                """,
                edges["citations"],
            ),
        ]
        for query, rows in edge_queries:
            if rows:
                tx.run(query, rows=rows)

    def get_author_network(self, author_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (a:Author {id: $author_id})
        OPTIONAL MATCH (a)-[:AUTHORED]->(w:Work)
        OPTIONAL MATCH (co:Author)-[:AUTHORED]->(w)
        WHERE co.id <> a.id
        RETURN a{.id, .name, .orcid} AS author,
               [item IN collect(DISTINCT w) WHERE item IS NOT NULL |
                 item{.id, .title, .year, .citation_count}] AS works,
               [item IN collect(DISTINCT co) WHERE item IS NOT NULL |
                 item{.id, .name}] AS coauthors
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(query, author_id=author_id).single()
        return record.data() if record else None

    def get_work(self, work_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (w:Work {id: $work_id})
        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(w)
        OPTIONAL MATCH (w)-[:HAS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (a)-[:AFFILIATED_WITH]->(i:Institution)
        RETURN w{.id, .title, .year, .citation_count} AS work,
               [item IN collect(DISTINCT a) WHERE item IS NOT NULL |
                 item{.id, .name, .orcid}] AS authors,
               [item IN collect(DISTINCT t) WHERE item IS NOT NULL |
                 item{.id, .name}] AS topics,
               [item IN collect(DISTINCT i) WHERE item IS NOT NULL |
                 item{.id, .name, .country_code}] AS institutions
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(query, work_id=work_id).single()
        return record.data() if record else None

    def get_stats(self) -> dict[str, int]:
        labels = {
            "authors": "Author",
            "institutions": "Institution",
            "topics": "Topic",
            "works": "Work",
        }
        result: dict[str, int] = {}
        with self.driver.session(database=self.database) as session:
            for key, label in labels.items():
                record = session.run(
                    f"MATCH (n:{label}) RETURN count(n) AS count"
                ).single()
                result[key] = int(record["count"] if record else 0)
        return result
