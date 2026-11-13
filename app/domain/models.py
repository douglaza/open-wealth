"""Domínio puro: sem imports de HTTP, DB ou framework além do Pydantic."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

class Position(BaseModel):
    institution: str
    account_type: str
    asset_name: str
    category: str
    amount: float
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def _patrimonio_nao_negativo(self):
        # apenas cartão de crédito pode ser negativo = dívida;
        # todo o resto é patrimônio e precisa ser >= 0
        if self.account_type != "CREDIT" and self.amount < 0:
            raise ValueError(f"patrimônio não pode ser negativo: {self.amount}")
        return self


class Snapshot(BaseModel):
    snapshot_date: date
    positions: list[Position] = Field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(p.amount for p in self.positions)
