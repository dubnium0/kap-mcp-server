from __future__ import annotations

import base64
import html
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from .adapter import KapApiAdapter
from .errors import (
    ATTACHMENT_NOT_FOUND,
    DISCLOSURE_NOT_FOUND,
    ENTITY_AMBIGUOUS,
    ENTITY_NOT_FOUND,
    UNSUPPORTED_DOCUMENT,
    VALIDATION_ERROR,
    KapError,
)
from .files import SafeFileStore, mime_for_name, verify_file
from .models import Disclosure, Entity, Period
from .parsers import parse_financial_package, parse_fund_portfolio


_FUND_TYPE_MAP = {
    "BYF": "etf", "YF": "fund", "EYF": "pension_fund", "OKS": "pension_fund",
    "GMF": "real_estate_fund", "GSF": "venture_capital_fund",
}
_REPORT_SUBJECTS = {
    "portföy dağılım": "portfolio_allocation_report",
    "finansal rapor": "financial_report",
    "finansal tablo": "financial_report",
    "bağımsız denet": "independent_audit_report",
    "faaliyet rapor": "annual_report",
    "sürdürülebilir": "sustainability_report",
    "kar pay": "dividend",
    "kâr pay": "dividend",
    "temettü": "dividend",
    "sermaye artır": "capital_increase",
    "sermaye azalt": "capital_decrease",
    "genel kurul": "general_assembly",
    "birleşme": "merger",
    "bölünme": "demerger",
    "pay geri al": "share_buyback",
    "kredi derecelend": "credit_rating",
    "yönetim": "management_change",
    "ilişkili taraf": "related_party_transaction",
    "varlık satış": "asset_sale",
    "halka arz": "public_offering",
    "özel durum": "material_event",
}
_BANK_CODES = {"AKBNK", "ALBRK", "GARAN", "HALKB", "ICBCT", "ISCTR", "KLNMA", "QNBTR", "SKBNK", "TSKB", "VAKBN", "YKBNK"}
_INSURANCE_CODES = {"AGESA", "AKGRT", "ANHYT", "ANSGR", "RAYSG", "TURSG"}


def _report_type(subject: str, disclosure_type: str = "", entity_type: str | None = None) -> str:
    folded = subject.casefold()
    for needle, report_type in _REPORT_SUBJECTS.items():
        if needle in folded:
            if report_type == "financial_report" and entity_type == "fund":
                return "fund_financial_report"
            return report_type
    if disclosure_type == "ODA":
        return "material_event"
    return "other"


def _iso_datetime(value: str) -> str:
    for pattern in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.astimezone().isoformat()
        except ValueError:
            pass
    return value


def _html_to_text(parts: list[str]) -> str:
    text = "\n".join(parts)
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(?:p|div|tr|li|h\d)>", "\n", text, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _date_range(from_date: str | None, to_date: str | None, year: int | None, month: int | None, latest: bool) -> tuple[date, date]:
    try:
        if year is not None and month is not None:
            start = date(year, month, 1)
            next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
            return start, next_month + timedelta(days=14)
        if year is not None:
            return date(year, 1, 1), date(year, 12, 31)
        if from_date or to_date:
            end = date.fromisoformat(to_date) if to_date else date.today()
            start = date.fromisoformat(from_date) if from_date else end - timedelta(days=30)
            if start > end or (end - start).days > 3660:
                raise ValueError
            return start, end
    except ValueError as exc:
        raise KapError(VALIDATION_ERROR, "Geçersiz veya aşırı geniş tarih aralığı.") from exc
    end = date.today()
    return end - timedelta(days=90 if latest else 30), end


