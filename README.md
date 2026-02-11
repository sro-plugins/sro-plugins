# SRO Plugins

[phBot](https://github.com/JellyBitz/phBot) için Silkroad Online (SRO) eklentileri ve karavan scriptleri.

## İçerik

| Klasör / Dosya | Açıklama |
|----------------|----------|
| **Santa-So-Ok-DaRKWoLVeS.py** | Ana eklenti: So-Ok event, Oto Kervan, Auto Dungeon, Garden Script, güncelleme kontrolü |
| **caravan/** | Oto Kervan için şehirler arası rota scriptleri (walk komutları) |
| **profile/** | Oto Kervan için örnek karavan profili (JSON) |
| **sc/** | Garden Dungeon scriptleri ve sürüm bilgileri |
| **create_release.py** | GitHub release oluşturma scripti |
| **release-notes.md** | Sürüm notları |

## Santa-So-Ok-DaRKWoLVeS Eklentisi

### Özellikler

- **So-Ok Event** – So-Ok event öğesini otomatik kullanma
- **Oto Kervan** – Karavan profili ve rota scriptleri ile otomatik ticaret rotası
- **Auto Dungeon** – Canavar sayacı, filtreleme, boyutsal delik, Unutulmuş Dünya davetleri
- **Garden Script** – Garden Dungeon için script güncellemeleri (normal ve wizz-cleric)
- **Çanta / Banka** – Birlestir ve sırala
- **Otomatik güncelleme** – Eklenti ve script sürümlerini GitHub üzerinden kontrol

### Kurulum

1. `Santa-So-Ok-DaRKWoLVeS.py` dosyasını phBot’un **plugins** klasörüne kopyalayın.
2. Opsiyonel: **caravan** ve **sc** klasörlerini eklenti dosyasıyla aynı dizine (veya phBot’un ilgili config/script dizinine) koyun; eklenti GitHub’dan da indirebilir.
3. phBot’u başlatıp eklentiyi etkinleştirin.

### Oto Kervan

- Ana pencerede karavan profili seçili olmalı (profil adında "karavan" geçmeli).
- İlk açılışta karavan profili yoksa `Server_CharName.karavan.json` şablonu oluşturulur.
- Rota scriptleri **caravan** içindeki `.txt` dosyalarından seçilir (Downhang–Hotan, Jangan–Alexandria, Samarkand vb.).

### Auto Dungeon

- Canavar sayacı, tür bazlı filtreleme (General, Champion, Giant, Titan, Strong, Elite, Unique, Party vb.)
- Boyutsal delik kullanımı ve Unutulmuş Dünya davetlerini otomatik kabul
- Arayüz Türkçe

## Gereksinimler

- [phBot](https://github.com/JellyBitz/phBot) (Silkroad Online bot istemcisi)
- Python 3.x (phBot ile birlikte gelir)

## Lisans

Bu proje **Apache-2.0** lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## Sürümler

Yayınlar: [Releases](https://github.com/sro-plugins/sro-plugins/releases)

Son sürüm notları için [release-notes.md](release-notes.md) dosyasına bakın.
