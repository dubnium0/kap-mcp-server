from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "search_entities", "get_entity", "query_disclosures", "get_disclosure",
    "get_disclosure_file", "download_file", "get_financials", "get_fund_portfolio",
    "get_corporate_actions", "get_expected_disclosures",
}


def _payload(result: Any) -> Any:
    if getattr(result, "structuredContent", None) is not None:
        return result.structuredContent
    for part in result.content:
        text = getattr(part, "text", None)
        if text:
            return json.loads(text)
    raise RuntimeError("MCP tool JSON içerik döndürmedi")


async def run_smoke() -> dict[str, Any]:
    params = StdioServerParameters(command=sys.executable, args=["-m", "kap_mcp.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == EXPECTED_TOOLS, {"expected": sorted(EXPECTED_TOOLS), "actual": sorted(names)}

            search = _payload(await session.call_tool("search_entities", {"query": "AFT"}))
            assert search["items"][0]["code"] == "AFT"
            entity = _payload(await session.call_tool("get_entity", {"code": "AFT", "sections": ["summary"]}))
            assert entity["entity"]["code"] == "AFT"


            disclosures = _payload(await session.call_tool("query_disclosures", {
                "entity_codes": ["AFT"], "report_types": ["portfolio_allocation_report"],
                "year": 2026, "month": 8, "limit": 10,
            }))
            assert disclosures["items"][0]["disclosure_index"] == 1657446

            detail = _payload(await session.call_tool("get_disclosure", {"disclosure_index": 1657446}))
            assert detail["metadata"]["disclosureIndex"] == 1657446

            file = _payload(await session.call_tool("get_disclosure_file", {"disclosure_index": 1657446, "action": "link"}))
            assert file["file_name"] == "AFT_2026.08.pdf"
            assert file["attachment_id"] == "4028328d9f52dddd01a06297b1c4308c"

            portfolio = _payload(await session.call_tool("get_fund_portfolio", {"fund_code": "AFT", "year": 2026, "month": 8}))
            assert portfolio["positions"] and DecimalLike.positive(portfolio["portfolio_total"])

            company = _payload(await session.call_tool("query_disclosures", {"entity_codes": ["THYAO"], "from_date": "2026-09-01", "to_date": "2026-09-30", "limit": 1}))
            assert company["items"] and company["items"][0]["entity_code"] == "THYAO"

            financials = _payload(await session.call_tool("get_financials", {
                "company_code": "THYAO",
                "periods": [{"year": 2025, "period": 4}],
                "statement_types": ["balance_sheet", "income_statement", "cash_flow"],
                "mode": "summary",
            }))
            assert financials["periods"][0]["format"] == "IFRS"
            assert financials["periods"][0]["statements"]

            expected = _payload(await session.call_tool("get_expected_disclosures", {"entity_codes": ["AFT"], "from_date": "2026-01-01", "to_date": "2026-12-31"}))
            assert expected["items"]

            actions = _payload(await session.call_tool("get_corporate_actions", {"from_date": "2026-09-01", "to_date": "2026-09-30"}))
            assert "items" in actions

            return {
                "ok": True,
                "tool_count": len(names),
                "financial_statement_count": len(financials["periods"][0]["statements"]),
                "portfolio_positions": len(portfolio["positions"]),
                "portfolio_validation": portfolio["validation"],
                "corporate_action_count": len(actions["items"]),
            }


class DecimalLike:
    @staticmethod
    def positive(value: Any) -> bool:
        return float(value) > 0


def main() -> None:
    print(json.dumps(asyncio.run(run_smoke()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
