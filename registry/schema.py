from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceSpec(BaseModel):
    id: str = ""
    name: str
    category: Literal["search_engine", "api_feed", "web_feed", "known_site"] = "search_engine"
    access: Literal["tor", "direct", "api"] = "tor"
    enabled: bool = True
    parser: str = "generic"
    timeout: int = 40
    rate_limit_per_minute: int | None = None
    tags: list[str] = Field(default_factory=list)
    supports_query: bool = True
    notes: str = ""
    url_template: str = ""

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value):
        return str(value or "").strip().lower().replace(" ", "_")

    @field_validator("name", "parser", "notes", "url_template", mode="before")
    @classmethod
    def stringify(cls, value):
        return str(value or "").strip()

    @field_validator("timeout")
    @classmethod
    def positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("timeout must be positive")
        return value

    def model_post_init(self, __context):
        if not self.id:
            self.id = self.name.strip().lower().replace(" ", "_")
        if self.supports_query and self.category == "search_engine" and "{query}" not in self.url_template:
            raise ValueError("search_engine sources must include url_template with {query}")
