"""Environment-backed application settings."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "please-change-me")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    openalex_api_key: str | None = os.getenv("OPENALEX_API_KEY") or None
    openalex_mailto: str | None = os.getenv("OPENALEX_MAILTO") or None


settings = Settings()
