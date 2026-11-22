"""Typed records used between ingestion, validation, and graph persistence."""

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Author(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    orcid: str | None = None
    institution_ids: list[str] = Field(default_factory=list)


class Institution(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    country_code: str | None = None


class Topic(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Work(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    citation_count: int = Field(default=0, ge=0)
    author_ids: list[str] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class GraphDataset(StrictModel):
    authors: list[Author] = Field(default_factory=list)
    institutions: list[Institution] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    works: list[Work] = Field(default_factory=list)
