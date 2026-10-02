from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from pypdf import PdfReader

from .errors import PARSE_FAILED, UNSUPPORTED_DOCUMENT, KapError
from .models import PortfolioPosition, ValidationResult


_TR_NUMBER = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")
_ROW_END = re.compile(
    r"(?P<total>-?\d[\d.]*,\d{2})\s+(?P<group>-?\d+[,.]\d+)\s+(?P<portfolio>-?\d+[,.]\d+)\s+(?P<fund>-?\d+[,.]\d+)\s*$"
)


def tr_decimal(value: str) -> Decimal:
    cleaned = value.strip().replace("%", "").replace(" ", "")
    if not _TR_NUMBER.match(cleaned):
        raise ValueError(f"Geçersiz Türkçe sayı: {value!r}")
    return Decimal(cleaned.replace(".", "").replace(",", "."))


def _pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
    except Exception as exc:
        raise KapError(PARSE_FAILED, "PDF metni çıkarılamadı.", context={"cause": type(exc).__name__}) from exc


def parse_fund_portfolio(content: bytes) -> tuple[list[PortfolioPosition], dict[str, Decimal], Decimal, ValidationResult]:
    text = _pdf_text(content)
    start = text.find("III-FON PORTFÖY DEĞERİ TABLOSU")
    end = text.find("IV-FON TOPLAM DEĞERİ TABLOSU", start)
    if start < 0 or end < 0:
        raise KapError(PARSE_FAILED, "Fon portföy tablosu PDF içinde bulunamadı.")
    table = text[start:end]
    portfolio_match = re.search(r"FON PORTFÖY DEĞERİ\s+([\d.]+,\d{2})", table)
    if not portfolio_match:
        raise KapError(PARSE_FAILED, "Bildirilen fon portföy değeri bulunamadı.")
    reported_total = tr_decimal(portfolio_match.group(1))

    group = "other"
    positions: list[PortfolioPosition] = []
    warnings: list[str] = []
    group_totals: dict[str, Decimal] = {}
    heading_map = {
        "HİSSE SENETLERİ": "equities",
        "T.REPO": "reverse_repo",
        "TPP": "money_market",
        "DİĞER": "other",
        "Döviz": "currency",
        "DÖVİZ": "currency",
    }
    for raw_line in table.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if line in heading_map:
            group = heading_map[line]
            continue
        if line.startswith("GRUP TOPLAMI"):
            numbers = re.findall(r"-?\d[\d.]*,\d+", line)
            if len(numbers) >= 2:
                try:
                    group_totals[group] = tr_decimal(numbers[-4] if len(numbers) >= 4 else numbers[-1])
                except ValueError:
                    pass
            continue
        match = _ROW_END.search(line)
        if not match or line.startswith(("FON PORTFÖY", "TOPLAM", "MENKUL", "VADEYE")):
            continue
        prefix = line[: match.start()].strip()
        tokens = prefix.split()
        if not tokens:
            continue
        security = " ".join(tokens[:2]) if len(tokens) > 1 and tokens[1] in {"US", "LI"} else tokens[0]
        currency = next((token for token in tokens[1:5] if token in {"TL", "USD", "EUR", "GBP"}), None)
        isin = next((token for token in tokens if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", token)), None)
        numeric = [token for token in tokens if _TR_NUMBER.match(token)]
        nominal = None
        daily = None
        try:
            if numeric:
                nominal = tr_decimal(numeric[-3] if len(numeric) >= 3 else numeric[0])
                daily = tr_decimal(numeric[-1])
            total = tr_decimal(match.group("total"))
            positions.append(PortfolioPosition(
                group=group,
                security=security,
                currency=currency,
                isin=isin,
                nominal_value=nominal,
                daily_value=daily,
                total_value=total,
                group_percent=tr_decimal(match.group("group")),
                portfolio_percent=tr_decimal(match.group("portfolio")),
                fund_total_percent=tr_decimal(match.group("fund")),
            ))
        except (ValueError, InvalidOperation):
            warnings.append(f"Satır ayrıştırılamadı: {line[:120]}")

    if not positions:
        raise KapError(PARSE_FAILED, "Portföy tablosunda yapılandırılabilir pozisyon bulunamadı.")
    excluded_groups = {"currency"}
    calculated = sum(
        (position.total_value for position in positions if position.group not in excluded_groups),
        Decimal(0),
    )
    if any(position.group == "currency" for position in positions):
        warnings.append("Döviz hazır değerleri pozisyonlarda gösterildi; bildirilen fon portföy değerinin dışında tutuldu.")
    difference = reported_total - calculated
    tolerance = max(Decimal("0.05"), reported_total * Decimal("0.000001"))
    validation = ValidationResult(
        calculated_total=calculated,
        reported_total=reported_total,
        difference=difference,
        valid=abs(difference) <= tolerance,
        warnings=warnings,
    )
    # Position-derived totals are deterministic; reported group rows remain metadata.
    derived: dict[str, Decimal] = defaultdict(Decimal)
    for position in positions:
        derived[position.group] += position.total_value
    return positions, dict(derived), reported_total, validation


def parse_financial_package(content: bytes, statement_types: list[str]) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content)) if content.startswith(b"PK\x03\x04") else None
        candidates = []
        if archive:
            candidates = [(name, archive.read(name)) for name in archive.namelist() if name.lower().endswith((".xls", ".xlsx"))]
        else:
            candidates = [("financial.xls", content)]
        if not candidates:
            raise KapError(UNSUPPORTED_DOCUMENT, "Finansal pakette Excel çalışma kitabı bulunamadı.")
        name, workbook_bytes = candidates[0]
        if workbook_bytes.lstrip().lower().startswith(b"<html"):
            return _parse_html_xls(name, workbook_bytes, statement_types)
        if workbook_bytes.startswith(b"\xd0\xcf\x11\xe0"):
            return _parse_xls(name, workbook_bytes, statement_types)
        if workbook_bytes.startswith(b"PK\x03\x04"):
            return _parse_xlsx(name, workbook_bytes, statement_types)
        raise KapError(UNSUPPORTED_DOCUMENT, "Finansal çalışma kitabı biçimi desteklenmiyor.")
    except KapError:
        raise
    except Exception as exc:
        raise KapError(PARSE_FAILED, "Finansal paket ayrıştırılamadı.", context={"cause": type(exc).__name__}) from exc


