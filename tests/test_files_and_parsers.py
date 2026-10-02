from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from kap_mcp.errors import FILE_EXISTS, UNSAFE_PATH, KapError
from kap_mcp.files import SafeFileStore, verify_file
from kap_mcp.parsers import parse_financial_package, tr_decimal


def test_java_wrapper_is_removed_by_signature_not_fixed_offset() -> None:
    pdf = b"%PDF-1.7\nbody"
    wrapped = b"\xac\xed\x00\x05" + (b"variable-prefix" * 3) + pdf
    result = verify_file(wrapped, "application/pdf")
    assert result.content == pdf
    assert result.wrapper_bytes_removed == wrapped.index(b"%PDF-")
    assert result.mime_type == "application/pdf"


def test_unknown_prefix_is_rejected() -> None:
    with pytest.raises(KapError) as raised:
        verify_file(b"untrusted-prefix%PDF-1.7")
    assert raised.value.code == "unsupported_document"


def test_safe_store_blocks_escape_and_overwrite(tmp_path: Path) -> None:
    store = SafeFileStore(tmp_path)
    verified = verify_file(b"%PDF-1.7\nbody")
    path = store.save(verified, directory=None, name="report.pdf")
    assert path.read_bytes().startswith(b"%PDF-")
    nested = store.save(verified, directory=str(tmp_path / "rapor"), name="nested.pdf")
    assert nested == (tmp_path / "rapor" / "nested.pdf").resolve()
    assert nested.read_bytes() == verified.content
    with pytest.raises(KapError) as existing:
        store.save(verified, directory=None, name="report.pdf")
    assert existing.value.code == FILE_EXISTS
    with pytest.raises(KapError) as escape:
        store.save(verified, directory=str(tmp_path.parent), name="escape.pdf")
    assert escape.value.code == UNSAFE_PATH


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("19.241.144.046,36", Decimal("19241144046.36")), ("-76.271.656,01", Decimal("-76271656.01")), ("0,00", Decimal("0.00"))],
)
def test_turkish_decimal_is_lossless(raw: str, expected: Decimal) -> None:
    assert tr_decimal(raw) == expected


def test_html_xls_financial_package_selects_requested_statements() -> None:
    html = b"""<html><body>
    <table class="financial-table"><tr><td>Finansal Durum Tablosu (Bilanco)</td></tr><tr><td>Varliklar</td><td>100</td></tr></table>
    <table class="financial-table"><tr><td>Kar veya Zarar Tablosu</td></tr><tr><td>Hasilat</td><td>20</td></tr></table>
    <table class="financial-table"><tr><td>Nakit Akis Tablosu</td></tr><tr><td>Isletme</td><td>10</td></tr></table>
    <table class="financial-table"><tr><td>Ozkaynak Degisim Tablosu</td></tr><tr><td>Kar veya zarar rezervi</td></tr></table>
    </body></html>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sample.xls", html)
    parsed = parse_financial_package(
        buffer.getvalue(),
        ["balance_sheet", "income_statement", "cash_flow"],
    )
    assert parsed["format"] == "html-xls"
    assert len(parsed["statements"]) == 3
