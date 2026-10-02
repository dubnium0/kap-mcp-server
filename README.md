# KAP MCP Server

### Kurulum Agents için prompt

```text
Aşağıdaki kaynaktaki KAP MCP sunucusunu kullandığım agente kur:
https://github.com/dubnium0/kap-mcp-server.git

Yalnızca kurulum ve bağlantı doğrulaması yap:
1. İçinde çalıştığın MCP istemcisini mevcut süreç, komutlar ve yapılandırma
   dosyalarından belirle. Desteklenen istemciler Claude Code, Codex ve Hermes
   Agent'tır. İstemciyi güvenilir biçimde belirleyemiyorsan yalnızca hangisini
   kullandığımı sor; birden fazla istemciyi yapılandırma.
2. Repo bilgisayarda zaten varsa ve geçerli bir git checkout ise onu güvenle
   yeniden kullan. Yoksa kullanıcıya ait kalıcı bir kurulum dizinine klonla.
   Mevcut, ilişkisiz bir dizinin üzerine yazma ve repo adresini değiştirme.
3. Checkout kökünü mutlak yola çevir ve KAP_MCP_DIR olarak kullan. Bu dizinde
   `pyproject.toml` bulunduğunu ve proje adının `kap-mcp` olduğunu doğrula.
4. Python 3.12+, uv ve git ön koşullarını kontrol et. uv eksikse işletim sistemine
   uygun resmî uv kurulum yöntemini kullan. Python 3.12+ eksikse
   `uv python install 3.12` kullan. Ardından KAP_MCP_DIR içinde `uv sync`
   çalıştır.
5. Seçilen istemcide daha önce tanımlanmış `kap` MCP kaydını kontrol et. Aynı
   kurulumu gösteren doğru kayıt varsa ikinci kayıt oluşturma; eski veya yanlış
   kaydı güvenli biçimde güncelle.
6. Bağlantı sonrasında tool listesinin tam olarak şu 10 tool'u içerdiğini doğrula:
   search_entities, get_entity, query_disclosures, get_disclosure,
   get_disclosure_file, download_file, get_financials, get_fund_portfolio,
   get_corporate_actions, get_expected_disclosures.

Klonlanan kaynak kodunu, testleri, README'yi, API belgelerini veya tool
sözleşmelerini değiştirme. Canlı KAP sorgusu çalıştırma ve dosya indirme.
Sonunda algılanan istemciyi, kurulum dizinini, kullanılan yapılandırma dosyasını,
çalıştırma komutunu ve doğrulanan tool sayısını kısaca bildir.

Resmî istemci belgeleri:
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Codex MCP](https://developers.openai.com/codex/mcp)
- [Hermes Agent MCP](https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference)

```

## Tool'lar
1. `search_entities` — şirket/fon/üye araması; akıllı arama farklı kod döndürürse fon kataloğunda büyük/küçük harf duyarsız kesin kod eşleşmesine geri düşer.
2. `get_entity` — kesin varlık profili ve doğrulanmış bölümler.
3. `query_disclosures` — şirket ve fon bildirimlerinin kısa, sayfalı listesi.
4. `get_disclosure` — tek bildirimin tam gövdesi, ekleri ve revizyon metadata bilgisi.
5. `get_disclosure_file` — dosya bağlantısı, metadata veya base64 içerik; diske yazmaz.
6. `download_file` — izin verilen köke doğrulanmış dosya indirir.
7. `get_financials` — IFRS/BDDK/sigorta metadata bilgili finansal tablolar.
8. `get_fund_portfolio` — portföy PDF'sini bulur, doğrular, pozisyon ve toplamları ayrıştırır.
9. `get_corporate_actions` — kurumsal işlem sorgusu.
10. `get_expected_disclosures` — ileri tarihli bildirim takvimi.

## [Örnek Senaryo](https://github.com/dubnium0/kap-mcp-server/blob/main/validation_test.md): Portföy PDF’sini yapılandırılmış veriye dönüştürme
- **Kategori Türü:** Sabit tarihsel | **Zorluk Seviyesi:** Zor
- **Çalışma Süresi:** 156.62 saniye | **Diyalog Adımı:** 2 tur

