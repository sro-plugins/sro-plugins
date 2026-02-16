## v1.7.14 (Auto Hwt - Config Sync kaldırıldı)

### Değişiklikler
- **Config Sync kaldırıldı** (çalışmadığı için)

---

## v1.7.2 (Script Command Maker güncellemesi)

### Değişiklikler
- **Script Command Maker**: Modül güncellemeleri

---

## v1.7.1 (SSL düzeltmesi, cacert.pem, güncelleme iyileştirmesi)

### Değişiklikler
- **SSL / CERTIFICATE_VERIFY_FAILED**: Plugin ile gelen `cacert.pem` ile HTTPS doğrulaması (ek paket kurulumu gerekmez)
- **Güncelleme**: Otomatik güncellemede `cacert.pem` da indirilir
- **Release**: `sromanager.py` ve `cacert.pem` birlikte yayınlanır

---

## v1.7.0 (SROManager: plugin adı ve dosya yeniden adlandırıldı)

### Değişiklikler
- **Plugin adı:** DaRKWoLVeS Alet Çantası → SROManager
- **Dosya adı:** Santa-So-Ok-DaRKWoLVeS.py → sromanager.py
- **sromaster → sromanager:** Script komutu ve referanslar güncellendi
- Config klasörü: `Config/SROManager/`
- User-Agent: phBot-SROManager/1.0

---

## v1.6.0 (Script-Command tab, TargetSupport, Sıralı Bless)

### Yeni Sekmeler
- **Tab9 TargetSupport**: xTargetSupport entegrasyonu, lisans korumalı
- **Tab10 Sıralı Bless**: Bless Queue entegrasyonu, lisans korumalı, scroll desteği
- **Tab11 Script-Command**: SROManager Script & Chat Command Maker

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
