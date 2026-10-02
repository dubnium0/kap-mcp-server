from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


EntityType = Literal[
    "company", "fund", "pension_fund", "etf", "real_estate_fund",
    "venture_capital_fund", "portfolio_company", "investment_trust", "other",
]
ReportType = Literal[
    "material_event", "financial_report", "fund_financial_report",
    "portfolio_allocation_report", "independent_audit_report", "annual_report",
    "sustainability_report", "dividend", "capital_increase", "capital_decrease",
    "general_assembly", "merger", "demerger", "share_buyback", "credit_rating",
    "management_change", "related_party_transaction", "asset_sale", "public_offering", "other",
]


class Period(BaseModel):
    year: int = Field(ge=2009, le=2100)
    period: int | None = Field(default=None, ge=1, le=4)
    month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def exactly_one_kind(self) -> Period:
        if (self.period is None) == (self.month is None):
            raise ValueError("period veya month alanlarından tam biri verilmelidir")
        return self


class Entity(BaseModel):
    code: str | None = None
    entity_id: str
    name: str
    entity_type: EntityType
    active: bool = True
    permalink: str | None = None
    portfolio_company_id: str | None = None
    portfolio_company: str | None = None
    upstream_type: str | None = None


class Disclosure(BaseModel):
    disclosure_index: int
    entity_code: str | None = None
    entity_type: EntityType | None = None
    entity_name: str
    publish_datetime: str
    report_type: ReportType
    subject: str
    summary: str | None = None
    year: int | None = None
    month: int | None = None
    period: int | str | None = None
    attachment_count: int = 0
    modify_status: str | None = None
    disclosure_url: str
    files: list[dict[str, Any]] | None = None


class FileMetadata(BaseModel):
    file_name: str
    attachment_id: str | None = None
    mime_type: str
    url: str
    size_bytes: int | None = None
    sha256: str | None = None
    content_base64: str | None = None


class PortfolioPosition(BaseModel):
    group: str
    security: str
    currency: str | None = None
    isin: str | None = None
    nominal_value: Decimal | None = None
    daily_value: Decimal | None = None
    total_value: Decimal
    group_percent: Decimal | None = None
    portfolio_percent: Decimal | None = None
    fund_total_percent: Decimal | None = None


class ValidationResult(BaseModel):
    calculated_total: Decimal
    reported_total: Decimal
    difference: Decimal
    valid: bool
    warnings: list[str] = []