**1. Kullanıcı Sorgusu (User Query):**
> "AFT’nin Ağustos 2026 portföy dağılım raporunu ayrıştır. Tüm pozisyonları, varlık grubu toplamlarını ve fon portföy değerini getir."

**2. Modelin Tetiklediği Araç Çağrısı (Tool Call) ve Parametreleri:**
```json
[
  {
    "adim": 1,
    "arac": "get_fund_portfolio",
    "argumanlar": {
      "fund_code": "AFT",
      "include_positions": true,
      "include_totals": true,
      "month": 8,
      "year": 2026
    }
  }
]
```

**3. KAP MCP Sunucusundan Dönen Canlı Veri (Tool Response Snippet):**
```json
// [Adım 1] Araç: get_fund_portfolio
{
  "fund": {
    "code": "AFT",
    "entity_id": "33E5FED7E77300EAE0530A4A622B2AEA",
    "name": "AK PORTFÖY YENİ TEKNOLOJİLER YABANCI HİSSE SENEDİ FONU",
    "entity_type": "fund",
    "active": true,
    "permalink": null,
    "portfolio_company_id": null,
    "portfolio_company": null,
    "upst

```

**4. Modelin Kullanıcıya Verdiği Nihai Yanıt (GLM-5.3 Assistant Response):**

### AFT – Ağustos 2026 Portföy Dağılım Raporu

