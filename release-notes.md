## v1.6.0 (Script-Command tab, TargetSupport, Sıralı Bless)

### Yeni Sekmeler
- **Tab9 TargetSupport**: xTargetSupport entegrasyonu, lisans korumalı
- **Tab10 Sıralı Bless**: Bless Queue entegrasyonu, lisans korumalı, scroll desteği
- **Tab11 Script-Command**: SROMaster Script & Chat Command Maker

### İyileştirmeler
- Sıralı Bless tasarımı orijinal Bless Queue yerleşimine uyumlu güncellendi
- Yardım metinleri Türkçeye çevrildi
- Tab9–Tab10 arası boşluk ayarları (5px → 3px → 1px → 0px)
- Sıralı Bless buton genişliği 85px → 65px
- Script-Command modülü: yerel bulunamazsa fallback path ile yükleme

---

## v1.4.0 (Oto-Kervan, Garden Script, temizlik)

### Oto-Kervan
- **Profil kontrolü**: Başlat sadece ana pencerede karavan profili seçiliyse çalışır (profil adında "karavan" aranır).
- **Init'te profil**: Plugin açılışında karavan profili (Server_CharName.karavan.json) yoksa oluşturulur (repodan veya mevcut config'ten).
- **Profil listesi**: Oto Kervan sekmesinde mevcut profiller listelenir; karavan seçili olmalı.

### Diğer
- Garden Script güncelleme log metni: "Garden Script güncellemeleri kontrol ediliyor..."
- Kod temizliği: gereksiz yorum ve kullanılmayan değişkenler kaldırıldı.

---

## Yeni Ozellikler

### Auto Dungeon Sistemi
- **Canavar Sayaci**: Bolgedeki canavarlari gercek zamanli sayma
- **Canavar Filtreleme**: Canavar turlerine gore filtreleme (General, Champion, Giant, Titan, Strong, Elite, Unique, Party, ChampionParty, GiantParty)
- **Boyutsal Delik Yonetimi**: Otomatik boyutsal delik kullanimi ve giris
- **Unutulmus Dunya**: Davetleri otomatik kabul etme ozelligi
- **Turkce Yerellestirme**: Tum arayuz Turkce

## Iyilestirmeler
- 3 panelli gelismis Auto Dungeon sekmesi
- Canavar tercihleri icin config yonetimi
- Isme gore canavar haric tutma listesi
- Tur bazli "Yoksay" ve "Sadece Say" secenekleri

## Tum Ozellikler
- So-Ok Event otomatik kullanma
- Canta/Banka birlestir ve sirala
- Auto Dungeon sistemi (YENI!)
- Otomatik guncelleme destegi