def _cursor_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(base64.urlsafe_b64decode(cursor + "===").decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise KapError(VALIDATION_ERROR, "Geçersiz cursor.") from exc


class KapService:
    def __init__(self, adapter: KapApiAdapter, file_store: SafeFileStore | None = None) -> None:
        self.adapter = adapter
        self.file_store = file_store or SafeFileStore()

    async def search_entities(self, query: str, entity_types: list[str], active_only: bool, limit: int) -> dict[str, Any]:
        query = query.strip()
        if len(query) < 2 or limit < 1 or limit > 100:
            raise KapError(VALIDATION_ERROR, "query en az 2 karakter; limit 1-100 arasında olmalıdır.")
        raw = await self.adapter.smart_search(query)
        entities: dict[tuple[str, str], Entity] = {}
        for item in raw:
            search_type = item.get("searchType")
            kind = "company" if search_type == "C" else "fund" if search_type == "F" else "other"
            if entity_types and kind not in entity_types:
                continue
            raw_code = item.get("cmpOrFundCode")
            entity = Entity(
                code=raw_code.upper() if raw_code else None,
                entity_id=str(item.get("memberOrFundOid") or ""),
                name=item.get("searchValue") or "",
                entity_type=kind,
            )
            if entity.entity_id:
                entities[(kind, entity.entity_id)] = entity
        exact = [entity for entity in entities.values() if (entity.code or "").casefold() == query.casefold()]
        if not exact and re.fullmatch(r"[A-Za-z0-9]{2,8}", query):
            fund = await self.adapter.find_fund_by_code(query, include_inactive=not active_only)
            if fund:
                fund_type = str(fund.get("fundType") or "")
                kind = _FUND_TYPE_MAP.get(fund_type, "fund")
                if not entity_types or kind in entity_types:
                    entity = Entity(
                        code=str(fund["fundCode"]).upper(),
                        entity_id=str(fund["fundOid"]),
                        name=str(fund.get("fundName") or ""),
                        entity_type=kind,
                        active=fund.get("fundState") == "Y",
                        permalink=fund.get("fundPermaLink"),
                        portfolio_company_id=fund.get("mkkMemberOid"),
                        portfolio_company=fund.get("title"),
                        upstream_type=fund_type or None,
                    )
                    entities[(kind, entity.entity_id)] = entity
                    exact = [entity]
        others = [entity for entity in entities.values() if entity not in exact]
        items = exact + others
        return {"items": [item.model_dump(mode="json") for item in items[:limit]], "count": min(len(items), limit)}

    async def resolve_entity(self, code: str | None = None, entity_id: str | None = None) -> Entity:
        if not code and not entity_id:
            raise KapError(VALIDATION_ERROR, "code veya entity_id gereklidir.")
        if code:
            results = (await self.search_entities(code, [], False, 100))["items"]
            exact = [Entity.model_validate(item) for item in results if (item.get("code") or "").casefold() == code.casefold()]
            if len(exact) == 1:
                return exact[0]
            if len(exact) > 1:
                raise KapError(ENTITY_AMBIGUOUS, "Kod birden çok varlıkla eşleşti.", context={"candidates": [item.model_dump(mode="json") for item in exact]})
            raise KapError(ENTITY_NOT_FOUND, "Varlık bulunamadı.", context={"code": code})
        results = await self.adapter.smart_search(entity_id or "")
        matches = [item for item in results if str(item.get("memberOrFundOid")) == entity_id]
        if len(matches) != 1:
            raise KapError(ENTITY_NOT_FOUND if not matches else ENTITY_AMBIGUOUS, "Varlık kimliği kesin çözümlenemedi.", context={"entity_id": entity_id})
        item = matches[0]
        raw_code = item.get("cmpOrFundCode")
        return Entity(code=raw_code.upper() if raw_code else None, entity_id=entity_id or "", name=item.get("searchValue", ""), entity_type="company" if item.get("searchType") == "C" else "fund")

    async def get_entity(self, code: str | None, entity_id: str | None, sections: list[str]) -> dict[str, Any]:
        allowed = {"summary", "contact", "management", "capital", "shareholders", "markets", "indices", "fund_details"}
        if not sections or set(sections) - allowed:
            raise KapError(VALIDATION_ERROR, "Geçersiz veya boş sections listesi.")
        entity = await self.resolve_entity(code, entity_id)
        result: dict[str, Any] = {"entity": entity.model_dump(mode="json"), "sections": {}}
        if "summary" in sections:
            result["sections"]["summary"] = entity.model_dump(mode="json")
        if entity.entity_type != "company" and entity.code and "fund_details" in sections:
            fund = await self.adapter.find_fund_by_code(entity.code)
            if fund:
                result["sections"]["fund_details"] = fund
        unsupported = [section for section in sections if section not in result["sections"]]
        if unsupported:
            result["unavailable_sections"] = unsupported
            result["warnings"] = ["KAP'ın doğrulanmış kamu sözleşmesi bu profil bölümlerini sağlamıyor."]
        return result

    async def query_disclosures(
        self, entity_codes: list[str], entity_types: list[str], report_types: list[str], subjects: list[str],
        from_date: str | None, to_date: str | None, year: int | None, month: int | None, period: int | None,
        latest: bool, latest_revision_only: bool, has_attachments: bool | None, include_files: bool,
        limit: int, cursor: str | None,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise KapError(VALIDATION_ERROR, "limit 1-100 arasında olmalıdır.")
        start, end = _date_range(from_date, to_date, year, month, latest)
        entities = [await self.resolve_entity(code=code) for code in dict.fromkeys(entity_codes)]
        if not entities and not latest:
            raise KapError(VALIDATION_ERROR, "Geniş sorguyu engellemek için entity_codes veya latest=true gereklidir.")
        if not entities:
            raw = await self.adapter.latest_disclosures()
            normalized = [self._normalize_disclosure(item, None) for item in raw]
        else:
            normalized: list[Disclosure] = []
            for entity in entities:
                if entity.entity_type == "company":
                    raw = await self.adapter.member_disclosures(self._member_payload(entity.entity_id, start, end, year, period))
                else:
                    raw = await self.adapter.fund_disclosures(self._fund_payload(entity.entity_id, start, end, entity.upstream_type))
                normalized.extend(self._normalize_disclosure(item, entity) for item in raw)
        items = [item for item in normalized if (not report_types or item.report_type in report_types) and (not subjects or any(subject.casefold() in item.subject.casefold() for subject in subjects))]
        if month is not None:
            items = [item for item in items if item.month == month or item.period == month]
        if period is not None:
            items = [item for item in items if str(item.period) == str(period)]
        if has_attachments is not None:
            items = [item for item in items if (item.attachment_count > 0) == has_attachments]
        items.sort(key=lambda item: item.disclosure_index, reverse=True)
        if latest_revision_only:
            deduplicated: dict[tuple[Any, ...], Disclosure] = {}
            for item in items:
                key = (item.entity_code, item.report_type, item.subject, item.year, item.month or item.period)
                deduplicated.setdefault(key, item)
            items = list(deduplicated.values())
        offset = _cursor_offset(cursor)
        selected = items[offset: offset + limit]
        if include_files:
            for item in selected:
                item.files = (await self._attachment_metadata(item.disclosure_index))["items"]
        next_cursor = None
        if offset + limit < len(items):
            next_cursor = base64.urlsafe_b64encode(str(offset + limit).encode()).decode().rstrip("=")
        return {"items": [item.model_dump(mode="json") for item in selected], "next_cursor": next_cursor}

    @staticmethod
    def _member_payload(oid: str, start: date, end: date, year: int | None, period: int | None) -> dict[str, Any]:
        return {"fromDate": str(start), "toDate": str(end), "memberType": "", "mkkMemberOidList": [oid], "inactiveMkkMemberOidList": [], "disclosureClass": "", "subjectList": [], "isLate": "", "mainSector": "", "sector": "", "subSector": "", "marketOid": "", "index": "", "bdkReview": "", "bdkMemberOidList": [], "year": year or "", "term": "", "ruleType": "", "period": period or "", "fromSrc": False, "srcCategory": "", "disclosureIndexList": []}

    @staticmethod
    def _fund_payload(oid: str, start: date, end: date, fund_type: str | None) -> dict[str, Any]:
        return {"fromDate": str(start), "toDate": str(end), "fundTypeList": [fund_type or "YF"], "mkkMemberOidList": [], "fundOidList": [oid], "passiveFundOidList": [], "disclosureClass": "", "isLate": "", "subjectList": [], "discIndex": [], "fromSrc": False, "srcCategory": ""}

    @staticmethod
    def _normalize_disclosure(item: dict[str, Any], entity: Entity | None) -> Disclosure:
        entity_type = entity.entity_type if entity else ("fund" if item.get("fundCode") else "company")
        raw_code = entity.code if entity else item.get("fundCode") or item.get("stockCodes")
        code = raw_code.upper() if raw_code else None
        subject = item.get("subject") or item.get("title") or ""
        month = item.get("period") if entity_type != "company" and isinstance(item.get("period"), int) else None
        return Disclosure(
            disclosure_index=int(item.get("disclosureIndex")), entity_code=code, entity_type=entity_type,
            entity_name=item.get("kapTitle") or item.get("title") or (entity.name if entity else ""),
            publish_datetime=_iso_datetime(item.get("publishDate", "")), report_type=_report_type(subject, item.get("disclosureType", ""), entity_type),
            subject=subject, summary=item.get("summary"), year=item.get("year"), month=month,
            period=item.get("period"), attachment_count=int(item.get("attachmentCount") or 0),
            modify_status=item.get("modifyStatus"), disclosure_url=f"https://kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}",
        )

    async def get_disclosure(self, disclosure_index: int, content_format: str, include_attachments: bool, include_revision_chain: bool) -> dict[str, Any]:
        if content_format not in {"structured", "text", "html"}:
            raise KapError(VALIDATION_ERROR, "content_format structured, text veya html olmalıdır.")
        rows = await self.adapter.disclosure_detail(disclosure_index)
        if not rows:
            raise KapError(DISCLOSURE_NOT_FOUND, "Bildirim bulunamadı.", context={"disclosure_index": disclosure_index})
        row = rows[0]
        disclosure = row.get("disclosure", {})
        basic = disclosure.get("disclosureBasic", {})
        bodies = row.get("disclosureBody") or []
        result = {"disclosure_index": disclosure_index, "metadata": basic, "detail": disclosure.get("disclosureDetail") or {}}
        if content_format == "html":
            result["content"] = "\n".join(bodies)
        elif content_format == "text":
            result["content"] = _html_to_text(bodies)
        else:
            result["content"] = {"text": _html_to_text(bodies), "fields": disclosure.get("disclosureDetail") or {}}
        if include_attachments:
            result["attachments"] = self._attachments_from_row(row, disclosure_index)
        if include_revision_chain:
            result["revision_chain"] = self._revision_chain(basic, disclosure.get("disclosureDetail") or {})
        return result

    @staticmethod
    def _revision_chain(basic: dict[str, Any], detail: dict[str, Any]) -> list[dict[str, Any]]:
        related = basic.get("relatedDisclosureOid") or detail.get("relatedDisclosureOid")
        return [{"disclosure_index": basic.get("disclosureIndex"), "status": basic.get("isChanged"), "related_disclosure_id": related}]

    @staticmethod
    def _attachments_from_row(row: dict[str, Any], disclosure_index: int) -> list[dict[str, Any]]:
        result = []
        for attachment in row.get("attachments") or []:
            object_id = attachment.get("objId")
            name = attachment.get("fileName") or f"{object_id}.{attachment.get('fileExtension', 'bin')}"
            result.append({"file_name": name, "attachment_id": object_id, "mime_type": mime_for_name(name), "url": f"https://kap.org.tr/tr/api/file/download/{object_id}", "disclosure_index": disclosure_index})
        return result

    async def _attachment_metadata(self, disclosure_index: int) -> dict[str, Any]:
        rows = await self.adapter.disclosure_detail(disclosure_index)
        if not rows:
            raise KapError(DISCLOSURE_NOT_FOUND, "Bildirim bulunamadı.")
        return {"items": self._attachments_from_row(rows[0], disclosure_index)}

    async def get_disclosure_file(self, disclosure_index: int, file_selector: str, attachment_id: str | None, action: str) -> dict[str, Any]:
        if file_selector not in {"primary_attachment", "rendered_disclosure_pdf", "first_pdf", "first_excel", "all"} or action not in {"link", "metadata", "content"}:
            raise KapError(VALIDATION_ERROR, "Geçersiz file_selector veya action.")
        metadata = (await self._attachment_metadata(disclosure_index))["items"]
        if file_selector == "rendered_disclosure_pdf":
            selected = [{"file_name": f"bildirim-{disclosure_index}.pdf", "attachment_id": None, "mime_type": "application/pdf", "url": f"https://kap.org.tr/tr/api/BildirimPdf/{disclosure_index}", "disclosure_index": disclosure_index}]
        elif attachment_id:
            selected = [item for item in metadata if item["attachment_id"] == attachment_id]
        elif file_selector == "all":
            selected = metadata
        elif file_selector == "first_pdf":
            selected = [item for item in metadata if item["file_name"].lower().endswith(".pdf")][:1]
        elif file_selector == "first_excel":
            selected = [item for item in metadata if item["file_name"].lower().endswith((".xls", ".xlsx"))][:1]
        else:
            selected = metadata[:1]
        if not selected:
            raise KapError(ATTACHMENT_NOT_FOUND, "İstenen bildirim dosyası bulunamadı.")
        if action == "content":
            for item in selected:
                raw, content_type, _ = await (self.adapter.attachment(item["attachment_id"]) if item["attachment_id"] else self.adapter.rendered_pdf(disclosure_index))
                verified = verify_file(raw, content_type)
                item.update({"mime_type": verified.mime_type, "size_bytes": len(verified.content), "sha256": verified.sha256, "content_base64": verified.as_content(), "wrapper_bytes_removed": verified.wrapper_bytes_removed})
        return {"items": selected} if file_selector == "all" else selected[0]

    async def download_file(self, attachment_id: str | None, disclosure_index: int | None, file_selector: str, output_directory: str | None, output_name: str | None, overwrite: bool) -> dict[str, Any]:
        if attachment_id:
            raw, content_type, source_url = await self.adapter.attachment(attachment_id)
            name = output_name or f"{attachment_id}"
        elif disclosure_index:
            file = await self.get_disclosure_file(disclosure_index, file_selector, None, "link")
            raw, content_type, source_url = await (self.adapter.attachment(file["attachment_id"]) if file.get("attachment_id") else self.adapter.rendered_pdf(disclosure_index))
            name = output_name or file["file_name"]
        else:
            raise KapError(VALIDATION_ERROR, "attachment_id veya disclosure_index gereklidir.")
        verified = verify_file(raw, content_type)
        if not PathLikeSuffix.has(name):
            name += verified.extension
        path = self.file_store.save(verified, directory=output_directory, name=name, overwrite=overwrite)
        return {"status": "downloaded", "saved_path": str(path), "mime_type": verified.mime_type, "size_bytes": len(verified.content), "sha256": verified.sha256, "source_url": source_url, "wrapper_bytes_removed": verified.wrapper_bytes_removed}

    async def get_financials(self, company_code: str, periods: list[dict[str, Any]], statement_types: list[str], mode: str, consolidation: str, include_ratios: bool) -> dict[str, Any]:
        if mode not in {"full", "summary", "raw"} or consolidation not in {"prefer_consolidated", "consolidated", "unconsolidated"}:
            raise KapError(VALIDATION_ERROR, "Geçersiz mode veya consolidation.")
        validated = [Period.model_validate(item) for item in periods]
        entity = await self.resolve_entity(code=company_code)
        if entity.entity_type != "company":
            raise KapError(VALIDATION_ERROR, "get_financials yalnızca şirket kodu kabul eder.")
        code = (entity.code or company_code).upper()
        format_name = "BDDK" if code in _BANK_CODES else "insurance" if code in _INSURANCE_CODES else "IFRS"
        results = []
        for period in validated:
            if period.period is None:
                raise KapError(VALIDATION_ERROR, "Finansallar için period 1-4 gereklidir.")
            filings = await self.adapter.financial_filings(entity.entity_id, period.year, period.period)
            raw, content_type, source_url = await self.adapter.financial_package(entity.entity_id, period.year, period.period)
            verified = verify_file(raw, content_type, max_bytes=100_000_000)
            if mode == "raw":
                document_format = verified.extension.lstrip(".")
                parsed = {"content_base64": verified.as_content(), "mime_type": verified.mime_type}
            else:
                parsed = parse_financial_package(verified.content, statement_types)
                document_format = parsed.pop("format")
                if mode == "summary":
                    for table in parsed["statements"].values():
                        table["rows"] = table["rows"][:80]
            results.append({"period": period.model_dump(exclude_none=True), "format": format_name, "document_format": document_format, "consolidation": consolidation, "filings": filings, "source_url": source_url, "sha256": verified.sha256, **parsed})
        return {"company": entity.model_dump(mode="json"), "periods": results, "ratios": {} if include_ratios else None, "warnings": ["Oranlar çalışma kitabındaki standardize kalemler güvenle eşlenemediği için boş döndürüldü."] if include_ratios else []}

    async def get_fund_portfolio(self, fund_code: str, periods: list[dict[str, Any]] | None, year: int | None, month: int | None, latest: bool, include_positions: bool, include_totals: bool) -> dict[str, Any]:
        requested = [Period.model_validate(item) for item in periods] if periods else []
        if year is not None or month is not None:
            if year is None or month is None:
                raise KapError(VALIDATION_ERROR, "year ve month birlikte verilmelidir.")
            requested.append(Period(year=year, month=month))
        if not requested and not latest:
            raise KapError(VALIDATION_ERROR, "periods, year/month veya latest=true gereklidir.")
        entity = await self.resolve_entity(code=fund_code)
        if entity.entity_type == "company":
            raise KapError(VALIDATION_ERROR, "Fon kodu gereklidir.")
        if latest:
            query = await self.query_disclosures([fund_code], [], ["portfolio_allocation_report"], [], None, None, None, None, None, True, True, True, False, 1, None)
            if not query["items"]:
                raise KapError(DISCLOSURE_NOT_FOUND, "Fon portföy bildirimi bulunamadı.")
            latest_item = query["items"][0]
            requested = [Period(year=latest_item["year"], month=latest_item["month"] or latest_item["period"])]
        results = []
        for requested_period in requested:
            query = await self.query_disclosures([fund_code], [], ["portfolio_allocation_report"], [], None, None, requested_period.year, requested_period.month, None, False, True, True, False, 10, None)
            if not query["items"]:
                raise KapError(DISCLOSURE_NOT_FOUND, "İstenen dönemin portföy bildirimi bulunamadı.", context=requested_period.model_dump(exclude_none=True))
            disclosure = query["items"][0]
            file = await self.get_disclosure_file(disclosure["disclosure_index"], "first_pdf", None, "link")
            raw, content_type, source_url = await self.adapter.attachment(file["attachment_id"])
            verified = verify_file(raw, content_type)
            positions, totals, portfolio_total, validation = parse_fund_portfolio(verified.content)
            result = {"fund": entity.model_dump(mode="json"), "period": requested_period.model_dump(exclude_none=True), "disclosure": disclosure, "source_file": {**file, "url": source_url, "size_bytes": len(verified.content), "sha256": verified.sha256, "wrapper_bytes_removed": verified.wrapper_bytes_removed}, "validation": validation.model_dump(mode="json")}
            if include_positions:
                result["positions"] = [item.model_dump(mode="json") for item in positions]
            if include_totals:
                result["group_totals"] = totals
                result["portfolio_total"] = portfolio_total
            results.append(result)
        return results[0] if len(results) == 1 else {"items": results}

    async def get_expected_disclosures(self, entity_codes: list[str], from_date: str, to_date: str) -> dict[str, Any]:
        start, end = _date_range(from_date, to_date, None, None, False)
        if not entity_codes:
            raise KapError(VALIDATION_ERROR, "entity_codes boş olamaz.")
        entities = [await self.resolve_entity(code=code) for code in entity_codes]
        company_ids = [entity.entity_id for entity in entities if entity.entity_type == "company"]
        fund_ids = [entity.entity_id for entity in entities if entity.entity_type != "company"]
        items = []
        if company_ids:
            items.extend(await self.adapter.expected_company({"mkkMemberOidList": company_ids, "fromDate": str(start), "toDate": str(end)}))
        if fund_ids:
            items.extend(await self.adapter.expected_fund({"fundOidList": fund_ids, "fromDate": str(start), "toDate": str(end)}))
        return {"items": items}

    async def get_corporate_actions(self, company_codes: list[str], action_types: list[str], from_date: str | None, to_date: str | None, latest: bool) -> dict[str, Any]:
        start, end = _date_range(from_date, to_date, None, None, latest)
        wanted = {code.upper() for code in company_codes}
        raw_items = []
        if action_types:
            for action in action_types:
                response = await self.adapter.corporate_actions(start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y"), action)
                raw_items.extend(response if isinstance(response, list) else response.get("items", []))
        else:
            response = await self.adapter.corporate_actions(start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y"))
            raw_items = response if isinstance(response, list) else response.get("items", [])
        if wanted:
            raw_items = [item for item in raw_items if str(item.get("stockCode") or item.get("companyCode") or "").upper() in wanted]
        return {"items": raw_items}


class PathLikeSuffix:
    @staticmethod
    def has(name: str) -> bool:
        return bool(re.search(r"\.[A-Za-z0-9]{1,8}$", name))