**Fon:** AK PORTFÖY YENİ TEKNOLOJİLER YABANCI HİSSE SENEDİ FONU (AFT)
**Dönem:** Ağustos 2026 (Aylık Rapor)
**Bildirim:** [1657446](https://kap.org.tr/tr/Bildirim/1657446) – Yayın: 02.09.2026 17:53 | Kaynak dosya: `AFT_2026.08.pdf`
**Doğrulama:** Hesaplanan toplam, bildirilen toplamla birebir tutuyor (fark: 0,00 TL) ✅

### Fon Portföy Değeri ve Varlık Grubu Toplamları

| Varlık Grubu | Değer (TL) | Portföy Payı |
|---|---:|---:|
| Yabancı Hisse Senetleri | 18.945.983.849,02 | %98,46 |
| Ters Repo | 2.002.025,20 | %0,01 |
| Para Piyasası | 380.400,82 | %0,00 |
| Diğer | 292.777.771,32 | %1,52 |
| **Fon Portföy Değeri** | **19.241.144.046,36** | %100,00 |
| Döviz (hazır değer) | 4.304.735,44 | *Portföy değerinin dışında* |

> Not: Döviz hazır değerleri (4.304.735,44 TL) pozisyonlarda gösterilmiş ancak bildirilen fon portföy değerinin **dışında** tutulmuştur.

### Hisse Senedi Pozisyonları (28 adet, USD bazlı)

| Menkul Kıymet | Nominal | Fiyat (USD) | Değer (TL) | % Fon |
|---|---:|---:|---:|---:|
| MSFT US | 78.366 | 509,31 | 1.922.768.944,59 | 10,03 |
| NVDA US | 172.863 | 218,85 | 1.822.492.763,69 | 9,51 |
| MU US | 38.784 | 940,86 | 1.757.902.643,35 | 9,17 |
| GOOGL US | 75.786 | 340,30 | 1.242.419.189,18 | 6,48 |
| AMZN US | 87.355 | 261,61 | 1.100.929.032,70 | 5,74 |
| SMSN LI | 4.385 | 4.698,33 | 992.499.578,30 | 5,18 |
| SKHY US | 125.796 | 163,27 | 989.442.225,56 | 5,16 |
| BABA US | 159.621 | 115,76 | 890.155.257,43 | 4,64 |
| AVGO US | 46.535 | 368,97 | 827.157.077,91 | 4,31 |
| TSM US | 38.060 | 420,88 | 771.692.516,29 | 4,03 |
| NOW US | 82.285 | 145,00 | 574.785.616,21 | 3,00 |
| WDC US | 25.787 | 453,52 | 563.396.935,10 | 2,94 |
| AMD US | 23.739 | 469,78 | 537.247.198,90 | 2,80 |
| META US | 17.555 | 573,07 | 484.647.217,35 | 2,53 |
| SNDK US | 6.367 | 1.517,17 | 465.357.065,55 | 2,43 |
| INTC US | 103.255 | 90,40 | 449.672.922,97 | 2,35 |
| STX US | 8.970 | 821,07 | 354.805.091,33 | 1,85 |
| AMGN US | 17.050 | 429,37 | 352.673.880,36 | 1,84 |
| LRCX US | 23.300 | 300,90 | 337.749.974,27 | 1,76 |
| BIDU US | 72.403 | 97,21 | 339.066.372,83 | 1,77 |
| KLAC US | 34.705 | 175,70 | 293.752.131,15 | 1,53 |
| CRM US | 24.122 | 257,84 | 299.626.914,12 | 1,56 |
| CRWV US | 157.009 | 83,12 | 628.705.555,46 | 3,28 |
| AMAT US | 9.760 | 460,41 | 216.477.010,28 | 1,13 |
| ASML US | 2.356 | 1.700,63 | 193.020.011,85 | 1,01 |
| ADI US | 10.919 | 365,13 | 192.064.720,67 | 1,00 |
| TXN US | 13.923 | 261,31 | 175.269.387,48 | 0,91 |
| MRVL US | 16.582 | 213,07 | 170.206.614,14 | 0,89 |

### Diğer Pozisyonlar

**Ters Repo (toplam 2.002.025,20 TL):**

| Menkul Kıymet | Nominal | Değer (TL) |
|---|---:|---:|
| TRT181028T14 | 81.919.363 | 1.001.012,60 |
| TRT181028T14 | 81.919.363 | 1.001.012,60 |

**Para Piyasası (toplam 380.400,82 TL):**

| Menkul Kıymet | Nominal | Değer (TL) |
|---|---:|---:|
| TPP | 247.453 | 380.400,82 |

**Diğer (toplam 292.777.771,32 TL):**

| Menkul Kıymet | Nominal | Fiyat (TL) | Değer (TL) |
|---|---:|---:|---:|
| ALE | 20.454.549 | 13,651342 | 279.232.043,85 |
| EML-AK | 6.163.404 | 1,267356 | 7.811.227,04 |
| PUR | 543.468 | 10,551680 | 5.734.500,43 |

**Döviz (portföy değeri dışında, toplam 4.304.735,44 TL):**

| Döviz | Tutar | Kur (TL) | Değer (TL) |
|---|---:|---:|---:|
| USD | 86.630,96 | 48,1745 | 4.173.403,18 |
| EUR | 2.350,26 | 55,8652 | 131.297,74 |
| GBP | 0,53 | 65,1261 | 34,52 |

### Öne Çıkanlar

- **En büyük 3 pozisyon:** MSFT (%10,03), NVDA (%9,51) ve MU (%9,17) — birlikte fonun yaklaşık %28,7'sini oluşturuyor.
- Fon, adına uygun şekilde **%98,5'e yakın** oranda ABD merkezli yabancı teknoloji hisselerine yatırım yapmış durumda.
- Nakit benzeri varlıklar (ters repo + para piyasası) çok küçük bir pay tutuyor (~%0,01).


## Hatalar

Tool hataları şu yapıdadır:

```json
{"ok":false,"error":{"code":"entity_not_found","message":"Varlık bulunamadı.","retryable":false,"context":{}}}
```

Kodlar: `validation_error`, `entity_not_found`, `entity_ambiguous`, `disclosure_not_found`, `attachment_not_found`, `upstream_changed`, `upstream_unavailable`, `unsupported_document`, `parse_failed`, `validation_failed`, `unsafe_path`, `file_exists`.
