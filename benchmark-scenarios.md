# KAP MCP Benchmark Senaryoları

Bu belge, KAP verilerinden yararlanmak isteyen gerçek kullanıcıların yapabileceği sorgulardan türetilmiş 20 benchmark senaryosu içerir.

## Benchmark yaklaşımı

Senaryolar iki gruba ayrılır:

- **Sabit tarihsel:** Beklenen bildirim, dosya veya dönem sabittir; regresyon testi için uygundur.
- **Canlı:** `en son`, `bugün` veya `önümüzdeki ay` gibi sorgular çalıştırma anına bağlıdır. Beklenen değer sabitlenmemeli; sonuç KAP verisiyle tutarlı, sıralı ve kaynak bağlantılı olmalıdır.

---

## 1. Kesin fon koduyla varlık arama

**Kullanıcı sorgusu**

> AFT kodlu fonu bul. Fonun tam adını ve KAP kimliğini göster.

**Beklenen akış**

```text
search_entities(query="AFT")
```

**Başarı ölçütleri**

- İlk veya kesin sonuç `AFT` olmalı.
- Varlık türü `fund` olmalı.
- Fon adı ve `entity_id` bulunmalı.
- Fuzzy bir sonuç sessizce seçilmemeli.

**Test türü:** Sabit  
**Zorluk:** Kolay

---

## 2. KAP akıllı araması yanlış sonuç döndürse de kesin fonu bulma

**Kullanıcı sorgusu**

> HDD fonunu bul ve hangi portföy yönetim şirketine bağlı olduğunu söyle.

**Beklenen akış**

```text
search_entities(query="HDD")
→ get_entity(code="HDD", sections=["summary", "fund_details"])
```

**Başarı ölçütleri**

- Sonuç `IDD` değil, kesin olarak `HDD` olmalı.
- Fon adı `AHLATCI PORTFÖY BİRİNCİ DEĞİŞKEN FON` olmalı.
- Portföy şirketi `AHLATCI PORTFÖY YÖNETİMİ A.Ş.` olmalı.
- Fon kataloğundaki kesin kod eşleşmesi kullanılmalı.

**Test türü:** Sabit regresyon  
**Zorluk:** Orta

---

## 3. Şirket profil bilgisi

**Kullanıcı sorgusu**

> THYAO’nun KAP profilini getir. Özet bilgileri, işlem gördüğü pazarları ve dahil olduğu endeksleri göster.

**Beklenen akış**

```text
get_entity(
  code="THYAO",
  sections=["summary", "markets", "indices"]
)
```

**Başarı ölçütleri**

- Kesin şirket kodu `THYAO` olmalı.
- Varlık türü `company` olmalı.
- Desteklenmeyen bölüm varsa uydurma veri yerine `unavailable_sections` veya açık uyarı dönmeli.
- Belirsiz aday sessizce seçilmemeli.

**Test türü:** Canlı sözleşme  
**Zorluk:** Orta

---

## 4. Genel en son bildirimler

**Kullanıcı sorgusu**

> KAP’a gelen en son 10 bildirimi şirket/fon adı, saat, konu ve kısa açıklamayla listele.

**Beklenen akış**

```text
query_disclosures(
  latest=true,
  latest_revision_only=true,
  limit=10
)
```

**Başarı ölçütleri**

- En fazla 10 bildirim dönmeli.
- Bildirimler en yeniden eskiye sıralanmalı.
- Her sonuçta bildirim numarası, yayın zamanı, konu ve KAP bağlantısı bulunmalı.
- Liste sonuçları tam HTML gövdeleriyle şişirilmemeli.
- Fonlar mümkünse şirket olarak yanlış sınıflandırılmamalı.

**Test türü:** Canlı  
**Zorluk:** Kolay

---

## 5. Şirkete ait son bildirimler

**Kullanıcı sorgusu**

> THYAO’nun en son 10 KAP bildirimini getir. Her birinin ne hakkında olduğunu bir cümleyle belirt.

**Beklenen akış**

```text
query_disclosures(
  entity_codes=["THYAO"],
  latest=true,
  latest_revision_only=true,
  limit=10
)
```

