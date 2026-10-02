from __future__ import annotations

from typing import Any

import pytest

from kap_mcp.files import SafeFileStore
from kap_mcp.services import KapService


class FakeAdapter:
    async def smart_search(self, term: str) -> list[dict[str, Any]]:
        return [
            {"searchValue": "Unrelated", "searchType": "C", "memberOrFundOid": "wrong", "cmpOrFundCode": "ZZZ"},
            {"searchValue": "AK PORTFÖY YENİ TEKNOLOJİLER YABANCI HİSSE SENEDİ FONU", "searchType": "F", "memberOrFundOid": "aft-id", "cmpOrFundCode": "aft"},
        ]

    async def list_funds(self, fund_type: str = "ALL", state: str = "Y") -> list[dict[str, Any]]:
        if state == "T":
            return []
        return [{"fundOid": "aft-id", "fundName": "AFT Fund", "fundCode": "AFT", "fundType": "YF", "fundState": "Y", "fundPermaLink": "aft", "mkkMemberOid": "founder", "title": "Founder"}]
    async def find_fund_by_code(self, code: str, include_inactive: bool = True) -> dict[str, Any] | None:
        funds = await self.list_funds("ALL", "Y")
        return next((fund for fund in funds if fund["fundCode"].casefold() == code.casefold()), None)


    async def fund_disclosures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"publishDate": "02.09.2026 17:53:14", "fundCode": "AFT", "kapTitle": "AFT Fund", "disclosureType": "FON", "subject": "Portföy Dağılım Raporu", "summary": "Aylık Rapor", "year": 2026, "period": 8, "disclosureIndex": 1657446, "attachmentCount": 1, "modifyStatus": None},
            {"publishDate": "03.09.2026 17:53:14", "fundCode": "AFT", "kapTitle": "AFT Fund", "disclosureType": "FON", "subject": "Başka Rapor", "summary": "Aylık Rapor", "year": 2026, "period": 9, "disclosureIndex": 1657447, "attachmentCount": 0, "modifyStatus": None},
        ]


class FuzzyFundAdapter(FakeAdapter):
    async def smart_search(self, term: str) -> list[dict[str, Any]]:
        return [
            {
                "searchValue": "LOGOS PORTFÖY DİNAMİK DAĞILIMLI SERBEST FON",
                "searchType": "F",
                "memberOrFundOid": "idd-id",
                "cmpOrFundCode": "IDD",
            }
        ]

    async def find_fund_by_code(self, code: str, include_inactive: bool = True) -> dict[str, Any] | None:
        if code.casefold() != "hdd":
            return None
        return {
            "fundOid": "hdd-id",
            "fundName": "AHLATCI PORTFÖY BİRİNCİ DEĞİŞKEN FON",
            "fundCode": "HDD",
            "fundType": "YF",
            "fundState": "Y",
            "fundPermaLink": "hdd",
            "mkkMemberOid": "founder-id",
            "title": "AHLATCI PORTFÖY YÖNETİMİ A.Ş.",
        }

    async def fund_disclosures(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        assert payload["fundOidList"] == ["hdd-id"]
        return [
            {
                "publishDate": "08.09.2026 16:31:22",
                "fundCode": "HDD",
                "kapTitle": "HDD Fund",
                "disclosureType": "FON",
                "subject": "Portföy Dağılım Raporu",
                "summary": "Portföy Dağılım Raporu",
                "year": 2026,
                "period": 8,
                "disclosureIndex": 1660216,
                "attachmentCount": 1,
                "modifyStatus": None,
            }
        ]


@pytest.fixture
def service(tmp_path):
    return KapService(FakeAdapter(), SafeFileStore(tmp_path))


@pytest.mark.asyncio
async def test_exact_fund_code_is_ranked_first(service: KapService) -> None:
    result = await service.search_entities("AFT", [], True, 20)
    assert result["items"][0]["code"] == "AFT"
    assert result["items"][0]["entity_id"] == "aft-id"



@pytest.mark.asyncio
async def test_exact_fund_code_falls_back_to_fund_catalog_when_smart_search_is_fuzzy(tmp_path) -> None:
    service = KapService(FuzzyFundAdapter(), SafeFileStore(tmp_path))

    found = await service.search_entities("hdd", [], True, 20)
    assert found["items"][0] == {
        "code": "HDD",
        "entity_id": "hdd-id",
        "name": "AHLATCI PORTFÖY BİRİNCİ DEĞİŞKEN FON",
        "entity_type": "fund",
        "active": True,
        "permalink": "hdd",
        "portfolio_company_id": "founder-id",
        "portfolio_company": "AHLATCI PORTFÖY YÖNETİMİ A.Ş.",
        "upstream_type": "YF",
    }

    disclosures = await service.query_disclosures(
        ["HDD"], [], ["portfolio_allocation_report"], [], None, None, None, None, None,
        True, True, True, False, 1, None,
    )
    assert disclosures["items"][0]["disclosure_index"] == 1660216

@pytest.mark.asyncio
async def test_period_query_includes_following_month_publication(service: KapService) -> None:
    result = await service.query_disclosures(
        ["AFT"], [], ["portfolio_allocation_report"], [], None, None, 2026, 8, None,
        False, True, True, False, 50, None,
    )
    assert [item["disclosure_index"] for item in result["items"]] == [1657446]
