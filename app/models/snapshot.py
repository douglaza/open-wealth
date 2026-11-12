"""DEPRECATED: use app.domain.models. Mantido até o fim da Fase 2."""
from app.domain.models import Position, Snapshot  # noqa: F401

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Position:
    institution: str
    account_type: str
    asset_name: str
    category: str
    amount: float
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Snapshot:
    snapshot_date: date
    positions: list[Position]

    @property
    def total(self) -> float:
        return sum(p.amount for p in self.positions)
