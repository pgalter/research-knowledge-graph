"""FastAPI read API for the Neo4j research knowledge graph."""

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query

from knowledge_graph.neo4j_store import Neo4jStore


def create_app(store: Any | None = None) -> FastAPI:
    app = FastAPI(
        title="Research Knowledge Graph API",
        description="Explore authors, works, affiliations, topics, and citation links.",
        version="1.0.0",
    )
    app.state.graph_store = store

    def get_store() -> Any:
        if app.state.graph_store is None:
            app.state.graph_store = Neo4jStore.from_env()
        return app.state.graph_store

    @app.get("/health", tags=["operations"])
    def health(graph: Any = Depends(get_store)) -> dict[str, str]:
        try:
            graph.ping()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Neo4j is unavailable") from exc
        return {"status": "ok", "database": "neo4j"}

    @app.get("/graph/stats", tags=["graph"])
    def graph_stats(graph: Any = Depends(get_store)) -> dict[str, int]:
        return graph.get_stats()

    @app.get("/authors/{author_id}/network", tags=["authors"])
    def author_network(
        author_id: str,
        limit: int = Query(default=10, ge=1, le=100),
        graph: Any = Depends(get_store),
    ) -> dict[str, Any]:
        result = graph.get_author_network(author_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Author '{author_id}' not found")
        return {
            "author": result["author"],
            "works": result.get("works", [])[:limit],
            "coauthors": result.get("coauthors", [])[:limit],
        }

    @app.get("/works/{work_id}", tags=["works"])
    def work_detail(work_id: str, graph: Any = Depends(get_store)) -> dict[str, Any]:
        result = graph.get_work(work_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Work '{work_id}' not found")
        return result

    return app


app = create_app()