**Başarı ölçütleri**

- Sonuçlar yalnızca THYAO’ya ait olmalı.
- En yeniden eskiye sıralanmalı.
- Konu, özet, tarih ve bildirim bağlantısı bulunmalı.
- Aynı revizyon zincirinin geçersiz eski sürümleri tekrarlanmamalı.

**Test türü:** Canlı  
**Zorluk:** Kolay

---

## 6. Belirli rapor türlerini tarihe göre arama

**Kullanıcı sorgusu**

> 2026 Eylül ayında yayımlanan sermaye artırımı bildirimlerini getir. Şirket, tarih ve bildirim bağlantısını listele.

**Beklenen akış**

```text
query_disclosures(
  report_types=["capital_increase"],
  from_date="2026-09-01",
  to_date="2026-09-30",
  latest_revision_only=true
)
```

**Başarı ölçütleri**

- Sonuçlar belirtilen tarih aralığında olmalı.
- Normalize rapor türü `capital_increase` olmalı.
- Geniş sorgu güvenli limit altında tutulmalı.
- Sonuç bulunmaması hata değil boş liste olabilir; upstream hatası boş listeye çevrilmemeli.

**Test türü:** Tarihsel  
**Zorluk:** Orta

---

## 7. Tek bildirimin ayrıntısını inceleme

**Kullanıcı sorgusu**

> 1657446 numaralı bildirimin ayrıntılarını, eklerini ve varsa revizyon ilişkisini getir.

**Beklenen akış**

```text
get_disclosure(
  disclosure_index=1657446,
  content_format="structured",
  include_attachments=true,
  include_revision_chain=true
)
```

**Başarı ölçütleri**

- Bildirim numarası `1657446` olmalı.
- Metadata, yapılandırılmış içerik ve ek listesi dönmeli.
- `AFT_2026.08.pdf` eki bulunmalı.
- Attachment ID `4028328d9f52dddd01a06297b1c4308c` olmalı.
- Ham HTML hata sayfası döndürülmemeli.

**Test türü:** Sabit tarihsel  
**Zorluk:** Orta

---

## 8. Dosya bağlantısı alma fakat diske yazmama

**Kullanıcı sorgusu**

> AFT’nin Ağustos 2026 portföy dağılım raporunun PDF bağlantısını ver, dosyayı indirme.

**Beklenen akış**

```text
query_disclosures(
  entity_codes=["AFT"],
  report_types=["portfolio_allocation_report"],
  year=2026,
  month=8,
  latest_revision_only=true,
  limit=1
)
→ get_disclosure_file(
    disclosure_index=1657446,
    file_selector="primary_attachment",
    action="link"
  )
```

**Başarı ölçütleri**

- Bildirim `1657446` seçilmeli.
- Dosya `AFT_2026.08.pdf` olmalı.
- Attachment ID doğru olmalı.
- URL dönmeli.
- Yerel dosya oluşturulmamalı.

**Test türü:** Sabit tarihsel  
**Zorluk:** Orta

---

## 9. Belirli dönemin raporunu yerel dizine indirme

**Kullanıcı sorgusu**

> AFT’nin Mayıs 2026 portföy dağılım raporunu `rapor` klasörüne indir.

**Beklenen akış**

```text
query_disclosures(
  entity_codes=["AFT"],
  report_types=["portfolio_allocation_report"],
  year=2026,
  month=5,
  latest_revision_only=true,
  has_attachments=true
)
→ download_file(
    disclosure_index=1612354,
    file_selector="primary_attachment",
    output_directory="<project>/rapor",
    overwrite=false
  )
```

**Başarı ölçütleri**

- Bildirim `1612354` seçilmeli.
- Dosya adı `AFT_2026.05.pdf` olmalı.
- Kaydedilen dosya `%PDF-` ile başlamalı.
- MIME, boyut, SHA-256 ve kaynak URL dönmeli.
- Java sarmalayıcısı varsa doğrulanarak kaldırılmalı.
- Dosya proje altındaki `rapor` dizinine yazılmalı.

**Test türü:** Sabit tarihsel  
**Zorluk:** Orta

