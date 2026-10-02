from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from .adapter import KapApiAdapter
from .client import KapHttpClient
from .errors import VALIDATION_ERROR, KapError
from .services import KapService

mcp = FastMCP(
    "kap-mcp",
    instructions=(
        "KAP'ın sürümlenmemiş kamu web API'sini görev odaklı ve normalize edilmiş biçimde sunar. "
        "upstream_changed hataları KAP iç API sözleşmesinin değiştiğini gösterebilir."
    ),
)
_client = KapHttpClient()
_service = KapService(KapApiAdapter(_client))


async def _safe(call: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    try:
        return await call()
    except KapError as exc:
        return exc.as_dict()
    except ValidationError as exc:
        return KapError(VALIDATION_ERROR, "Argüman doğrulaması başarısız.", context={"details": exc.errors(include_url=False)}).as_dict()


@mcp.tool()
async def search_entities(
    query: str,
    entity_types: list[str] = [],
    active_only: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    """Şirket, fon, portföy yönetim şirketi ve diğer KAP üyelerini arar."""
    return await _safe(lambda: _service.search_entities(query, entity_types, active_only, limit))


@mcp.tool()
async def get_entity(
    code: str | None = None,
    entity_id: str | None = None,
    sections: list[str] = ["summary"],
) -> dict[str, Any]:
    """Kesin şirket veya fon profilini getirir; belirsiz eşleşmeyi seçmez."""
    return await _safe(lambda: _service.get_entity(code, entity_id, sections))


@mcp.tool()
async def query_disclosures(
    entity_codes: list[str] = [],
    entity_types: list[str] = [],
    report_types: list[str] = [],
    subjects: list[str] = [],
    from_date: str | None = None,
    to_date: str | None = None,
    year: int | None = None,
    month: int | None = None,
    period: int | None = None,
    latest: bool = False,
    latest_revision_only: bool = True,
    has_attachments: bool | None = None,
    include_files: bool = False,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Şirket ve fon bildirimlerini tek kısa sonuç sözleşmesinde sorgular."""
    return await _safe(lambda: _service.query_disclosures(
        entity_codes, entity_types, report_types, subjects, from_date, to_date, year, month,
        period, latest, latest_revision_only, has_attachments, include_files, limit, cursor,
    ))


@mcp.tool()
async def get_disclosure(
    disclosure_index: int,
    content_format: str = "structured",
    include_attachments: bool = True,
    include_revision_chain: bool = True,
) -> dict[str, Any]:
    """Tek bildirimin içeriğini, eklerini ve revizyon ilişkisini getirir."""
    return await _safe(lambda: _service.get_disclosure(disclosure_index, content_format, include_attachments, include_revision_chain))


@mcp.tool()
async def get_disclosure_file(
    disclosure_index: int,
    file_selector: str = "primary_attachment",
    attachment_id: str | None = None,
    action: str = "link",
) -> dict[str, Any]:
    """Bildirim dosyasının bağlantısını, metadata bilgisini veya doğrulanmış içeriğini getirir; diske yazmaz."""
    return await _safe(lambda: _service.get_disclosure_file(disclosure_index, file_selector, attachment_id, action))


@mcp.tool()
async def download_file(
    attachment_id: str | None = None,
    disclosure_index: int | None = None,
    file_selector: str = "primary_attachment",
    output_directory: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """KAP dosyasını izin verilen yerel kök içine güvenle indirir."""
    return await _safe(lambda: _service.download_file(attachment_id, disclosure_index, file_selector, output_directory, output_name, overwrite))


@mcp.tool()
async def get_financials(
    company_code: str,
    periods: list[dict[str, Any]],
    statement_types: list[str] = ["balance_sheet", "income_statement", "cash_flow"],
    mode: str = "full",
    consolidation: str = "prefer_consolidated",
    include_ratios: bool = False,
) -> dict[str, Any]:
    """Şirket finansal tablolarını IFRS, BDDK veya sigorta metadata bilgisiyle getirir."""
    return await _safe(lambda: _service.get_financials(company_code, periods, statement_types, mode, consolidation, include_ratios))


@mcp.tool()
async def get_fund_portfolio(
    fund_code: str,
    periods: list[dict[str, Any]] | None = None,
    year: int | None = None,
    month: int | None = None,
    latest: bool = False,
    include_positions: bool = True,
    include_totals: bool = True,
) -> dict[str, Any]:
    """Fon portföy PDF'sini bulur, doğrular ve yapılandırılmış pozisyonlara dönüştürür."""
    return await _safe(lambda: _service.get_fund_portfolio(fund_code, periods, year, month, latest, include_positions, include_totals))


@mcp.tool()
async def get_corporate_actions(
    company_codes: list[str] = [],
    action_types: list[str] = [],
    from_date: str | None = None,
    to_date: str | None = None,
    latest: bool = False,
) -> dict[str, Any]:
    """Temettü, sermaye işlemleri, genel kurul ve diğer hak kullanımlarını getirir."""
    return await _safe(lambda: _service.get_corporate_actions(company_codes, action_types, from_date, to_date, latest))


@mcp.tool()
async def get_expected_disclosures(
    entity_codes: list[str],
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Şirket ve fonların ileri tarihli beklenen bildirim takvimini getirir."""
    return await _safe(lambda: _service.get_expected_disclosures(entity_codes, from_date, to_date))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
