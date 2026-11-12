"""Domínio puro: sem imports de HTTP, DB ou framework além do Pydantic."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class Position(BaseModel):
    institution: str
    account_type: str
    asset_name: str
    category: str
    amount: float = Field(ge=0)  # patrimônio nunca é negativo
    updated_at: datetime = Field(default_factory=datetime.now)


class Snapshot(BaseModel):
    snapshot_date: date
    positions: list[Position] = Field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(p.amount for p in self.positions)