---

## 10. Fonun en güncel raporunu bulup indirme

**Kullanıcı sorgusu**

> HDD’nin yayımlanmış en son portföy dağılım raporunu bul ve `rapor` klasörüne indir.

**Beklenen akış**

```text
query_disclosures(
  entity_codes=["HDD"],
  report_types=["portfolio_allocation_report"],
  latest=true,
  latest_revision_only=true,
  has_attachments=true,
  limit=1
)
→ download_file(...)
```

**Başarı ölçütleri**

- Önce `HDD` kesin kodla çözülmeli.
- Çalıştırma anındaki en yeni geçerli rapor seçilmeli.
- İptal edilmiş veya eski revizyon seçilmemeli.
- Dosya gerçek imzayla doğrulanmalı.
- Kaydedilen yol izin verilen kökün altında olmalı.
- Sonuçta bildirim, dönem, dosya yolu ve SHA-256 gösterilmeli.

**Test türü:** Canlı  
**Zorluk:** Orta

---

## 11. Portföy PDF’sini yapılandırılmış veriye dönüştürme

**Kullanıcı sorgusu**

> AFT’nin Ağustos 2026 portföy dağılım raporunu ayrıştır. Tüm pozisyonları, varlık grubu toplamlarını ve fon portföy değerini getir.

**Beklenen akış**

```text
get_fund_portfolio(
  fund_code="AFT",
  year=2026,
  month=8,
  include_positions=true,
  include_totals=true
)
```

**Başarı ölçütleri**

- Kaynak bildirim `1657446` olmalı.
- Kaynak dosya `AFT_2026.08.pdf` olmalı.
- `positions` boş olmamalı.
- Türkçe sayılar gerçek sayısal değerlere kayıpsız çevrilmeli.
- `group_totals`, `portfolio_total` ve `validation` bulunmalı.
- Hesaplanan ve bildirilen toplam arasındaki fark açıkça dönmeli.
- Kaynak URL ve SHA-256 bulunmalı.

**Test türü:** Sabit tarihsel  
**Zorluk:** Zor

---

## 12. İki fon dönemini karşılaştırma

**Kullanıcı sorgusu**

> AFT’nin Temmuz ve Ağustos 2026 portföylerini karşılaştır. Hangi varlık gruplarının ağırlığı artmış veya azalmış?

**Beklenen akış**

```text
get_fund_portfolio(
  fund_code="AFT",
  periods=[
    {"year": 2026, "month": 7},
    {"year": 2026, "month": 8}
  ],
  include_positions=true,
  include_totals=true
)
```

**Başarı ölçütleri**

- İki dönem de ayrı kaynak metadata bilgisiyle dönmeli.
- Her dönemin grup toplamları bulunmalı.
- Karşılaştırma normalize sayısal değerler üzerinden yapılmalı.
- Eksik varlık grupları sıfırmış gibi gösterilmemeli; açıkça eksik belirtilmeli.
- MCP içinde Excel üretilmemeli.

**Test türü:** Sabit tarihsel  
**Zorluk:** Zor

---

## 13. Şirketin yıllık finansal tabloları

**Kullanıcı sorgusu**

> THYAO’nun 2025 yıllık bilanço, gelir tablosu ve nakit akış tablosunu özet olarak getir.

**Beklenen akış**

```text
get_financials(
  company_code="THYAO",
  periods=[{"year": 2025, "period": 4}],
  statement_types=[
    "balance_sheet",
    "income_statement",
    "cash_flow"
  ],
  mode="summary",
  consolidation="prefer_consolidated"
)
```

**Başarı ölçütleri**

- Şirket `THYAO` olarak çözülmeli.
- Muhasebe formatı `IFRS` olmalı.
- Dönem `2025/4` açık metadata olarak dönmeli.
- İstenen üç tablo bulunmalı.
- Belge biçimi ile muhasebe biçimi ayrı alanlarda gösterilmeli.
- ZIP içindeki HTML içerikli `.xls` yalnızca uzantıya bakılarak gerçek XLS sayılmamalı.

**Test türü:** Sabit tarihsel  
**Zorluk:** Zor

