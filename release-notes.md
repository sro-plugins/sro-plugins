## v1.7.22 (Merge main - Auto Hwt Gemi Enkazı, CAPTCHA)

### Auto Hwt (FGW/HWT) - main'den
- **Gemi Enkazı 1-2★ / 3-4★**: Scriptler artık sunucudan indiriliyor (`api/download`, type=SC)
- **Dosya adları**: `Ship Wreck 1-2 Stars Forgotten World.txt`, `Ship Wreck 3-4 Stars Forgotten World.txt`

### Oto Kervan / CAPTCHA - vps
- **Input konumu dinamik**: Sabit (x,y) kaldırıldı; Edit kontrolü aranır, yoksa pencere merkezi + ofset
- **Confirm butonu**: Enter yerine Confirm butonuna tıklanır

---

## v1.7.19 (Sunucu entegrasyonu: Caravan, Garden, versions.json)

### Genel
- **api/list, api/download**: Caravan, Garden scriptleri ve profil dosyaları artık ana sunucudan (vps.sro-plugins.cloud) indiriliyor
- **GitHub fallback kaldırıldı**: Caravan list/download, Garden script, Karavan profil JSON tamamen sunucu tabanlı

### Oto Kervan
- **Liste**: api/list (type=CARAVAN) ile sunucudan script listesi
- **İndirme**: api/download ile caravan scriptleri
- **Profil JSON**: ServerName_CharName.karavan.json sunucudan (files/caravan)

### Garden Dungeon
- **Scriptler**: api/download (type=SC) ile garden-dungeon.txt, garden-dungeon-wizz-cleric.txt
- **versions.json**: Sunucudan okunuyor

### versions.json (JSONS)
- **type=JSONS**: files/jsons/ içindeki versiyon dosyaları
- **Merkezi versiyonlama**: Tüm scriptler (garden + caravan) tek versions.json ile versiyonlanıyor
- **Otomatik güncelleme**: _check_script_updates hem garden hem caravan scriptlerini günceller

### Karavan Profil
- **db3**: GitHub indirme kaldırıldı; mevcut config'ten kopyalanır

---

## v1.7.21 (Oto Kervan – GUI düzeni, 2Captcha test modu)

### Oto Kervan
- **Script listesi**: Genişlik %50 düşürüldü (400 → 200 px)
- **API Key / CAPTCHA**: API key, Kaydet, checkbox'lar listenin sağına taşındı
- **2Captcha test modu**: API Key olarak `TEST` yazınca gerçek API çağrılmaz, akış test edilir (TEST123 yazılır + Confirm + tekrar mal al)

---

## v1.7.20 (Oto Kervan – Manuel shop, Mal al butonu, Confirm + tekrar mal al)

### Oto Kervan
- **NPC'yi manuel aç**: Opcode ile kervan çantası açılmıyorsa; "NPC'yi manuel aç" ile sadece NPC'ye gidilir, shop'u siz açarsınız
- **Mal al butonu**: Shop açıkken Mal al'a basınca satın alma paketi gider, Image Code Verification (CAPTCHA) tetiklenir
- **Confirm + tekrar mal al**: CAPTCHA çözümü input'a yazılır, Enter (Confirm) basılır, 2 sn sonra otomatik tekrar mal alma denemesi
- **Config**: `npc_manual_open` (varsayılan true)

---

## v1.7.19 (Oto Kervan – Mal alma + CAPTCHA otomatik çözüm)

### Oto Kervan
- **Mal alma otomatik**: CAPTCHA Test NPC açtıktan sonra satın alma paketi (0x704B) gönderilir; CAPTCHA tetiklenir
- **CAPTCHA otomatik çözüm**: 2Captcha API ile ekran bölgesi yakalanıp çözülür, cevap tuş basımı ile yazılır
- **GUI**: 2Captcha API Key, Kaydet, "CAPTCHA otomatik çöz (2Captcha)" checkbox (Tab 5)
- **Config**: `Config/SROManager/caravan_captcha.json` (api_key, auto_solve, region x,y,w,h)

---

## v1.7.18 (Oto Kervan – CAPTCHA Test butonu)

### Oto Kervan
- **CAPTCHA Test butonu**: Jangan (Jodaesan) ve Downhang (Leegak) ticaret NPC'sine gidip NPC'yi açar; mal almayı deneyerek CAPTCHA testi yapabilirsiniz (manuel CAPTCHA girişi)

---

## v1.7.17 (Oto Kervan, Script-Command iyileştirmeleri)

### Oto Kervan
- **NPC tabanlı varış**: Leegak (Downhang), Jodaesan (Jangan) ticaret NPC'lerine yaklaşınca otomatik durdur (5 birim)
- **Profil yoksa dialog**: Karavan profili seçili değilse talimat dialogu, otomatik profil oluşturma kaldırıldı
- **Profil üstüne yazma**: Karavan profilindeyken tweak'ler mevcut config'e uygulanır (backup/restore yok)
- **Varış mesafesi**: 5 birim threshold, son 8 waypoint + 2 saniye onay

### Script-Command (Varsayılan komutlar)
- **Lideri Kaydet butonu**: Sadece lider adını kaydeder, varsayılan komutlar için opcode gerekmez
- **Lider kaydı**: Kaydet'e basıldığında lider de kaydedilir
- **Çoklu lider**: Virgülle ayrılmış (Lider1,Lider2) desteklenir
- **Varsayılan komutlar**: START, STOP, TRACE, NOTRACE, ZERK, SETPOS, GETPOS, SETRADIUS, SETSCRIPT, SETAREA, PROFILE, FOLLOW, NOFOLLOW — liste yazıldığında o lider(ler)den çalışır

---

## v1.7.16 (Auto Hwt - FGW/HWT sc/ GitHub entegrasyonu)

### Değişiklikler
- **FGW/HWT scriptleri GitHub sc/ klasöründe**: Togui, Gemi, Alev, HWT scriptleri repoda
- **Scriptleri İndir**: GitHub'dan sc/'ye indirir (sabit path yok)
- **4 PC uyumlu**: Attack Area FGW_<PC>/ ile her PC kendi klasörüne yazar

---

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
