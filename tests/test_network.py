from __future__ import annotations

import pytest

from kap_mcp.adapter import KapApiAdapter
from kap_mcp.client import KapHttpClient
from kap_mcp.services import KapService


@pytest.mark.network
@pytest.mark.asyncio
async def test_historical_aft_disclosure_and_file() -> None:
    async with KapHttpClient() as client:
        service = KapService(KapApiAdapter(client))
        found = await service.search_entities("AFT", [], True, 20)
        assert found["items"][0]["code"] == "AFT"
        disclosures = await service.query_disclosures(
            ["AFT"], [], ["portfolio_allocation_report"], [], None, None, 2026, 8, None,
            False, True, True, False, 10, None,
        )
        assert disclosures["items"][0]["disclosure_index"] == 1657446
        detail = await service.get_disclosure(1657446, "structured", True, True)
        assert detail["metadata"]["disclosureIndex"] == 1657446
        file = await service.get_disclosure_file(1657446, "primary_attachment", None, "link")
        assert file["file_name"] == "AFT_2026.08.pdf"
        assert file["attachment_id"] == "4028328d9f52dddd01a06297b1c4308c"


@pytest.mark.network
@pytest.mark.asyncio
async def test_expected_company_and_fund_disclosures() -> None:
    async with KapHttpClient() as client:
        service = KapService(KapApiAdapter(client))
        result = await service.get_expected_disclosures(["AFT", "THYAO"], "2026-01-01", "2026-12-31")
        assert any(item.get("fundCode") == "AFT" for item in result["items"])
        assert any(item.get("stockCode") == "THYAO" for item in result["items"])