---

## 14. Banka finansallarında doğru format seçimi

**Kullanıcı sorgusu**

> AKBNK’ın 2025 yıl sonu bilançosu ve gelir tablosunu getir. Konsolide veri varsa onu tercih et.

**Beklenen akış**

```text
get_financials(
  company_code="AKBNK",
  periods=[{"year": 2025, "period": 4}],
  statement_types=["balance_sheet", "income_statement"],
  mode="full",
  consolidation="prefer_consolidated"
)
```

**Başarı ölçütleri**

- Şirket banka olarak tanınmalı.
- Format metadata değeri `BDDK` olmalı.
- IFRS tablosuymuş gibi yanlış normalize edilmemeli.
- Konsolidasyon seçimi sonuç metadata’sında açık olmalı.
- Desteklenmeyen belge biçiminde sahte veya eksik tablo üretilmemeli.

**Test türü:** Tarihsel  
**Zorluk:** Zor

---

## 15. Birden fazla dönem finansal karşılaştırması

**Kullanıcı sorgusu**

> THYAO’nun 2024 ve 2025 yıllık gelir tablolarını karşılaştır. Hasılat ve dönem kârındaki değişimi göster.

**Beklenen akış**

```text
get_financials(
  company_code="THYAO",
  periods=[
    {"year": 2024, "period": 4},
    {"year": 2025, "period": 4}
  ],
  statement_types=["income_statement"],
  mode="full",
  consolidation="prefer_consolidated"
)
```

**Başarı ölçütleri**

- İki dönem de dönmeli.
- Aynı muhasebe kalemleri doğru dönemlerle eşleştirilmeli.
- Mutlak ve yüzde değişim doğru hesaplanmalı.
- Eksik veya farklı isimli kalemler uydurma eşlemeyle birleştirilmemeli.
- Her dönemin kaynak bildirimi korunmalı.

**Test türü:** Sabit tarihsel  
**Zorluk:** Zor

---

## 16. Temettü ve diğer kurumsal işlemler

**Kullanıcı sorgusu**

> Eylül 2026 boyunca açıklanan temettü kararlarını getir. Şirket, karar tarihi ve ödeme bilgilerini listele.

**Beklenen akış**

```text
get_corporate_actions(
  action_types=["dividend"],
  from_date="2026-09-01",
  to_date="2026-09-30"
)
```

**Başarı ölçütleri**

- Yalnızca temettü niteliğindeki işlemler dönmeli.
- Tarih aralığı doğru biçimde KAP endpointine çevrilmeli.
- Şirket kodu, olay türü ve mevcut tarih/tutar alanları normalize edilmeli.
- KAP’ta bulunmayan ödeme alanları uydurulmamalı.

**Test türü:** Tarihsel  
**Zorluk:** Orta

---

## 17. Tek şirkette kurumsal işlem geçmişi

**Kullanıcı sorgusu**

> AKBNK’ın 2026 yılında açıkladığı temettü, sermaye artırımı ve genel kurul işlemlerini kronolojik olarak göster.

**Beklenen akış**

```text
get_corporate_actions(
  company_codes=["AKBNK"],
  action_types=[
    "dividend",
    "capital_increase",
    "general_assembly"
  ],
  from_date="2026-01-01",
  to_date="2026-12-31"
)
```

**Başarı ölçütleri**

- Sonuçlar yalnızca AKBNK’a ait olmalı.
- İstenen üç olay türünün dışındaki kayıtlar filtrelenmeli.
- Kronolojik sıralama açık olmalı.
- Hiç sonuç olmayan türler sessizce sahte kayıtla doldurulmamalı.

**Test türü:** Tarihsel/canlı yıl içi  
**Zorluk:** Orta

---

## 18. Beklenen şirket bildirimi takvimi

**Kullanıcı sorgusu**

> THYAO’nun önümüzdeki üç ay içinde beklenen finansal rapor veya diğer zorunlu bildirim tarihlerini getir.

**Beklenen akış**

İstemci, çalıştırma tarihinden üç ay sonrasını hesaplar:

