from __future__ import annotations
import asyncio

from typing import Any
from urllib.parse import quote

from .cache import TTLCache
from .client import KapHttpClient


class KapApiAdapter:
    def __init__(self, client: KapHttpClient) -> None:
        self.client = client
        self.cache = TTLCache(ttl_seconds=900, max_entries=32)

    async def smart_search(self, term: str) -> list[dict[str, Any]]:
        data = await self.client.post_json(
            "/search/smart",
            {"keyword": term, "discClass": "ALL", "lang": "tr", "channel": "WEB"},
        )
        return [item for group in data for item in group.get("results", [])]

    async def list_funds(self, fund_type: str = "ALL", state: str = "Y") -> list[dict[str, Any]]:
        key = f"funds:{fund_type}:{state}"

        async def load() -> list[dict[str, Any]]:
            if fund_type != "ALL":
                return await self.client.get_json(f"/fund/criteria/{fund_type}/{state}")
            types = ("BYF", "YF", "EYF", "OKS", "YYF", "VFF", "KFF", "GMF", "GSF", "PFF", "TEYF")
            pages = await asyncio.gather(
                *(self.client.get_json(f"/fund/criteria/{item}/{state}") for item in types)
            )
            unique: dict[str, dict[str, Any]] = {}
            for page in pages:
                if not isinstance(page, list):
                    continue
                for fund in page:
                    if isinstance(fund, dict) and fund.get("fundOid"):
                        unique[fund["fundOid"]] = fund
            return list(unique.values())

        return await self.cache.get_or_load(key, load)
    async def find_fund_by_code(self, code: str, include_inactive: bool = True) -> dict[str, Any] | None:
        wanted = code.casefold()
        states = ("Y", "T") if include_inactive else ("Y",)
        for state in states:
            for fund_type in ("YF", "BYF", "EYF", "OKS", "YYF", "VFF", "KFF", "GMF", "GSF", "PFF", "TEYF"):
                funds = await self.list_funds(fund_type, state)
                if not isinstance(funds, list):
                    continue
                match = next(
                    (fund for fund in funds if str(fund.get("fundCode", "")).casefold() == wanted),
                    None,
                )
                if match:
                    return match
        return None

    async def member_filter(self, term: str) -> list[dict[str, Any]]:
        return await self.client.get_json(f"/member/filter/{quote(term, safe='')}")

    async def member_disclosures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return await self.client.post_json("/disclosure/members/byCriteria", payload)

    async def fund_disclosures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return await self.client.post_json("/disclosure/funds/byCriteria", payload)

    async def latest_disclosures(self) -> list[dict[str, Any]]:
        return await self.client.get_json("/disclosure/list/light")

    async def disclosure_detail(self, disclosure_index: int) -> list[dict[str, Any]]:
        return await self.client.get_json(f"/notification/attachment-detail/{disclosure_index}")

    async def expected_company(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return await self.client.post_json("/expected-disclosure-inquiry/company", payload)

    async def expected_fund(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return await self.client.post_json("/expected-disclosure-inquiry/fund", payload)

    async def financial_filings(self, oid: str, year: int, period: int) -> list[dict[str, Any]]:
        return await self.client.get_json(f"/financialTable/listCompanyExcelMembers/{quote(oid, safe='')}/{year}/{period}")

    async def financial_package(self, oid: str, year: int, period: int) -> tuple[bytes, str | None, str]:
        return await self.client.get_bytes(f"/home-financial/download-file/{quote(oid, safe='')}/{year}/{period}")

    async def attachment(self, object_id: str) -> tuple[bytes, str | None, str]:
        return await self.client.get_bytes(f"/file/download/{quote(object_id, safe='')}")

    async def rendered_pdf(self, disclosure_index: int) -> tuple[bytes, str | None, str]:
        return await self.client.get_bytes(f"/BildirimPdf/{disclosure_index}")

    async def corporate_actions(self, from_date: str, to_date: str, action_type: str | None = None) -> Any:
        # KAP's current client uses dd.MM.yyyy in this path.
        endpoint = "filteredCa" if action_type else "allCa"
        suffix = f"/{quote(action_type, safe='')}" if action_type else ""
        return await self.client.get_json(f"/ca/{endpoint}/{from_date}/{to_date}{suffix}")