def _wanted_sheet(name: str, statement_types: list[str]) -> bool:
    turkish_ascii = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"})
    folded = unicodedata.normalize("NFKD", name.casefold().translate(turkish_ascii)).encode("ascii", "ignore").decode()
    words = {
        "balance_sheet": ("finansal durum", "bilanco", "balance"),
        "income_statement": ("kar veya zarar", "gelir tablos", "income", "profit"),
        "cash_flow": ("nakit akis", "cash flow"),
    }
    return any(any(word in folded for word in words.get(kind, (kind,))) for kind in statement_types)


def _rows_to_table(rows: list[list[Any]]) -> dict[str, Any]:
    normalized = []
    for row in rows:
        values = [value.isoformat() if hasattr(value, "isoformat") else value for value in row]
        if any(value not in (None, "") for value in values):
            normalized.append(values)
    return {"rows": normalized}
def _parse_html_xls(name: str, content: bytes, statement_types: list[str]) -> dict[str, Any]:
    from html.parser import HTMLParser

    class FinancialTableParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.table_depth = 0
            self.in_financial = False
            self.row: list[str] | None = None
            self.cell: list[str] | None = None
            self.current: list[list[str]] = []
            self.tables: list[list[list[str]]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attributes = dict(attrs)
            if tag == "table":
                if self.in_financial:
                    self.table_depth += 1
                elif "financial-table" in (attributes.get("class") or "").split():
                    self.in_financial = True
                    self.table_depth = 1
                    self.current = []
            elif self.in_financial and tag == "tr" and self.table_depth == 1 and self.row is None:
                self.row = []
            elif self.in_financial and tag in {"td", "th"} and self.row is not None and self.cell is None:
                self.cell = []
            elif self.in_financial and tag == "br" and self.cell is not None:
                self.cell.append(" ")

        def handle_endtag(self, tag: str) -> None:
            if not self.in_financial:
                return
            if tag in {"td", "th"} and self.cell is not None:
                self.row.append(" ".join("".join(self.cell).split()))
                self.cell = None
            elif tag == "tr" and self.row is not None and self.table_depth == 1:
                if any(self.row):
                    self.current.append(self.row)
                self.row = None
            elif tag == "table":
                self.table_depth -= 1
                if self.table_depth == 0:
                    self.tables.append(self.current)
                    self.current = []
                    self.in_financial = False

        def handle_data(self, data: str) -> None:
            if self.cell is not None:
                self.cell.append(data)

    parser = FinancialTableParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    statements: dict[str, Any] = {}
    for index, rows in enumerate(parser.tables, 1):
        title = next((cell for cell in rows[0] if _wanted_sheet(cell, statement_types)), None) if rows else None
        if not title and rows and rows[0] and not rows[0][0] and len(rows) > 1:
            title = next((cell for cell in rows[1] if _wanted_sheet(cell, statement_types)), None)
        if title:
            statements[f"{title} [{index}]"] = _rows_to_table(rows)
    if not statements:
        raise KapError(
            UNSUPPORTED_DOCUMENT,
            "İstenen finansal tablo türü HTML çalışma kitabında bulunamadı.",
            context={"table_count": len(parser.tables)},
        )
    return {"source_file": name, "format": "html-xls", "statements": statements}




def _parse_xls(name: str, content: bytes, statement_types: list[str]) -> dict[str, Any]:
    try:
        import xlrd
    except ImportError as exc:
        raise KapError(UNSUPPORTED_DOCUMENT, "Eski XLS finansal tabloları için xlrd kurulu değil.") from exc
    book = xlrd.open_workbook(file_contents=content)
    sheets = {}
    for sheet in book.sheets():
        if _wanted_sheet(sheet.name, statement_types):
            sheets[sheet.name] = _rows_to_table([[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)])
    if not sheets:
        raise KapError(UNSUPPORTED_DOCUMENT, "İstenen finansal tablo türü çalışma kitabında bulunamadı.", context={"available_sheets": book.sheet_names()})
    return {"source_file": name, "format": "xls", "statements": sheets}


def _parse_xlsx(name: str, content: bytes, statement_types: list[str]) -> dict[str, Any]:
    # Modern KAP packages are uncommon; parse workbook XML without adding a generation dependency.
    import xml.etree.ElementTree as ET
    archive = zipfile.ZipFile(io.BytesIO(content))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    shared: list[str] = []
    if "xl/sharedStrings.xml" in archive.namelist():
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(node.itertext()) for node in root.findall("m:si", ns)]
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {node.attrib["Id"]: node.attrib["Target"] for node in rels}
    sheets = {}
    for sheet in workbook.findall("m:sheets/m:sheet", ns):
        sheet_name = sheet.attrib["name"]
        if not _wanted_sheet(sheet_name, statement_types):
            continue
        target = targets[sheet.attrib[f"{{{ns['r']}}}id"]].lstrip("/")
        path = target if target.startswith("xl/") else f"xl/{target}"
        root = ET.fromstring(archive.read(path))
        rows = []
        for row in root.findall("m:sheetData/m:row", ns):
            values = []
            for cell in row.findall("m:c", ns):
                value = cell.findtext("m:v", default="", namespaces=ns)
                values.append(shared[int(value)] if cell.attrib.get("t") == "s" and value else value)
            rows.append(values)
        sheets[sheet_name] = _rows_to_table(rows)
    if not sheets:
        raise KapError(UNSUPPORTED_DOCUMENT, "İstenen finansal tablo türü çalışma kitabında bulunamadı.")
    return {"source_file": name, "format": "xlsx", "statements": sheets}