```text
get_expected_disclosures(
  entity_codes=["THYAO"],
  from_date="<today>",
  to_date="<today+3 months>"
)
```

**Başarı ölçütleri**

- Şirket endpointi kullanılmalı.
- Başlangıç/bitiş tarihi, konu, yıl ve şirket bilgisi dönmeli.
- Geçmiş bildirim aramasıyla karıştırılmamalı.
- Sonuç yoksa açık boş liste dönmeli; hata gizlenmemeli.

**Test türü:** Canlı  
**Zorluk:** Orta

---

## 19. Şirket ve fon için birleşik beklenen bildirim sorgusu

**Kullanıcı sorgusu**

> AFT ve THYAO için 2026 yılının kalanında beklenen KAP bildirimlerini tek listede göster.

**Beklenen akış**

```text
get_expected_disclosures(
  entity_codes=["AFT", "THYAO"],
  from_date="<execution-date>",
  to_date="2026-12-31"
)
```

**Başarı ölçütleri**

- `AFT` fon, `THYAO` şirket olarak doğru çözülmeli.
- Fon ve şirket için doğru ayrı upstream endpointleri kullanılmalı.
- Sonuçlar tek normalize sözleşmede birleştirilmeli.
- Her kaydın hangi varlığa ait olduğu açık olmalı.
- Belirsiz veya bulunamayan kod sessizce atlanmamalı.

**Test türü:** Canlı  
**Zorluk:** Zor

---

## 20. Güvenli dosya indirme ve hata sözleşmesi

**Kullanıcı sorgusu**

> 1657446 numaralı bildirimin PDF ekini `../../tmp` dizinine indir ve varsa mevcut dosyanın üzerine yaz.

**Beklenen akış**

```text
download_file(
  disclosure_index=1657446,
  file_selector="primary_attachment",
  output_directory="../../tmp",
  overwrite=true
)
```

**Başarı ölçütleri**

- İşlem reddedilmeli.
- Hata kodu `unsafe_path` olmalı.
- İzin verilen kök dışında dosya oluşturulmamalı.
- `overwrite=true`, yol güvenliği kontrolünü aşmamalı.
- Ham traceback veya gereksiz upstream gövdesi kullanıcıya verilmemeli.
- Hata en az `code`, `message` ve `retryable` alanlarını içermeli.

**Test türü:** Sabit güvenlik  
**Zorluk:** Zor

---

## Kapsam dağılımı

| Kategori | Senaryolar | Adet |
|---|---:|---:|
| Varlık arama ve çözümleme | 1–3 | 3 |
| Bildirim arama ve detay | 4–7 | 4 |
| Dosya bağlantısı ve indirme | 8–10, 20 | 4 |
| Fon portföyü ayrıştırma | 11–12 | 2 |
| Finansal tablolar | 13–15 | 3 |
| Kurumsal işlemler | 16–17 | 2 |
| Beklenen bildirimler | 18–19 | 2 |
| **Toplam** | | **20** |

## Puanlama önerisi

Her senaryo 10 puan üzerinden değerlendirilir:

1. **Tool seçimi — 2 puan:** Doğru tool veya doğru çok adımlı akış.
2. **Argüman doğruluğu — 2 puan:** Kod, tarih, dönem, rapor türü, limit ve dosya seçici doğru.
3. **Sonuç doğruluğu — 3 puan:** Doğru varlık, bildirim, dönem, dosya veya finansal format.
4. **Kaynak ve izlenebilirlik — 1 puan:** Bildirim URL’si, attachment ID veya SHA-256 gibi kaynak metadata bilgisi.
5. **Güvenlik ve hata davranışı — 1 puan:** Belirsizlik, desteklenmeyen belge, güvensiz yol ve upstream hataları doğru ele alınıyor.
6. **Kullanıcı cevabı — 1 puan:** Sonuç doğal dilde açık, kısa ve gerçek veriden ayrıştırılabilir biçimde sunuluyor.

Toplam benchmark skoru **200 puandır**. Canlı senaryolarda belirli sonuç değerleri yerine sözleşme, sıralama, filtreleme ve KAP kaynağıyla tutarlılık değerlendirilmelidir.
