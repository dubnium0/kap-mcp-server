# KAP MCP

KAP'ın kamuya açık web uç noktalarını 10 görev odaklı MCP tool'una normalize eden Python 3.12+ stdio sunucusu.

> KAP uç noktaları resmî, sürümlenmiş bir kamu API'si değildir. KAP web istemcisinden tersine çıkarılmıştır ve bildirim yapılmadan değişebilir. Son doğrulama: **30 Eylül 2026**. `upstream_changed` hatası bu sözleşmenin değişmiş olabileceğini belirtir.


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

## Örnek call

```json
{
  "user": "AFT Fonu güncel portföy bilgisi",
  "tool_calls": [
    {
      "name": "get_fund_portfolio",
      "arguments": {
        "fund_code": "AFT",
        "latest": true,
        "include_positions": false,
        "include_totals": true
      },
      "duration_seconds": 1.662
    }
  ],
  "response_time_seconds": 3.45,
  "assistant": "AFT'nin en güncel portföy dağılım raporu Ağustos 2026 dönemine ait. Fonun toplam portföy değeri 19.241.144.046,36 TL. Bunun 18.945.983.849,02 TL'si hisse senetleri, 292.777.771,32 TL'si diğer varlıklar, 4.304.735,44 TL'si döviz, 2.002.025,20 TL'si ters repo ve 380.400,82 TL'si para piyasası işlemlerinden oluşuyor. Hesaplanan toplam ile raporlanan toplam birebir eşleşiyor. Rapor 2 Eylül 2026'da yayımlanmış: https://kap.org.tr/tr/Bildirim/1657446"
}
```

## Hatalar

Tool hataları şu yapıdadır:

```json
{"ok":false,"error":{"code":"entity_not_found","message":"Varlık bulunamadı.","retryable":false,"context":{}}}
```

Kodlar: `validation_error`, `entity_not_found`, `entity_ambiguous`, `disclosure_not_found`, `attachment_not_found`, `upstream_changed`, `upstream_unavailable`, `unsupported_document`, `parse_failed`, `validation_failed`, `unsafe_path`, `file_exists`.
