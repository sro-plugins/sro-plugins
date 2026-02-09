# -*- coding: utf-8 -*-
from phBot import *
import phBot
import phBotChat
import QtBind
import math
import threading
import time
import copy
import json
import os
import shutil
import urllib.request
import urllib.parse
import sqlite3
import struct
import signal
import subprocess
from datetime import datetime, timedelta

pName = 'DaRKWoLVeS Alet Çantası'
PLUGIN_FILENAME = 'Santa-So-Ok-DaRKWoLVeS.py'
pVersion = '1.5.1'

MOVE_DELAY = 0.25

# Auto Dungeon constants
DIMENSIONAL_COOLDOWN_DELAY = 7200  # saniye (2 saat)
WAIT_DROPS_DELAY_MAX = 10  # saniye
COUNT_MOBS_DELAY = 1.0  # saniye

GITHUB_REPO = 'sro-plugins/sro-plugins'
GITHUB_API_LATEST = 'https://api.github.com/repos/%s/releases/latest' % GITHUB_REPO
GITHUB_RELEASES_URL = 'https://github.com/%s/releases' % GITHUB_REPO
GITHUB_RAW_MAIN = 'https://raw.githubusercontent.com/%s/main/%s' % (GITHUB_REPO, PLUGIN_FILENAME)
GITHUB_GARDEN_SCRIPT_URL = 'https://raw.githubusercontent.com/%s/main/sc/garden-dungeon.txt' % GITHUB_REPO
GITHUB_GARDEN_WIZZ_CLERIC_SCRIPT_URL = 'https://raw.githubusercontent.com/%s/main/sc/garden-dungeon-wizz-cleric.txt' % GITHUB_REPO
GITHUB_SCRIPT_VERSIONS_URL = 'https://raw.githubusercontent.com/%s/main/sc/versions.json' % GITHUB_REPO
# Oto Kervan: GitHub'daki karavan scriptleri klasörü (API ile liste, raw ile indirme)
# GitHub'da klasör yoksa veya 404 alırsa yerel "PHBOT Caravan SC" klasörü kullanılır (plugin yanında).
GITHUB_CARAVAN_FOLDER = 'PHBOT Caravan SC'
GITHUB_CARAVAN_BRANCH = 'main'
# API URL _fetch_caravan_script_list içinde quote ile oluşturulur (400 hatası önlemi)
# Raw template: tek format çağrısında (repo, branch, filename)
GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE = 'https://raw.githubusercontent.com/%s/%s/%s/%s'
# Karavan profili (sadece JSON): repoda profile/ServerName_CharName.karavan.json (şablon); indirilince Config'e Server_CharName.karavan.json olarak kaydedilir.
# JSON = Komut/kasılma alanı (Training, Script, Radius, Skip Town Script).
GITHUB_CARAVAN_PROFILE_FOLDER = 'profile'
GITHUB_CARAVAN_PROFILE_JSON_FILENAME = 'ServerName_CharName.karavan.json'
GITHUB_CARAVAN_PROFILE_DB3_FILENAME = 'caravan_profile.db3'
# Bu eklenti sürümüyle birlikte gelen script versiyonları (kullanıcı manipüle edemez).
# Repo'da script + versions.json güncellediğinde burayı da aynı versiyonlara çek ve eklenti sürümünü yayınla.
EMBEDDED_SCRIPT_VERSIONS = {
    "garden-dungeon.txt": "1.0",
    "garden-dungeon-wizz-cleric.txt": "1.0",
}
UPDATE_CHECK_DELAY = 3

def _parse_version(s):
    if not s or not isinstance(s, str):
        return (0, 0, 0)
    s = s.strip().lstrip('vV')
    parts = s.split('.')
    out = []
    for i in range(3):
        try:
            out.append(int(parts[i]) if i < len(parts) else 0)
        except (ValueError, IndexError):
            out.append(0)
    return tuple(out)

def _version_less(current_tuple, latest_tuple):
    return current_tuple < latest_tuple

def _fetch_github_latest():
    try:
        req = urllib.request.Request(
            GITHUB_API_LATEST,
            headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
        tag = data.get('tag_name') or ''
        url = data.get('html_url') or GITHUB_RELEASES_URL
        return tag, url
    except Exception as ex:
        log('[%s] Güncelleme kontrolü hatası: %s' % (pName, str(ex)))
        return None

def _get_update_download_url():
    try:
        req = urllib.request.Request(
            GITHUB_API_LATEST,
            headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
        assets = data.get('assets') or []
        for a in assets:
            name = (a.get('name') or '').lower()
            if name == PLUGIN_FILENAME.lower() or name.endswith('.py'):
                u = a.get('browser_download_url')
                if u:
                    return u
    except Exception:
        pass
    return GITHUB_RAW_MAIN

_update_label_ref = None
_update_status_text = ''

# Auto Dungeon global değişkenleri
character_data = None
itemUsedByPlugin = None
dimensionalItemActivated = None
lstMobsData = []
lstIgnore = []
lstOnlyCount = []

# Garden Dungeon global değişkenleri
_garden_dungeon_running = False
_garden_dungeon_script_path = ""
_garden_dungeon_script_type = "normal"  # "normal" veya "wizz-cleric"
_garden_dungeon_thread = None
_garden_dungeon_stop_event = threading.Event()
_garden_dungeon_lock = threading.Lock()

# Oto Kervan global değişkenleri
_caravan_script_list = []  # GitHub'dan gelen .txt dosya adları (liste sırası = gösterim sırası)
_caravan_running = False
_caravan_script_path = ""
_caravan_thread = None
_caravan_stop_event = threading.Event()
_caravan_lock = threading.Lock()

# Script Komutları (TR_ScriptCommands) global değişkenleri
_script_cmds_path = get_config_dir()[:-7]  # phBot ana klasör yolu
_script_cmds_StartBotAt = 0
_script_cmds_CloseBotAt = 0
_script_cmds_CheckStartTime = False
_script_cmds_CheckCloseTime = False
_script_cmds_SkipCommand = False
_script_cmds_delay_counter = 0
_script_cmds_BtnStart = False
_script_cmds_Recording = False
_script_cmds_RecordedPackets = []
_script_cmds_ExecutedPackets = []
_script_cmds_Index = 0
_script_cmds_StopBot = True
_script_cmds_cbxShowPackets = None  # Tab 7'de oluşturulacak

# Sunucu İletişimi (Server Communication) global değişkenleri
_server_license_key = ""  # Kullanıcının lisans anahtarı
_server_user_ip = ""  # Kullanıcının external IP adresi
_server_ip_fetch_lock = threading.Lock()
_server_ip_last_fetch = 0  # Son IP fetch zamanı (timestamp)

def _fetch_user_external_ip():
    """
    Kullanıcının external IP adresini alır.
    Birden fazla servis deneyerek güvenilirlik sağlar.
    """
    global _server_user_ip, _server_ip_last_fetch
    
    # Son 5 dakika içinde alınmışsa cache'den dön
    now = time.time()
    with _server_ip_fetch_lock:
        if _server_user_ip and (now - _server_ip_last_fetch) < 300:
            return _server_user_ip
    
    # Deneme yapılacak servisler (sırayla)
    ip_services = [
        'https://api.ipify.org?format=text',
        'https://icanhazip.com',
        'https://ident.me',
        'https://ipinfo.io/ip'
    ]
    
    fetched_ip = None
    for service_url in ip_services:
        try:
            req = urllib.request.Request(
                service_url,
                headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'}
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                ip = r.read().decode('utf-8').strip()
                # Basit IP format kontrolü (IPv4)
                parts = ip.split('.')
                if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                    fetched_ip = ip
                    break
        except Exception:
            continue
    
    if fetched_ip:
        with _server_ip_fetch_lock:
            _server_user_ip = fetched_ip
            _server_ip_last_fetch = now
        log('[%s] [Server] Kullanıcı IP alındı: %s' % (pName, fetched_ip))
        return fetched_ip
    else:
        log('[%s] [Server] IP adresi alınamadı!' % pName)
        return None

def _get_license_key():
    """Config'den lisans anahtarını okur"""
    global _server_license_key
    return _server_license_key

def _set_license_key(key):
    """Lisans anahtarını ayarlar ve config'e kaydeder"""
    global _server_license_key
    _server_license_key = key.strip()
    _save_server_config()
    log('[%s] [Server] Lisans anahtarı güncellendi' % pName)

def _save_server_config():
    """Sunucu ayarlarını config dosyasına kaydeder"""
    try:
        config_path = get_config_dir() + pName + "\\" + "server_config.json"
        config_dir = os.path.dirname(config_path)
        
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        config = {
            "license_key": _server_license_key
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        log('[%s] [Server] Config kaydetme hatası: %s' % (pName, str(ex)))

def _load_server_config():
    """Sunucu ayarlarını config dosyasından yükler"""
    global _server_license_key
    try:
        config_path = get_config_dir() + pName + "\\" + "server_config.json"
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                _server_license_key = config.get("license_key", "")
            log('[%s] [Server] Config yüklendi' % pName)
    except Exception as ex:
        log('[%s] [Server] Config yükleme hatası: %s' % (pName, str(ex)))
        _server_license_key = ""

def _validate_license():
    """
    Sunucuya lisans doğrulama isteği gönderir.
    IP manipüle edilemez - external servislerden alınır.
    
    Returns:
        dict: {"valid": True/False, "message": "..."} veya None (hata durumunda)
    """
    try:
        license_key = _get_license_key()
        
        # Lisans key kontrolü
        if not license_key:
            log('[%s] [Server] Lisans anahtarı girilmemiş!' % pName)
            return {"valid": False, "message": "Lisans anahtarı girilmemiş"}
        
        # IP'yi al (manipüle edilemez - external servislerden alınır)
        user_ip = _fetch_user_external_ip()
        if not user_ip:
            log('[%s] [Server] IP adresi alınamadı!' % pName)
            return {"valid": False, "message": "IP adresi alınamadı"}
        
        # API URL'i oluştur (query parametreleri ile)
        api_url = 'https://vps.sro-plugins.cloud/api/validate?publicId=%s&ip=%s' % (
            urllib.parse.quote(license_key),
            urllib.parse.quote(user_ip)
        )
        
        log('[%s] [Server] Lisans doğrulanıyor... (IP: %s)' % (pName, user_ip))
        
        # İstek gönder
        req = urllib.request.Request(
            api_url,
            headers={
                'User-Agent': 'phBot-Santa-So-Ok-Plugin/' + pVersion,
                'Accept': 'application/json'
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            response_data = response.read().decode('utf-8')
            
            # JSON yanıt parse et
            try:
                result = json.loads(response_data)
            except:
                # JSON değilse düz text olarak değerlendir
                result = {"detail": response_data}
            
            # Sunucu response formatı: {"status": "ok", "message": "..."} -> başarılı
            # Sunucu response formatı: {"detail": "..."} -> hata
            if result.get("status") == "ok":
                msg = result.get("message", "Authorized")
                log('[%s] [Server] Lisans geçerli: %s' % (pName, msg))
                return {"valid": True, "message": msg}
            else:
                msg = result.get("detail", result.get("message", "Lisans geçersiz"))
                log('[%s] [Server] Lisans doğrulama başarısız: %s' % (pName, msg))
                return {"valid": False, "message": msg}
                
    except urllib.error.HTTPError as ex:
        error_msg = "HTTP %d" % ex.code
        log('[%s] [Server] Lisans doğrulama hatası: %s' % (pName, error_msg))
        return {"valid": False, "message": error_msg}
    except Exception as ex:
        error_msg = str(ex)
        log('[%s] [Server] Lisans doğrulama hatası: %s' % (pName, error_msg))
        return {"valid": False, "message": error_msg}

def _validate_license_and_update_ui():
    """Lisans doğrulama yapar ve UI'ı günceller (thread-safe) - init sırasında çağrılır"""
    try:
        # UI'ı kontrol ediliyor durumuna getir
        QtBind.setText(gui, _lbl_server_status, 'Kontrol ediliyor...')
        # Error mesajlarını temizle
        QtBind.setText(gui, _lbl_error_msg1, '')
        QtBind.setText(gui, _lbl_error_msg2, '')
    except Exception:
        pass
    
    # Lisans doğrula
    result = _validate_license()
    
    if result and result.get("valid"):
        # Başarılı - lisans durumunu güncelle ve butonları aktif et
        _update_license_status(True)
        try:
            QtBind.setText(gui, _lbl_server_status, 'Sunucu: Bağlı - Geçerli')
            # Error mesajlarını temizle
            QtBind.setText(gui, _lbl_error_msg1, '')
            QtBind.setText(gui, _lbl_error_msg2, '')
            log('[%s] [Server] Lisans başarıyla doğrulandı!' % pName)
        except Exception:
            pass
    else:
        # Hata - lisans durumunu güncelle ve butonları pasif et
        _update_license_status(False)
        
        # Hata - init sırasında geçersiz key'i temizle
        global _server_license_key
        _server_license_key = ""
        _save_server_config()
        
        error_msg = result.get("message", "Bilinmeyen hata") if result else "Bağlantı hatası"
        
        # HTTP hataları veya bağlantı sorunları için "Bağlantı hatası"
        if "HTTP" in error_msg or "timed out" in error_msg.lower() or "connection" in error_msg.lower():
            error_msg = "Bağlantı hatası"
        
        try:
            QtBind.setText(gui, _lbl_server_status, 'Sunucu: ' + error_msg)
            
            # Error açıklama mesajı göster
            QtBind.setText(gui, _lbl_error_msg1, 'Sorun devam ederse,')
            QtBind.setText(gui, _lbl_error_msg2, 'brkcnszgn@gmail.com')
        except Exception:
            pass

def _download_garden_script(script_type="normal"):
    """GitHub'dan garden-dungeon script dosyasını indirir"""
    try:
        sc_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sc")

        # Script türüne göre dosya adı ve URL belirle
        if script_type == "wizz-cleric":
            script_filename = "garden-dungeon-wizz-cleric.txt"
            download_url = GITHUB_GARDEN_WIZZ_CLERIC_SCRIPT_URL
        else:
            script_filename = "garden-dungeon.txt"
            download_url = GITHUB_GARDEN_SCRIPT_URL

        script_path = os.path.join(sc_folder, script_filename)

        log('[%s] [Garden-Auto] GitHub\'dan script indiriliyor... (Tür: %s)' % (pName, script_type))
        log('[%s] [Garden-Auto] URL: %s' % (pName, download_url))

        # sc klasörü yoksa oluştur
        if not os.path.exists(sc_folder):
            os.makedirs(sc_folder)
            log('[%s] [Garden-Auto] sc klasörü oluşturuldu: %s' % (pName, sc_folder))

        # GitHub'dan indir (cache bypass için timestamp ekle)
        import time
        cache_buster = int(time.time())
        url_with_cache_buster = download_url + '?v=' + str(cache_buster)

        req = urllib.request.Request(
            url_with_cache_buster,
            headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'}
        )

        with urllib.request.urlopen(req, timeout=15) as r:
            script_content = r.read()

        content_length = len(script_content) if script_content else 0
        log('[%s] [Garden-Auto] İndirilen boyut: %d byte' % (pName, content_length))

        if not script_content or content_length < 10:
            log('[%s] [Garden-Auto] İndirilen script geçersiz (çok kısa: %d byte)' % (pName, content_length))
            return False

        # Dosyaya kaydet
        with open(script_path, 'wb') as f:
            f.write(script_content)

        log('[%s] [Garden-Auto] Script başarıyla indirildi: %s (%d byte)' % (pName, script_path, content_length))
        return script_path
    except Exception as ex:
        log('[%s] [Garden-Auto] Script indirme hatası: %s' % (pName, str(ex)))
        return False

def _caravan_filename_to_display_name(filename):
    """Dosya adını 'Hotan --> Jangan' formatında gösterim adına çevirir."""
    name = filename.replace('.txt', '').replace('_PHBOT', '')
    parts = name.split('_')
    to_idx = -1
    for i, p in enumerate(parts):
        if p.lower() == 'to':
            to_idx = i
            break
    if to_idx <= 0 or to_idx >= len(parts) - 1:
        return filename
    # Ön ek (1a, 8a vb.) varsa atla
    start = 0
    if parts and len(parts[0]) <= 3 and parts[0][0:1].isdigit():
        start = 1
    from_name = ' '.join(parts[start:to_idx])
    to_name = ' '.join(parts[to_idx + 1:])
    return from_name + ' --> ' + to_name

def _fetch_caravan_script_list():
    """GitHub API veya yerel klasör ile PHBOT Caravan SC .txt listesini döndürür."""
    # GitHub API: path quote ile encode, ref=main ile branch belirt
    path_encoded = urllib.parse.quote(GITHUB_CARAVAN_FOLDER, safe='')
    api_url = 'https://api.github.com/repos/%s/contents/%s?ref=%s' % (
        GITHUB_REPO, path_encoded, GITHUB_CARAVAN_BRANCH
    )
    try:
        req = urllib.request.Request(
            api_url,
            headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0', 'Accept': 'application/vnd.github.v3+json'}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode('utf-8'))
        names = []
        for item in (data if isinstance(data, list) else []):
            if isinstance(item, dict) and item.get('type') == 'file':
                name = item.get('name') or ''
                if name.endswith('.txt'):
                    names.append(name)
        names.sort(key=lambda x: x.lower())
        return names
    except Exception as ex:
        log('[%s] [Oto-Kervan] GitHub listesi alınamadı: %s' % (pName, str(ex)))
    # Fallback: yerel PHBOT Caravan SC klasöründeki .txt dosyaları
    folder = _get_caravan_script_folder()
    if os.path.isdir(folder):
        try:
            names = [f for f in os.listdir(folder) if f.endswith('.txt')]
            names.sort(key=lambda x: x.lower())
            if names:
                log('[%s] [Oto-Kervan] Yerel klasörden %d script listelendi.' % (pName, len(names)))
                return names
        except Exception as ex:
            log('[%s] [Oto-Kervan] Yerel liste okunamadı: %s' % (pName, str(ex)))
    return []

def _get_caravan_script_folder():
    """Oto Kervan scriptlerinin yerel klasör yolunu döndürür (plugin ile aynı dizinde)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), GITHUB_CARAVAN_FOLDER)

def _download_caravan_script(filename):
    """GitHub'dan tek bir karavan scriptini indirir; yerel yol döndürür veya False."""
    try:
        folder = _get_caravan_script_folder()
        if not os.path.exists(folder):
            os.makedirs(folder)
        script_path = os.path.join(folder, filename)
        path_encoded = urllib.parse.quote(GITHUB_CARAVAN_FOLDER, safe='')
        url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, path_encoded, filename)
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read()
        if not content or len(content) < 10:
            return False
        with open(script_path, 'wb') as f:
            f.write(content)
        log('[%s] [Oto-Kervan] Script indirildi: %s' % (pName, filename))
        return script_path
    except Exception as ex:
        log('[%s] [Oto-Kervan] İndirme hatası (%s): %s' % (pName, filename, str(ex)))
        return False

def _get_script_versions_cache_path():
    """Sürüm önbelleği dosya yolu (kullanıcı sc/ klasöründe görmez; phBot config içinde)"""
    try:
        return get_config_dir() + pName + "\\" + "sc_versions.dat"
    except Exception:
        return None

def _get_local_script_versions():
    """Son indirilen script versiyonlarını okur (config klasöründe; kullanıcı sc/ içinde görmez)"""
    path = _get_script_versions_cache_path()
    if not path:
        return {}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

def _save_local_script_versions(versions):
    """İndirilen sürümleri config klasörüne yazar (sc/ içine dosya koymuyoruz)"""
    path = _get_script_versions_cache_path()
    if not path:
        return False
    try:
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(versions, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def _check_script_updates():
    """GitHub'daki script versiyonlarını kontrol eder ve gerekirse günceller"""
    try:
        log('[%s] [Script-Update] Garden Script güncellemeleri kontrol ediliyor...' % pName)

        # GitHub'dan versions.json'ı indir (CDN cache bypass: no-cache + benzersiz query)
        cache_buster = str(int(time.time())) + '_' + str(id(object()))
        url_with_cache_buster = GITHUB_SCRIPT_VERSIONS_URL + '?v=' + cache_buster
        req = urllib.request.Request(
            url_with_cache_buster,
            headers={
                'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
            }
        )

        with urllib.request.urlopen(req, timeout=15) as r:
            github_versions_data = r.read()

        if not github_versions_data:
            log('[%s] [Script-Update] GitHub versions.json indirilemedi' % pName)
            return False

        github_versions = json.loads(github_versions_data.decode('utf-8'))
        local_versions = _get_local_script_versions()
        sc_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sc")
        updated_count = 0

        # Karar: yerleşik veya son indirdiğimiz versiyon vs GitHub (indirdikten sonra kaydediyoruz, tekrar indirme olmasın)
        for script_name, github_info in github_versions.items():
            if isinstance(github_info, dict):
                github_version = github_info.get("version", "0.0")
            else:
                github_version = github_info

            embedded_version = EMBEDDED_SCRIPT_VERSIONS.get(script_name, "0.0")
            local_info = local_versions.get(script_name, {})
            stored_version = local_info.get("version", "") if isinstance(local_info, dict) else ""
            current_version = stored_version if stored_version else embedded_version

            script_path = os.path.join(sc_folder, script_name)

            needs_update = False
            update_reason = ""
            if not os.path.exists(script_path):
                needs_update = True
                update_reason = "dosya yok"
            elif _version_less(_parse_version(current_version), _parse_version(github_version)):
                needs_update = True
                update_reason = "yeni versiyon (v%s -> v%s)" % (current_version, github_version)

            if needs_update:
                log('[%s] [Script-Update] %s güncelleniyor... (%s)' % (pName, script_name, update_reason))
                if os.path.exists(script_path):
                    try:
                        os.remove(script_path)
                        log('[%s] [Script-Update] Eski %s silindi' % (pName, script_name))
                    except Exception as ex:
                        log('[%s] [Script-Update] Eski dosya silinemedi: %s' % (pName, str(ex)))

                script_type = "wizz-cleric" if "wizz-cleric" in script_name else "normal"
                download_result = _download_garden_script(script_type)
                if download_result:
                    local_versions[script_name] = {"version": github_version}
                    _save_local_script_versions(local_versions)
                    updated_count += 1
                    log('[%s] [Script-Update] %s başarıyla güncellendi (v%s)' % (pName, script_name, github_version))
                else:
                    log('[%s] [Script-Update] %s güncellenemedi!' % (pName, script_name))

        if updated_count > 0:
            log('[%s] [Script-Update] %d script güncellendi' % (pName, updated_count))
        else:
            log('[%s] [Script-Update] Tüm scriptler güncel' % pName)

        return True

    except Exception as ex:
        log('[%s] [Script-Update] Güncelleme kontrolü hatası: %s' % (pName, str(ex)))
        return False

def _check_script_updates_thread():
    """Script güncellemelerini thread'de kontrol eder"""
    time.sleep(5)  # Plugin yüklenene kadar bekle
    _check_script_updates()

def _check_update_thread(skip_delay=False):
    global _update_status_text, _update_label_ref
    try:
        if not skip_delay:
            time.sleep(UPDATE_CHECK_DELAY)
        result = _fetch_github_latest()
        if result is None:
            _update_status_text = 'Sürüm kontrol edilemedi'
            log('[%s] Sürüm kontrolü başarısız (ağ veya API hatası).' % pName)
        else:
            tag, url = result
            latest_tuple = _parse_version(tag)
            current_tuple = _parse_version(pVersion)
            if _version_less(current_tuple, latest_tuple):
                _update_status_text = 'Yeni sürüm: %s (indir)' % tag
                log('[%s] Güncelleme var: %s → %s | %s' % (pName, pVersion, tag, url))
            else:
                _update_status_text = 'Güncel (v%s)' % pVersion
                log('[%s] Sürüm güncel: v%s' % (pName, pVersion))
        if _update_label_ref is not None:
            try:
                QtBind.setText(gui, _update_label_ref, _update_status_text)
            except Exception:
                pass
    except Exception as ex:
        _update_status_text = 'Hata'
        log('[%s] Sürüm kontrolü hatası: %s' % (pName, str(ex)))
        if _update_label_ref is not None:
            try:
                QtBind.setText(gui, _update_label_ref, _update_status_text)
            except Exception:
                pass

def check_update():
    global _update_status_text
    _update_status_text = 'Kontrol ediliyor...'
    if _update_label_ref is not None:
        try:
            QtBind.setText(gui, _update_label_ref, _update_status_text)
        except Exception:
            pass
    log('[%s] Güncelleme kontrol ediliyor...' % pName)
    t = threading.Thread(target=lambda: _check_update_thread(skip_delay=True), name=pName + '_update_check', daemon=True)
    t.start()

def _do_auto_update_thread():
    global _update_status_text, _update_label_ref
    try:
        if _update_label_ref is not None:
            try:
                QtBind.setText(gui, _update_label_ref, 'İndiriliyor...')
            except Exception:
                pass
        log('[%s] Güncelleme indiriliyor...' % pName)
        download_url = _get_update_download_url()
        req = urllib.request.Request(download_url, headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            new_content = r.read()
        if not new_content or len(new_content) < 500:
            log('[%s] Güncelleme indirilemedi: dosya geçersiz.' % pName)
            _update_status_text = 'İndirme başarısız'
            if _update_label_ref is not None:
                try:
                    QtBind.setText(gui, _update_label_ref, _update_status_text)
                except Exception:
                    pass
            return
        plugin_path = os.path.abspath(__file__)
        with open(plugin_path, 'wb') as f:
            f.write(new_content)
        log('[%s] Güncelleme tamamlandı. Eklentiyi yeniden yükleyin.' % pName)
        _update_status_text = 'Güncellendi - yeniden yükleyin'
        if _update_label_ref is not None:
            try:
                QtBind.setText(gui, _update_label_ref, _update_status_text)
            except Exception:
                pass
    except Exception as ex:
        log('[%s] Güncelleme hatası: %s' % (pName, str(ex)))
        _update_status_text = 'Hata: %s' % str(ex)[:30]
        if _update_label_ref is not None:
            try:
                QtBind.setText(gui, _update_label_ref, _update_status_text)
            except Exception:
                pass

def do_auto_update():
    t = threading.Thread(target=_do_auto_update_thread, name=pName + '_auto_update', daemon=True)
    t.start()

def _save_license_key_clicked():
    """Lisans anahtarını kaydet butonuna tıklandığında - önce doğrular, başarılıysa kaydeder"""
    try:
        key = QtBind.text(gui, _tbx_license_key)
        if not key or not key.strip():
            log('[%s] [Server] Lisans anahtarı boş olamaz!' % pName)
            return
        
        # Geçici olarak key'i set et (kaydetmeden önce doğrulama için)
        global _server_license_key
        temp_key = _server_license_key
        _server_license_key = key.strip()
        
        # Doğrulama yap
        threading.Thread(target=_validate_and_save_if_success, name=pName + '_validate_save', daemon=True).start()
    except Exception as ex:
        log('[%s] [Server] Lisans kaydetme hatası: %s' % (pName, str(ex)))

def _validate_and_save_if_success():
    """Lisans doğrular, başarılıysa kaydeder"""
    try:
        # UI'ı kontrol ediliyor durumuna getir
        QtBind.setText(gui, _lbl_server_status, 'Sunucu: Kontrol ediliyor...')
        QtBind.setText(gui, _lbl_error_msg1, '')
        QtBind.setText(gui, _lbl_error_msg2, '')
    except Exception:
        pass
    
    # Lisans doğrula
    result = _validate_license()
    
    if result and result.get("valid"):
        # Başarılı - kaydet ve butonları aktif et
        _save_server_config()
        _update_license_status(True)
        try:
            QtBind.setText(gui, _lbl_server_status, 'Sunucu: Bağlı - Geçerli')
            QtBind.setText(gui, _lbl_error_msg1, '')
            QtBind.setText(gui, _lbl_error_msg2, '')
            log('[%s] [Server] Lisans doğrulandı ve kaydedildi!' % pName)
        except Exception:
            pass
    else:
        # Hata - kaydetme ve butonları pasif et
        _update_license_status(False)
        global _server_license_key
        _server_license_key = ""  # Geçersiz key'i temizle
        
        error_msg = result.get("message", "Bilinmeyen hata") if result else "Bağlantı hatası"
        
        # HTTP 401 gibi kodları "Bağlantı hatası" olarak göster
        if "HTTP" in error_msg or "timed out" in error_msg.lower() or "connection" in error_msg.lower():
            error_msg = "Bağlantı hatası"
        
        try:
            QtBind.setText(gui, _lbl_server_status, 'Sunucu: ' + error_msg)
            log('[%s] [Server] Lisans geçersiz, kaydedilmedi!' % pName)
        except Exception:
            pass

def _clear_license_key_clicked():
    """Temizle butonuna tıklandığında - kayıtlı lisans anahtarını siler"""
    try:
        global _server_license_key
        _server_license_key = ""
        _save_server_config()
        
        # Butonları pasif et
        _update_license_status(False)
        
        # UI'ı temizle
        QtBind.setText(gui, _tbx_license_key, '')
        QtBind.setText(gui, _lbl_server_status, 'Sunucu: Bağlı Değil')
        QtBind.setText(gui, _lbl_error_msg1, '')
        QtBind.setText(gui, _lbl_error_msg2, '')
        
        log('[%s] [Server] Lisans anahtarı temizlendi' % pName)
    except Exception as ex:
        log('[%s] [Server] Temizleme hatası: %s' % (pName, str(ex)))

def _refresh_ip_clicked():
    """IP yenile butonuna tıklandığında"""
    try:
        QtBind.setText(gui, _lbl_user_ip, 'Alınıyor...')
        threading.Thread(target=_fetch_and_update_ip_ui, name=pName + '_fetch_ip', daemon=True).start()
    except Exception as ex:
        log('[%s] [Server] IP yenileme hatası: %s' % (pName, str(ex)))

def _fetch_and_update_ip_ui():
    """IP'yi fetch eder ve UI'ı günceller (thread-safe)"""
    ip = _fetch_user_external_ip()
    if ip:
        try:
            QtBind.setText(gui, _lbl_user_ip, ip)
        except Exception:
            pass
    else:
        try:
            QtBind.setText(gui, _lbl_user_ip, 'Alınamadı')
        except Exception:
            pass

def _init_server_credentials():
    """Plugin başlatıldığında sunucu bilgilerini yükler, IP'yi alır ve lisans doğrular"""
    # Config'i yükle
    _load_server_config()
    
    # Başlangıçta butonları pasif et (lisans yoksa)
    if not _server_license_key:
        _update_license_status(False)
    
    # UI'ya lisans key'i yükle
    try:
        if _server_license_key:
            QtBind.setText(gui, _tbx_license_key, _server_license_key)
    except Exception:
        pass
    
    # IP'yi fetch et ve lisans doğrula (background'da)
    def _init_validate():
        # Önce IP'yi al
        _fetch_and_update_ip_ui()
        # Lisans key varsa doğrula
        if _server_license_key:
            time.sleep(1)  # IP'nin UI'a yansıması için kısa bekleme
            _validate_license_and_update_ui()
        else:
            # Lisans yoksa butonları pasif tut
            _update_license_status(False)
    
    threading.Thread(target=_init_validate, name=pName + '_init_validate', daemon=True).start()

NPC_STORAGE_SERVERNAMES = [
    'NPC_CH_WAREHOUSE_M', 'NPC_CH_WAREHOUSE_W', 'NPC_EU_WAREHOUSE',
    'NPC_WC_WAREHOUSE_M', 'NPC_WC_WAREHOUSE_W', 'NPC_CA_WAREHOUSE',
    'NPC_KT_WAREHOUSE', 'NPC_AR_WAREHOUSE', 'NPC_SD_M_AREA_WAREHOUSE',
    'NPC_SD_T_AREA_WAREHOUSE2'
]

JEWEL_INJECT_PACKETS = [
    (0x7045, False, b'\xE9\x00\x00\x00'),
    (0x7046, False, b'\xE9\x00\x00\x00\x02'),
    (0x30D4, False, b'\x05'),
    (0x30D4, False, b'\x05')
]
JEWEL_DELAY = 0.1

_jewel_stop_event = threading.Event()
_jewel_thread = None
_jewel_lock = threading.Lock()

def _jewel_loop():
    while not _jewel_stop_event.is_set():
        for opcode, encrypted, data in JEWEL_INJECT_PACKETS:
            if _jewel_stop_event.is_set():
                break
            try:
                inject_joymax(opcode, data, encrypted)
                log('[%s] Inject → 0x%X' % (pName, opcode))
            except Exception as ex:
                log('[%s] Inject hata → %s' % (pName, str(ex)))
            if _jewel_stop_event.is_set() or _jewel_stop_event.wait(JEWEL_DELAY):
                break
        if _jewel_stop_event.is_set():
            break
        time.sleep(0.3)
    log('[%s] Jewel Box kırdırma durdu.' % pName)

def jewel_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _jewel_thread
    with _jewel_lock:
        if _jewel_thread and _jewel_thread.is_alive():
            log('[%s] Jewel Box zaten çalışıyor.' % pName)
            return
        _jewel_stop_event.clear()
        _jewel_thread = threading.Thread(target=_jewel_loop, name=pName + '_jewel', daemon=True)
        _jewel_thread.start()
    log('[%s] Jewel Box kırdırma başladı.' % pName)

def jewel_stop():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _jewel_thread
    with _jewel_lock:
        _jewel_stop_event.set()
        if _jewel_thread and _jewel_thread.is_alive():
            _jewel_thread.join(timeout=2)
        _jewel_thread = None
    log('[%s] Jewel Box kırdırma durduruldu.' % pName)

def _send_move(source_slot, destination_slot):
    inv = get_inventory()
    if not inv or not inv.get('items') or inv.get('size', 0) == 0:
        return False
    items = inv['items']
    size = inv['size']
    if source_slot < 0 or source_slot >= size or destination_slot < 0 or destination_slot >= size:
        return False
    if items[source_slot] is None:
        return False
    qty = items[source_slot].get('quantity', 1)
    packet = bytearray(b'\x00')
    packet.append(source_slot)
    packet.append(destination_slot)
    packet += struct.pack('<H', qty)
    try:
        inject_joymax(0x7034, bytes(packet), False)
    except Exception as ex:
        log('[%s] Taşıma hata: %s' % (pName, ex))
        return False
    time.sleep(MOVE_DELAY)
    return True

def _slot_is_full(slot_item):
    if not slot_item or not isinstance(slot_item, dict):
        return True
    try:
        info = get_item(slot_item.get('model'))
        if not info:
            return False
        max_stack = info.get('max_stack', 0)
        if max_stack <= 0:
            return False
        return slot_item.get('quantity', 0) >= max_stack
    except Exception:
        return False

_merge_stop_event = threading.Event()
_merge_thread = None
_merge_lock = threading.Lock()

def _merge_loop():
    item_start_slot = 13
    max_passes = 200
    for _ in range(max_passes):
        if _merge_stop_event.is_set():
            break
        inv = get_inventory()
        if not inv or 'items' not in inv:
            break
        items = inv['items']
        size = inv.get('size', len(items))
        merged = False
        for i in range(item_start_slot, size):
            if _merge_stop_event.is_set():
                break
            inv = get_inventory()
            if not inv or 'items' not in inv:
                break
            items = inv['items']
            size = inv.get('size', len(items))
            if i >= len(items) or items[i] is None:
                continue
            if _slot_is_full(items[i]):
                continue
            srv = items[i].get('servername')
            if not srv:
                continue
            for j in range(i + 1, size):
                if _merge_stop_event.is_set():
                    break
                if j >= len(items) or items[j] is None:
                    continue
                if items[j].get('servername') != srv:
                    continue
                if _slot_is_full(items[i]):
                    break
                log('[%s] Birleştir: slot %d → %d' % (pName, j, i))
                _send_move(j, i)
                merged = True
                inv = get_inventory()
                if inv and 'items' in inv:
                    items = inv['items']
                    size = inv.get('size', len(items))
                break
            if merged:
                break
        if not merged:
            break
    log('[%s] Birleştirme bitti.' % pName)

def merge_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _merge_thread
    with _merge_lock:
        if _merge_thread and _merge_thread.is_alive():
            log('[%s] Birleştirme zaten çalışıyor.' % pName)
            return
        _merge_stop_event.clear()
        _merge_thread = threading.Thread(target=_merge_loop, name=pName + '_merge', daemon=True)
        _merge_thread.start()
    log('[%s] Birleştirme başladı.' % pName)

def merge_stop():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _merge_thread
    with _merge_lock:
        _merge_stop_event.set()
        if _merge_thread and _merge_thread.is_alive():
            _merge_thread.join(timeout=5)
        _merge_thread = None
    log('[%s] Birleştirme durduruldu.' % pName)

def _array_sort_by_subkey(array, subkey):
    if not isinstance(array, list):
        return False
    sorted_array = copy.deepcopy(array)
    for i, elem in enumerate(sorted_array):
        if elem is None or not isinstance(elem, dict):
            sorted_array[i] = {subkey: ''}
        elif subkey not in elem:
            sorted_array[i] = dict(elem)
            sorted_array[i][subkey] = ''
        else:
            sorted_array[i] = dict(elem)
            for o, subelem in list(sorted_array[i].items()):
                if not isinstance(subelem, (int, str)):
                    sorted_array[i][o] = ''
    sorted_array = sorted(sorted_array, key=lambda x: x.get(subkey, ''), reverse=True)
    return sorted_array

def _array_get_subkey_filtered_keys(array, subkey, values):
    keys = []
    if not isinstance(array, list):
        return keys
    if not isinstance(values, list):
        values = [values]
    for i, subarray in enumerate(array):
        if not isinstance(subarray, dict):
            continue
        if subkey not in subarray:
            continue
        for v in values:
            if subarray[subkey] == v:
                keys.append(i)
                break
    return keys

_sort_stop_event = threading.Event()
_sort_thread = None
_sort_lock = threading.Lock()

def _sort_loop():
    try:
        inv = get_inventory()
        if not inv or 'items' not in inv:
            log('[%s] Envanter alınamadı.' % pName)
            return
        size = inv.get('size', len(inv['items']))
        item_start_slot = 13
        for i in range(item_start_slot, size):
            if _sort_stop_event.is_set():
                break
            inv = get_inventory()
            if not inv or 'items' not in inv:
                break
            items = inv['items']
            slice_items = items[i:]
            sorted_items = _array_sort_by_subkey(slice_items, 'servername')
            if not sorted_items or len(sorted_items) == 0:
                continue
            first_name = sorted_items[0].get('servername', '')
            if not first_name:
                continue
            item_slots = _array_get_subkey_filtered_keys(slice_items, 'servername', first_name)
            if not item_slots:
                break
            from_slot = i + item_slots[0]
            if from_slot == i:
                continue
            log('[%s] Sırala: slot %d → %d' % (pName, from_slot, i))
            _send_move(from_slot, i)
    except Exception as ex:
        log('[%s] Sıralama hata: %s' % (pName, str(ex)))
    log('[%s] Sıralama bitti.' % pName)

def sort_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _sort_thread
    with _sort_lock:
        if _sort_thread and _sort_thread.is_alive():
            log('[%s] Sıralama zaten çalışıyor.' % pName)
            return
        _sort_stop_event.clear()
        _sort_thread = threading.Thread(target=_sort_loop, name=pName + '_sort', daemon=True)
        _sort_thread.start()
    log('[%s] Sıralama başladı.' % pName)

def sort_stop():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _sort_thread
    with _sort_lock:
        _sort_stop_event.set()
        if _sort_thread and _sort_thread.is_alive():
            _sort_thread.join(timeout=5)
        _sort_thread = None
    log('[%s] Sıralama durduruldu.' % pName)

def _npc_get_id_storage():
    try:
        npcs = get_npcs()
        if not npcs:
            return None
        if isinstance(npcs, dict):
            for idx, n in npcs.items():
                if isinstance(n, dict) and n.get('servername') in NPC_STORAGE_SERVERNAMES:
                    return struct.pack('<H', idx)
        else:
            for i, n in enumerate(npcs):
                if isinstance(n, dict) and n.get('servername') in NPC_STORAGE_SERVERNAMES:
                    return struct.pack('<H', i)
    except Exception:
        pass
    return None

def _open_storage_npc():
    npc_id = _npc_get_id_storage()
    if not npc_id:
        log('[%s] Banka NPC bulunamadı. Banka NPC\'sinin yakınına gidin.' % pName)
        return False
    try:
        inject_joymax(0x7045, npc_id + b'\x00\x00', False)
        time.sleep(0.5)
        inject_joymax(0x7046, npc_id + b'\x00\x00\x03', False)
        time.sleep(1.0)
        inject_joymax(0x703C, npc_id + b'\x00\x00\x00', False)
        time.sleep(1.0)
    except Exception as ex:
        log('[%s] Banka açma hata: %s' % (pName, ex))
        return False
    log('[%s] Banka açıldı.' % pName)
    return True

def _send_move_storage(source_slot, destination_slot):
    st = get_storage()
    if not st or not st.get('items') or st.get('size', 0) == 0:
        return False
    items = st['items']
    size = st['size']
    if source_slot < 0 or source_slot >= size or destination_slot < 0 or destination_slot >= size:
        return False
    if items[source_slot] is None:
        return False
    npc_id = _npc_get_id_storage()
    if not npc_id:
        log('[%s] Banka NPC bulunamadı. Banka NPC\'sini açın.' % pName)
        return False
    qty = items[source_slot].get('quantity', 1)
    packet = bytearray(b'\x01')
    packet.append(source_slot)
    packet.append(destination_slot)
    packet += struct.pack('<H', qty)
    packet += npc_id
    packet += b'\x00\x00'
    try:
        inject_joymax(0x7034, bytes(packet), False)
    except Exception as ex:
        log('[%s] Banka taşıma hata: %s' % (pName, ex))
        return False
    time.sleep(MOVE_DELAY)
    return True

def _storage_slot_is_full(slot_item):
    if not slot_item or not isinstance(slot_item, dict):
        return True
    try:
        info = get_item(slot_item.get('model'))
        if not info:
            return False
        max_stack = info.get('max_stack', 0)
        if max_stack <= 0:
            return False
        return slot_item.get('quantity', 0) >= max_stack
    except Exception:
        return False

_bank_merge_stop_event = threading.Event()
_bank_merge_thread = None
_bank_merge_lock = threading.Lock()

def _bank_merge_loop():
    item_start_slot = 0
    max_passes = 200
    for _ in range(max_passes):
        if _bank_merge_stop_event.is_set():
            break
        st = get_storage()
        if not st or 'items' not in st:
            break
        items = st['items']
        size = st.get('size', len(items))
        merged = False
        for i in range(item_start_slot, size):
            if _bank_merge_stop_event.is_set():
                break
            st = get_storage()
            if not st or 'items' not in st:
                break
            items = st['items']
            size = st.get('size', len(items))
            if i >= len(items) or items[i] is None:
                continue
            if _storage_slot_is_full(items[i]):
                continue
            srv = items[i].get('servername')
            if not srv:
                continue
            for j in range(i + 1, size):
                if _bank_merge_stop_event.is_set():
                    break
                if j >= len(items) or items[j] is None:
                    continue
                if items[j].get('servername') != srv:
                    continue
                if _storage_slot_is_full(items[i]):
                    break
                log('[%s] Banka birleştir: slot %d → %d' % (pName, j, i))
                _send_move_storage(j, i)
                merged = True
                st = get_storage()
                if st and 'items' in st:
                    items = st['items']
                    size = st.get('size', len(items))
                break
            if merged:
                break
        if not merged:
            break
    log('[%s] Banka birleştirme bitti.' % pName)

def bank_merge_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _bank_merge_thread
    if not _open_storage_npc():
        return
    with _bank_merge_lock:
        if _bank_merge_thread and _bank_merge_thread.is_alive():
            log('[%s] Banka birleştirme zaten çalışıyor.' % pName)
            return
        _bank_merge_stop_event.clear()
        _bank_merge_thread = threading.Thread(target=_bank_merge_loop, name=pName + '_bank_merge', daemon=True)
        _bank_merge_thread.start()
    log('[%s] Banka birleştirme başladı.' % pName)

def bank_merge_stop():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _bank_merge_thread
    with _bank_merge_lock:
        _bank_merge_stop_event.set()
        if _bank_merge_thread and _bank_merge_thread.is_alive():
            _bank_merge_thread.join(timeout=5)
        _bank_merge_thread = None
    log('[%s] Banka birleştirme durduruldu.' % pName)

_bank_sort_stop_event = threading.Event()
_bank_sort_thread = None
_bank_sort_lock = threading.Lock()

def _bank_sort_loop():
    try:
        st = get_storage()
        if not st or 'items' not in st:
            log('[%s] Banka alınamadı. Banka NPC\'sini açın.' % pName)
            return
        size = st.get('size', len(st['items']))
        item_start_slot = 0
        for i in range(item_start_slot, size):
            if _bank_sort_stop_event.is_set():
                break
            st = get_storage()
            if not st or 'items' not in st:
                break
            items = st['items']
            slice_items = items[i:]
            sorted_items = _array_sort_by_subkey(slice_items, 'servername')
            if not sorted_items or len(sorted_items) == 0:
                continue
            first_name = sorted_items[0].get('servername', '')
            if not first_name:
                continue
            item_slots = _array_get_subkey_filtered_keys(slice_items, 'servername', first_name)
            if not item_slots:
                break
            from_slot = i + item_slots[0]
            if from_slot == i:
                continue
            log('[%s] Banka sırala: slot %d → %d' % (pName, from_slot, i))
            _send_move_storage(from_slot, i)
    except Exception as ex:
        log('[%s] Banka sıralama hata: %s' % (pName, str(ex)))
    log('[%s] Banka sıralama bitti.' % pName)

def bank_sort_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _bank_sort_thread
    if not _open_storage_npc():
        return
    with _bank_sort_lock:
        if _bank_sort_thread and _bank_sort_thread.is_alive():
            log('[%s] Banka sıralama zaten çalışıyor.' % pName)
            return
        _bank_sort_stop_event.clear()
        _bank_sort_thread = threading.Thread(target=_bank_sort_loop, name=pName + '_bank_sort', daemon=True)
        _bank_sort_thread.start()
    log('[%s] Banka sıralama başladı.' % pName)

def bank_sort_stop():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _bank_sort_thread
    with _bank_sort_lock:
        _bank_sort_stop_event.set()
        if _bank_sort_thread and _bank_sort_thread.is_alive():
            _bank_sort_thread.join(timeout=5)
        _bank_sort_thread = None
    log('[%s] Banka sıralama durduruldu.' % pName)

# ______________________________ Garden Dungeon Fonksiyonları ______________________________ #

def _garden_dungeon_loop():
    global _garden_dungeon_running
    try:
        script_path = _garden_dungeon_script_path

        log('[%s] [Garden-Auto] Garden Dungeon başlatılıyor...' % pName)

        # Script kontrolü
        if not script_path or not os.path.exists(script_path):
            log('[%s] [Garden-Auto] Script bulunamadı: %s' % (pName, script_path))
            _garden_dungeon_running = False
            return

        # Her başlatmada mevcut pozisyonu al ve training area'yı güncelle
        pos = get_position()
        if not pos:
            log('[%s] [Garden-Auto] Pozisyon alınamadı!' % pName)
            _garden_dungeon_running = False
            return

        # Training position'ı karakterin mevcut konumuna göre ayarla
        region = pos.get('region', 0)
        x = pos.get('x', 0)
        y = pos.get('y', 0)
        z = pos.get('z', 0)

        set_training_position(region, x, y, z)
        set_training_radius(50.0)
        log('[%s] [Garden-Auto] Training position ayarlandı: (%d, %.1f, %.1f, %.1f)' % (pName, region, x, y, z))

        # Script'i ayarla
        result = set_training_script(script_path)
        if result:
            log('[%s] [Garden-Auto] Training script ayarlandı: %s' % (pName, script_path))
        else:
            log('[%s] [Garden-Auto] Training script ayarlanamadı!' % pName)
            _garden_dungeon_running = False
            return

        # Kısa bir bekleme süresi (training area'nın hazır olması için)
        time.sleep(0.5)

        start_bot()
        _garden_dungeon_running = True
        log('[%s] [Garden-Auto] Bot başlatıldı' % pName)

        # Thread çalışırken bot'un durumunu kontrol et
        while not _garden_dungeon_stop_event.is_set():
            time.sleep(1)

        log('[%s] [Garden-Auto] Garden Dungeon durduruluyor...' % pName)
        stop_bot()
        _garden_dungeon_running = False
    except Exception as ex:
        log('[%s] [Garden-Auto] Hata: %s' % (pName, str(ex)))
        _garden_dungeon_running = False

def garden_dungeon_select_normal():
    global _garden_dungeon_script_type
    _garden_dungeon_script_type = "normal"
    QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Normal script seçildi')
    log('[%s] [Garden-Auto] Normal script seçildi' % pName)

def garden_dungeon_select_wizz_cleric():
    global _garden_dungeon_script_type
    _garden_dungeon_script_type = "wizz-cleric"
    QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Wizz/Cleric script seçildi')
    log('[%s] [Garden-Auto] Wizz/Cleric script seçildi' % pName)

def garden_dungeon_start():
    global _garden_dungeon_thread, _garden_dungeon_running, _garden_dungeon_script_path, _garden_dungeon_script_type

    # Textbox'tan script yolunu al ve temizle
    script_path_from_ui = QtBind.text(gui, tbxGardenScriptPath).strip()

    # Tırnak işaretlerini temizle (baş ve sondaki " ve ' karakterlerini)
    if script_path_from_ui:
        # Başta ve sonda " veya ' varsa kaldır
        script_path_from_ui = script_path_from_ui.strip('"').strip("'").strip()

    # Eğer textbox'ta bir şey varsa onu kullan
    if script_path_from_ui:
        _garden_dungeon_script_path = script_path_from_ui
        log('[%s] [Garden-Auto] Özel script yolu: %s' % (pName, _garden_dungeon_script_path))
    # Yoksa seçilen türe göre varsayılanı kullan
    elif not _garden_dungeon_script_path:
        if _garden_dungeon_script_type == "wizz-cleric":
            _garden_dungeon_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sc", "garden-dungeon-wizz-cleric.txt")
            log('[%s] [Garden-Auto] Wizz/Cleric script kullanılıyor: %s' % (pName, _garden_dungeon_script_path))
        else:
            _garden_dungeon_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sc", "garden-dungeon.txt")
            log('[%s] [Garden-Auto] Normal script kullanılıyor: %s' % (pName, _garden_dungeon_script_path))

    # Training area "garden-auto" var mı kontrol et (script olmasa da çalışabilir)
    has_training_area = False
    try:
        current_area = get_training_area()
        if current_area and current_area.get('name') == 'garden-auto':
            has_training_area = True
    except Exception:
        pass

    # Script dosyasının var olup olmadığını kontrol et (training area yoksa script şart)
    if not has_training_area and not os.path.exists(_garden_dungeon_script_path):
        # Varsayılan scriptlerden biri mi kontrol et
        default_normal = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sc", "garden-dungeon.txt")
        default_wizz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sc", "garden-dungeon-wizz-cleric.txt")

        if _garden_dungeon_script_path in [default_normal, default_wizz]:
            log('[%s] [Garden-Auto] Script bulunamadı, GitHub\'dan indiriliyor...' % pName)
            QtBind.setText(gui, lblGardenScriptStatus, 'Durum: GitHub\'dan indiriliyor...')

            downloaded_path = _download_garden_script(_garden_dungeon_script_type)
            if downloaded_path:
                _garden_dungeon_script_path = downloaded_path
                log('[%s] [Garden-Auto] Script başarıyla indirildi' % pName)
                QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Script indirildi ✓')
            else:
                log('[%s] [Garden-Auto] Script indirilemedi!' % pName)
                QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Script indirilemedi! ✗')
                return
        else:
            # Özel script ise indirme, hata ver
            log('[%s] [Garden-Auto] Özel script bulunamadı: %s' % (pName, _garden_dungeon_script_path))
            QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Script bulunamadı! ✗')
            return

    with _garden_dungeon_lock:
        if _garden_dungeon_thread and _garden_dungeon_thread.is_alive():
            log('[%s] [Garden-Auto] Garden Dungeon zaten çalışıyor.' % pName)
            QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Zaten çalışıyor...')
            return
        _garden_dungeon_stop_event.clear()
        _garden_dungeon_thread = threading.Thread(target=_garden_dungeon_loop, name=pName + '_garden_dungeon', daemon=True)
        _garden_dungeon_thread.start()

    QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Çalışıyor... ▶')
    log('[%s] [Garden-Auto] Garden Dungeon başlatıldı.' % pName)

def garden_dungeon_stop():
    global _garden_dungeon_thread, _garden_dungeon_running
    with _garden_dungeon_lock:
        _garden_dungeon_stop_event.set()
        if _garden_dungeon_thread and _garden_dungeon_thread.is_alive():
            _garden_dungeon_thread.join(timeout=3)
        _garden_dungeon_thread = None
        _garden_dungeon_running = False
    stop_bot()
    QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Durduruldu ■')
    log('[%s] [Garden-Auto] Garden Dungeon durduruldu.' % pName)

# ______________________________ Oto Kervan Fonksiyonları ______________________________ #

def kervan_refresh_list():
    """GitHub'dan karavan script listesini çeker ve listeyi günceller (gösterim: From --> To)."""
    global _caravan_script_list
    QtBind.setText(gui, lblKervanStatus, 'Durum: Liste yükleniyor...')
    names = _fetch_caravan_script_list()
    QtBind.clear(gui, lstKervanScripts)
    _caravan_script_list = []
    if not names:
        QtBind.append(gui, lstKervanScripts, '(Liste alınamadı - Yenile\'yi tekrar deneyin)')
        QtBind.setText(gui, lblKervanStatus, 'Durum: Liste alınamadı')
        log('[%s] [Oto-Kervan] Script listesi boş veya hata.' % pName)
        return
    for name in names:
        _caravan_script_list.append(name)
        display = _caravan_filename_to_display_name(name)
        QtBind.append(gui, lstKervanScripts, display)
    QtBind.setText(gui, lblKervanStatus, 'Durum: %d script listelendi' % len(names))
    log('[%s] [Oto-Kervan] %d karavan scripti listelendi.' % (pName, len(names)))
    _caravan_ensure_karavan_profile_on_init()
    _caravan_update_profile_display()

def _caravan_update_profile_display():
    """Aktif profil adını gösterir."""
    try:
        path = get_config_path()
        if not path:
            QtBind.setText(gui, lblKervanProfile, '(Bilinmiyor)')
            return
        base = os.path.basename(path)
        if base.endswith('.json'):
            profile_name = base[:-5]  # .json eki çıkarılır
            QtBind.setText(gui, lblKervanProfile, profile_name)
        else:
            QtBind.setText(gui, lblKervanProfile, '(Bilinmiyor)')
    except Exception:
        QtBind.setText(gui, lblKervanProfile, '(Hata)')


# Bu mesafenin altındaysak rota üzerindeyiz sayılır; üstündeyse bot en yakın script noktasına götürür sonra script devam eder
CARAVAN_JOIN_STEP = 5
# Karakter zaten bu mesafedeyse ilk waypoint'e değil bir sonrakinden başla (ilk komut "orada" sayılıp hareket etmeyebilir)
CARAVAN_ON_PATH_THRESHOLD = 15

def _caravan_script_from_nearest(script_path, current_region, current_x, current_y, current_z):
    """
    En yakın script waypoint'ini bulur. Char çok uzaktaysa: generate_script(region, x, y, z)
    ile en yakın noktaya takılmadan giden yol alınır, önce o çalıştırılır sonra script devam eder.
    Char zaten rotada çok yakınsa (ON_PATH_THRESHOLD) bir sonraki waypoint'ten başlar ki hareket etsin.
    """
    with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    if not lines:
        return ''
    nearest_line_idx = 0
    nearest_dist = float('inf')
    nearest_x, nearest_y, nearest_z = current_x, current_y, current_z
    for i, line in enumerate(lines):
        parts = line.split(',')
        if len(parts) < 2:
            continue
        cmd = parts[0].strip().lower()
        if cmd != 'walk':
            continue
        try:
            if len(parts) == 4:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            elif len(parts) == 5:
                reg = int(parts[1])
                if reg != current_region:
                    continue
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            else:
                continue
        except (ValueError, IndexError):
            continue
        d = math.sqrt((x - current_x) ** 2 + (y - current_y) ** 2 + (z - current_z) ** 2)
        if d < nearest_dist:
            nearest_dist = d
            nearest_line_idx = i
            nearest_x, nearest_y, nearest_z = x, y, z
    start_idx = nearest_line_idx
    if nearest_dist < CARAVAN_ON_PATH_THRESHOLD and nearest_line_idx + 1 < len(lines):
        start_idx = nearest_line_idx + 1
        log('[%s] [Oto-Kervan] Rotada çok yakınsın (%.0f); %d. satırdan devam ediyor.' % (pName, nearest_dist, start_idx + 1))
    elif nearest_line_idx > 0:
        log('[%s] [Oto-Kervan] En yakın nokta %d. satır (mesafe ~%.0f).' % (pName, nearest_line_idx + 1, nearest_dist))
    script_from_nearest = '\n'.join(lines[start_idx:])
    if nearest_dist <= CARAVAN_JOIN_STEP:
        return script_from_nearest
    # Char script konumunda değilse bot devralır: generate_script ile en yakın script waypoint'ine götür, sonra script devam etsin
    join_lines = None
    try:
        path_script = generate_script(int(current_region), int(round(nearest_x)), int(round(nearest_y)), int(round(nearest_z)))
        if path_script and isinstance(path_script, list) and len(path_script) > 0:
            join_lines = [ln.strip() for ln in path_script if ln and ln.strip()]
            # İlk walk komutları mevcut konuma çok yakınsa atla (oyun "orada" deyip hareket ettirmeyebilir)
            filtered = []
            for ln in join_lines:
                parts = [p.strip() for p in ln.split(',')]
                if len(parts) >= 4 and parts[0].lower() == 'walk':
                    try:
                        if len(parts) == 4:
                            wx, wy, wz = float(parts[1]), float(parts[2]), float(parts[3])
                        else:
                            wx, wy, wz = float(parts[2]), float(parts[3]), float(parts[4])
                        d = math.sqrt((wx - current_x)**2 + (wy - current_y)**2 + (wz - current_z)**2)
                        if d < CARAVAN_ON_PATH_THRESHOLD:
                            continue
                    except (ValueError, IndexError):
                        pass
                filtered.append(ln)
            if filtered:
                join_lines = filtered
                log('[%s] [Oto-Kervan] Bot en yakın script konumuna götürüyor (%d adım), sonra script devam edecek.' % (pName, len(join_lines)))
            else:
                join_lines = None
    except Exception as ex:
        log('[%s] [Oto-Kervan] generate_script kullanılamadı: %s' % (pName, str(ex)))
    if not join_lines:
        log('[%s] [Oto-Kervan] Pathfinding alınamadı; en yakın noktadan devam (takılma riski).' % pName)
        return script_from_nearest
    return '\n'.join(join_lines) + '\n' + script_from_nearest

def _caravan_temp_script_path():
    """Karavan için geçici script dosyası; phBot set_training_script'in kabul etmesi için Config kökünde."""
    try:
        config_dir = get_config_dir()
        if not config_dir:
            return None
        config_dir = config_dir.rstrip('/\\')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, 'caravan_current.txt')
        return os.path.abspath(path)
    except Exception:
        return None

# Karavan: Başlat'ta config yedeklenir, karavan profili (JSON) uygulanır; Durdur'da yedek geri yüklenir.
CARAVAN_PROFILE_FILENAME = 'caravan_profile.json'
CARAVAN_BACKUP_FILENAME = 'caravan_backup.json'
CARAVAN_DB3_PROFILE_SUFFIX = 'caravan'
CARAVAN_DB3_BACKUP_SUFFIX = '_caravan_backup'

def _caravan_profile_path():
    """Karavan profili dosya yolu (saldırı kapalı, şehir atla ayarlı tam config)."""
    folder = get_config_dir() + pName + "\\"
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder + CARAVAN_PROFILE_FILENAME

def _caravan_backup_path():
    """Karavan başlamadan önce mevcut config yedeği."""
    folder = get_config_dir() + pName + "\\"
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder + CARAVAN_BACKUP_FILENAME

def _caravan_db3_filename():
    """phBot aktif db3 dosya adı (Server_CharName). DatabaseProfiles ile aynı isimlendirme."""
    try:
        cd = get_character_data()
        if cd and cd.get('server') and cd.get('name'):
            return cd['server'] + '_' + cd['name']
    except Exception:
        pass
    return None

def _caravan_db3_dir():
    """Config klasörü (db3 dosyaları burada; get_config_dir() sonunda / veya \\ olabilir)."""
    d = get_config_dir()
    return d.rstrip('/\\') if d else ''


def _caravan_db3_current_path():
    """Aktif db3 dosya yolu."""
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + '.db3')

def _caravan_db3_caravan_path():
    """Karavan profili db3 yolu (Server_CharName.caravan.db3)."""
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + '.' + CARAVAN_DB3_PROFILE_SUFFIX + '.db3')

def _caravan_db3_backup_path():
    """Karavan öncesi db3 yedeği."""
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + CARAVAN_DB3_BACKUP_SUFFIX + '.db3')

def _caravan_has_caravan_db3():
    """Karavan db3 profili var mı (önceden oluşturulmuş veya indirilmiş)."""
    path = _caravan_db3_caravan_path()
    return path and os.path.exists(path)

def _caravan_db3_karavan_named_path():
    """Botta 'Karavan' adlı profil (DatabaseProfiles) varsa onun db3 yolu (Server_CharName.Karavan.db3)."""
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + '.Karavan.db3')

def _caravan_download_profile_db3(save_path):
    """
    Repodan karavan_profile.db3 indirir ve save_path'e yazar. Başarılı ise True.
    Önce sc/, sonra PHBOT Caravan SC/ altında aranır.
    """
    if not save_path:
        return False
    for folder in ('sc', GITHUB_CARAVAN_FOLDER):
        try:
            path_encoded = urllib.parse.quote(folder, safe='')
            url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, path_encoded, GITHUB_CARAVAN_PROFILE_DB3_FILENAME)
            req = urllib.request.Request(url, headers={'User-Agent': 'phBot-Santa-So-Ok/1.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            if data:
                with open(save_path, 'wb') as f:
                    f.write(data)
                log('[%s] [Oto-Kervan] Karavan profili (db3) indirildi: %s' % (pName, folder + '/' + GITHUB_CARAVAN_PROFILE_DB3_FILENAME))
                return True
        except Exception as ex:
            continue
    return False

def _caravan_switch_to_caravan_db3():
    """Aktif db3 yedeklenir; karavan db3 aktif yapılır. Durdur'da yedek geri yüklenir."""
    current = _caravan_db3_current_path()
    caravan = _caravan_db3_caravan_path()
    backup = _caravan_db3_backup_path()
    if not current or not caravan or not backup:
        return None
    if not os.path.exists(current):
        return None
    try:
        source_db3 = None
        karavan_named = _caravan_db3_karavan_named_path()
        if karavan_named and os.path.exists(karavan_named):
            source_db3 = karavan_named
            log('[%s] [Oto-Kervan] Botta mevcut "Karavan" profili kullanılıyor.' % pName)
        if not source_db3 and os.path.exists(caravan):
            source_db3 = caravan
        if not source_db3:
            if _caravan_download_profile_db3(caravan):
                source_db3 = caravan
            else:
                shutil.copy2(current, caravan)
                source_db3 = caravan
                log('[%s] [Oto-Kervan] Karavan db3 profili oluşturuldu (mevcut ayarlardan); repoda %s yoksa ekleyebilirsiniz.' % (pName, GITHUB_CARAVAN_PROFILE_DB3_FILENAME))
        shutil.copy2(current, backup)
        shutil.copy2(source_db3, current)
        if source_db3 != karavan_named:
            log('[%s] [Oto-Kervan] Karavan db3 profili uygulandı (pick filter, town vb.).' % pName)
        return backup
    except Exception as ex:
        log('[%s] [Oto-Kervan] db3 karavan profili uygulanamadı: %s' % (pName, str(ex)))
        return None

def _caravan_restore_db3(backup_path):
    """Aktif db3 dosyasını yedekten geri yükler."""
    if not backup_path or not os.path.exists(backup_path):
        return
    current = _caravan_db3_current_path()
    if not current:
        return
    try:
        shutil.copy2(backup_path, current)
        log('[%s] [Oto-Kervan] db3 yedekten geri yüklendi.' % pName)
    except Exception as ex:
        log('[%s] [Oto-Kervan] db3 geri yüklenemedi: %s' % (pName, str(ex)))

def _caravan_apply_tweaks_to_dict(data):
    """
    Config dict'inin bir kopyasına karavan ayarlarını uygular: tüm Attack/Combat -> False,
    SkipTown / SkipTownScript / NoTownScript vb. -> True. İç içe dict'leri dolaşır.
    """
    if not isinstance(data, dict):
        return data
    out = copy.deepcopy(data)
    attack_keys = ('Attack', 'attack', 'Combat', 'combat')
    skip_keys = ('SkipTownScript', 'SkipTown', 'SkipTownLoop', 'NoTownScript', 'SkipTownScriptLoop')

    def apply(obj):
        if not isinstance(obj, dict):
            return
        for k, v in list(obj.items()):
            if isinstance(v, dict):
                apply(v)
            elif isinstance(v, bool):
                if k in attack_keys and v:
                    obj[k] = False
                elif k in skip_keys and not v:
                    obj[k] = True
                else:
                    k_lower = k.lower()
                    if k_lower in ('attack', 'combat') and v:
                        obj[k] = False
                    elif 'skiptown' in k_lower or 'notown' in k_lower:
                        obj[k] = True
    apply(out)
    return out

def _caravan_karavan_json_path():
    """
    Bu char için karavan config JSON dosya yolu (phBot Config klasöründe).
    Örn: Config/Sirion_VisKi.karavan.json. Dosya var olmasa da path döner (indirince buraya yazılacak).
    """
    fn = _caravan_db3_filename()
    if not fn:
        return None
    config_dir = _caravan_db3_dir()
    if not config_dir:
        path = get_config_path()
        config_dir = os.path.dirname(path) if path else ''
    if not config_dir:
        return None
    return os.path.join(config_dir, fn + '.karavan.json')

def _caravan_phbot_karavan_json_path():
    """
    phBot'ta bu char için karavan profil JSON'u var mı; varsa yolu (Config/Server_CharName.karavan.json veya .Karavan.json).
    """
    for suffix in ('.karavan.json', '.Karavan.json'):
        p = os.path.join(_caravan_db3_dir(), _caravan_db3_filename() + suffix) if _caravan_db3_filename() and _caravan_db3_dir() else None
        if p and os.path.exists(p):
            return p
    return None

def _caravan_char_has_any_config():
    """Bu char için Config klasöründe herhangi bir dosya var mı (örn. Sirion_VisKi.json veya .karavan.json)."""
    fn = _caravan_db3_filename()
    if not fn:
        return False
    config_dir = _caravan_db3_dir()
    if not config_dir or not os.path.isdir(config_dir):
        return False
    try:
        for name in os.listdir(config_dir):
            if name.startswith(fn + '.') or name == fn + '.json':
                return True
    except Exception:
        pass
    return False

def _caravan_download_profile_json(save_path):
    """
    Repodan profile/ServerName_CharName.karavan.json indirir; Config içine o anki char adıyla kaydeder:
    Sirion_VisKi.karavan.json (server + '_' + name + '.karavan.json'). Başarılı ise True.
    """
    if not save_path:
        return False
    config_dir = os.path.dirname(save_path)
    if config_dir and not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception:
            pass
    try:
        folder_enc = urllib.parse.quote(GITHUB_CARAVAN_PROFILE_FOLDER, safe='')
        url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, folder_enc, GITHUB_CARAVAN_PROFILE_JSON_FILENAME)
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-Santa-So-Ok/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if data:
            with open(save_path, 'wb') as f:
                f.write(data)
            basename = os.path.basename(save_path)
            log('[%s] [Oto-Kervan] Karavan profili indirildi; Config içine %s olarak kaydedildi.' % (pName, basename))
            return True
    except Exception:
        pass
    return False


def _caravan_ensure_karavan_profile_on_init():
    """Init'te karavan profili (Server_CharName.karavan.json) yoksa oluşturur (repodan veya mevcut config'ten). Var olanı ezmez."""
    if _caravan_phbot_karavan_json_path():
        return
    save_path = _caravan_karavan_json_path()
    if not save_path:
        return
    if _caravan_download_profile_json(save_path):
        return
    path = get_config_path()
    if not path or not os.path.exists(path):
        return
    try:
        config_dir = os.path.dirname(save_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data = _caravan_apply_tweaks_to_dict(data)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log('[%s] [Oto-Kervan] Init: Karavan profili oluşturuldu (mevcut ayarlardan). Otomatik yapılandırma: "karavan" profilini seçip Başlat\'a basabilirsiniz.' % pName)
    except Exception as ex:
        log('[%s] [Oto-Kervan] Init: Karavan profili oluşturulamadı: %s' % (pName, str(ex)))


def _caravan_ensure_profile_file(current_config_path):
    """
    Karavan profil dosyası (plugin içi caravan_profile.json) yoksa mevcut config'ten oluşturur.
    Sadece phBot karavan JSON'u yoksa kullanılır. Profil dosyası yolunu döndürür veya None.
    """
    profile_path = _caravan_profile_path()
    if os.path.exists(profile_path):
        return profile_path
    if not current_config_path or not os.path.exists(current_config_path):
        return None
    try:
        with open(current_config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data = _caravan_apply_tweaks_to_dict(data)
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log('[%s] [Oto-Kervan] Karavan profili oluşturuldu (yedek): %s' % (pName, profile_path))
        return profile_path
    except Exception as ex:
        log('[%s] [Oto-Kervan] Karavan profili oluşturulamadı: %s' % (pName, str(ex)))
        return None

def _caravan_switch_to_profile():
    """Mevcut config yedeklenir; karavan profili (yerel/repodan) aktif config'e yazılır. Yedek path döner."""
    path = get_config_path()
    if not path or not os.path.exists(path):
        return None
    backup_path = _caravan_backup_path()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            backup_data = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(backup_data)
        profile_path = _caravan_phbot_karavan_json_path()
        if not profile_path:
            save_path = _caravan_karavan_json_path()
            if save_path:
                if not _caravan_char_has_any_config():
                    log('[%s] [Oto-Kervan] Bu char için Config\'te henüz dosya yok; repodan profil indiriliyor.' % pName)
                if _caravan_download_profile_json(save_path):
                    profile_path = save_path
        if not profile_path or not os.path.exists(profile_path):
            profile_path = _caravan_ensure_profile_file(path)
        if not profile_path or not os.path.exists(profile_path):
            return None
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_data = f.read()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(profile_data)
        phbot_karavan = _caravan_phbot_karavan_json_path()
        if phbot_karavan and profile_path == phbot_karavan:
            log('[%s] [Oto-Kervan] phBot karavan profili uygulandı (config yedeklendi).' % pName)
        else:
            log('[%s] [Oto-Kervan] Karavan profili uygulandı (config yedeklendi).' % pName)
        return backup_path
    except Exception as ex:
        log('[%s] [Oto-Kervan] Profil uygulanamadı: %s' % (pName, str(ex)))
        return None

def _caravan_restore_from_backup(backup_path):
    """Aktif config dosyasını yedekten geri yükler."""
    if not backup_path or not os.path.exists(backup_path):
        return
    path = get_config_path()
    if not path:
        return
    try:
        with open(backup_path, 'r', encoding='utf-8') as f:
            data = f.read()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        log('[%s] [Oto-Kervan] Config yedekten geri yüklendi.' % pName)
    except Exception as ex:
        log('[%s] [Oto-Kervan] Config geri yüklenemedi: %s' % (pName, str(ex)))

def _caravan_loop():
    """Config yedeklenir, karavan profili (JSON) uygulanır, script çalıştırılır; Durdur'da config geri yüklenir."""
    global _caravan_running
    temp_path = None
    backup_path = None
    try:
        current_area = get_training_area()
        if not current_area:
            cfg_path_now = get_config_path()
            if cfg_path_now and os.path.exists(cfg_path_now):
                try:
                    with open(cfg_path_now, 'r', encoding='utf-8') as f:
                        cfg_now = json.load(f)
                    script_cfg = (cfg_now.get('Loop') or {}).get('Script') or {}
                    if isinstance(script_cfg, dict):
                        for area_name in list(script_cfg.keys()):
                            if area_name and set_training_area(area_name):
                                log('[%s] [Oto-Kervan] Kasılma alanı aktif edildi: %s' % (pName, area_name))
                                break
                except Exception:
                    pass

        backup_path = _caravan_switch_to_profile()
        if not backup_path:
            log('[%s] [Oto-Kervan] Config profil uygulanamadı; mevcut ayarlarla devam ediliyor.' % pName)

        script_path = _caravan_script_path
        log('[%s] [Oto-Kervan] Karavan yürüyüşü başlatılıyor: %s' % (pName, script_path))
        if not script_path or not os.path.exists(script_path):
            log('[%s] [Oto-Kervan] Script bulunamadı: %s' % (pName, script_path))
            _caravan_running = False
            return
        pos = get_position()
        if not pos:
            log('[%s] [Oto-Kervan] Pozisyon alınamadı!' % pName)
            _caravan_running = False
            return
        region = pos.get('region', 0)
        cx = float(pos.get('x', 0))
        cy = float(pos.get('y', 0))
        cz = float(pos.get('z', 0))
        script_content = _caravan_script_from_nearest(script_path, region, cx, cy, cz)
        if not script_content:
            log('[%s] [Oto-Kervan] Script dosyası boş veya uygun nokta yok!' % pName)
            _caravan_running = False
            return
        temp_path = _caravan_temp_script_path()
        if not temp_path:
            log('[%s] [Oto-Kervan] Geçici dosya yolu alınamadı.' % pName)
            _caravan_running = False
            return
        with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script_content)
        current_area = get_training_area()
        if not current_area and backup_path and os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                script_cfg = (cfg.get('Loop') or {}).get('Script') or {}
                if isinstance(script_cfg, dict):
                    for area_name in list(script_cfg.keys()):
                        if area_name and set_training_area(area_name):
                            log('[%s] [Oto-Kervan] Aktif training area seçildi: %s' % (pName, area_name))
                            break
            except Exception:
                pass
        set_training_position(region, cx, cy, cz)
        set_training_radius(600.0)
        script_path_for_bot = os.path.abspath(temp_path)
        script_set_ok = set_training_script(script_path_for_bot)
        if not script_set_ok:
            cfg_path = get_config_path()
            if cfg_path and os.path.exists(cfg_path):
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                    loop = cfg.get('Loop')
                    if not isinstance(loop, dict):
                        loop = {}
                        cfg['Loop'] = loop
                    script_cfg = loop.get('Script')
                    if not isinstance(script_cfg, dict):
                        script_cfg = {}
                        loop['Script'] = script_cfg
                    caravan_area = {
                        'Data': [],
                        'Enabled': True,
                        'Path': script_path_for_bot.replace('/', '\\'),
                        'Pick Radius': 50,
                        'Polygon': [],
                        'Radius': 600.0,
                        'Region': region,
                        'Type': 0,
                        'X': float(cx),
                        'Y': float(cy),
                        'Z': float(cz),
                    }
                    for name in list(script_cfg.keys()):
                        if isinstance(script_cfg.get(name), dict):
                            script_cfg[name]['Enabled'] = False
                    script_cfg['Caravan'] = caravan_area
                    with open(cfg_path, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, indent=4, ensure_ascii=False)
                    script_set_ok = True
                    log('[%s] [Oto-Kervan] Kasılma alanı yoktu; config\'e "Caravan" alanı eklendi, script atandı, bot başlatılıyor.' % pName)
                except Exception as ex:
                    log('[%s] [Oto-Kervan] Config güncellenemedi: %s' % (pName, str(ex)))
            if not script_set_ok:
                log('[%s] [Oto-Kervan] Seçilen script atanamadı. Yol: %s' % (pName, script_path_for_bot))
                _caravan_running = False
                return
        time.sleep(0.3)
        if not get_training_area():
            log('[%s] [Oto-Kervan] Kasılma: Kasılma alanınızı aktif etmediniz. Bot başlatılamıyor.' % pName)
            _caravan_running = False
            QtBind.setText(gui, lblKervanStatus, 'Durum: Durduruldu ■')
            return
        start_bot()
        _caravan_running = True
        log('[%s] [Oto-Kervan] Karavan scripti dosyadan çalışıyor (training script).' % pName)
        while not _caravan_stop_event.is_set():
            time.sleep(1)
        log('[%s] [Oto-Kervan] Karavan durduruluyor...' % pName)
        stop_bot()
        _caravan_running = False
    except Exception as ex:
        log('[%s] [Oto-Kervan] Hata: %s' % (pName, str(ex)))
        _caravan_running = False
        try:
            stop_bot()
        except Exception:
            pass
    finally:
        if backup_path:
            _caravan_restore_from_backup(backup_path)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def kervan_start():
    global _caravan_script_path, _caravan_thread
    # Profil kontrolü: karavan profili seçili olmalı
    try:
        path = get_config_path()
        if not path:
            log('[%s] [Oto-Kervan] Profil bilgisi alınamadı. Botu tekrar açıp oyuna giriş yapın.' % pName)
            QtBind.setText(gui, lblKervanStatus, 'Durum: Profil alınamadı')
            return
        profile_name = os.path.basename(path)
        if profile_name.endswith('.json'):
            profile_name = profile_name[:-5]
        if 'karavan' not in profile_name.lower():
            log('[%s] [Oto-Kervan] Karavan profili seçili değil! Ana pencereden karavan profilini seçin, sonra Başlat\'a basın.' % pName)
            QtBind.setText(gui, lblKervanStatus, 'Durum: Karavan profili seçili değil!')
            return
    except Exception:
        log('[%s] [Oto-Kervan] Profil kontrolü yapılamadı.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Profil kontrolü hatası')
        return
    
    selected_display = QtBind.text(gui, lstKervanScripts).strip()
    if not selected_display or selected_display.startswith('('):
        log('[%s] [Oto-Kervan] Lütfen listeden bir script seçin.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Önce script seçin')
        return
    # Gösterim adından dosya adını bul (örn. "Hotan --> Jangan" -> 8a_Hotan_to_Jangan.txt)
    selected = None
    for fname in _caravan_script_list:
        if _caravan_filename_to_display_name(fname) == selected_display:
            selected = fname
            break
    if not selected:
        log('[%s] [Oto-Kervan] Seçim eşleşmedi; listeyi Yenile ile tekrar yükleyin.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Listeyi yenileyin')
        return
    folder = _get_caravan_script_folder()
    script_path = os.path.join(folder, selected)
    if not os.path.exists(script_path):
        QtBind.setText(gui, lblKervanStatus, 'Durum: İndiriliyor...')
        script_path = _download_caravan_script(selected)
        if not script_path:
            QtBind.setText(gui, lblKervanStatus, 'Durum: İndirilemedi!')
            return
    _caravan_script_path = script_path
    with _caravan_lock:
        if _caravan_thread and _caravan_thread.is_alive():
            QtBind.setText(gui, lblKervanStatus, 'Durum: Zaten çalışıyor')
            return
        _caravan_stop_event.clear()
        _caravan_thread = threading.Thread(target=_caravan_loop, name=pName + '_caravan', daemon=True)
        _caravan_thread.start()
    QtBind.setText(gui, lblKervanStatus, 'Durum: Çalışıyor... ▶')
    log('[%s] [Oto-Kervan] Başlatıldı: %s' % (pName, selected))

def kervan_stop():
    global _caravan_thread, _caravan_running
    try:
        stop_bot()
    except Exception:
        pass
    with _caravan_lock:
        _caravan_stop_event.set()
        if _caravan_thread and _caravan_thread.is_alive():
            _caravan_thread.join(timeout=3)
        _caravan_thread = None
        _caravan_running = False
    QtBind.setText(gui, lblKervanStatus, 'Durum: Durduruldu ■')
    log('[%s] [Oto-Kervan] Durduruldu.' % pName)

# ______________________________ Auto Dungeon Fonksiyonları ______________________________ #

def getPath():
    return get_config_dir() + pName + "\\"

def getConfig():
    return getPath() + character_data['server'] + "_" + character_data['name'] + ".json"

def isJoined():
    global character_data
    character_data = get_character_data()
    if not (character_data and "name" in character_data and character_data["name"]):
        character_data = None
    return character_data

def ListContains(text, lst):
    text = text.lower()
    for i in range(len(lst)):
        if lst[i].lower() == text:
            return True
    return False

def GetDistance(ax, ay, bx, by):
    return ((bx - ax) ** 2 + (by - ay) ** 2) ** (0.5)

def GetFilterConnection():
    path = get_config_dir() + character_data['server'] + '_' + character_data['name'] + '.db3'
    return sqlite3.connect(path)

def IsPickable(filterCursor, ItemID):
    return filterCursor.execute('SELECT EXISTS(SELECT 1 FROM pickfilter WHERE id=? AND pick=1 LIMIT 1)', (ItemID,)).fetchone()[0]

def WaitPickableDrops(filterCursor, waiting=0):
    if waiting >= WAIT_DROPS_DELAY_MAX:
        log('[%s] Dropları bekleme süresi doldu!' % pName)
        return
    drops = get_drops()
    if drops:
        drop = None
        for key in drops:
            value = drops[key]
            if IsPickable(filterCursor, value['model']):
                drop = value
                break
        if drop:
            log('[%s] "%s" toplanması bekleniyor...' % (pName, drop['name']))
            time.sleep(1.0)
            WaitPickableDrops(filterCursor, waiting + 1)

def getMobCount(position, radius):
    QtBind.clear(gui, lstMonsterCounter)
    QtBind.append(gui, lstMonsterCounter, 'İsim (Tür)')
    count = 0
    p = position if radius != None else None
    monsters = get_monsters()
    if monsters:
        for key, mob in monsters.items():
            if mob['type'] in lstIgnore:
                continue
            if len(lstOnlyCount) > 0:
                if not mob['type'] in lstOnlyCount:
                    continue
            elif ListContains(mob['name'], lstMobsData):
                continue
            if radius != None:
                if round(GetDistance(p['x'], p['y'], mob['x'], mob['y']), 2) > radius:
                    continue
            QtBind.append(gui, lstMonsterCounter, mob['name'] + ' (' + str(mob['type']) + ')')
            count += 1
    return count

def AttackMobs(wait, isAttacking, position, radius):
    count = getMobCount(position, radius)
    if count > 0:
        if not isAttacking:
            start_bot()
            log("[%s] Bu bölgede (%d) canavar öldürülüyor. Yarıçap: %s" % (pName, count, str(radius) if radius != None else "Max."))
        threading.Timer(wait, AttackMobs, [wait, True, position, radius]).start()
    else:
        log("[%s] Tüm canavarlar öldürüldü!" % pName)
        conn = GetFilterConnection()
        cursor = conn.cursor()
        WaitPickableDrops(cursor)
        conn.close()
        stop_bot()
        set_training_position(0, 0, 0, 0)
        log("[%s] Script konumuna geri dönülüyor..." % pName)
        threading.Timer(2.5, move_to, [position['x'], position['y'], position['z']]).start()
        threading.Timer(5.0, start_bot).start()

def AttackArea(args):
    radius = None
    if len(args) >= 2:
        radius = round(float(args[1]), 2)
    p = get_position()
    if getMobCount(p, radius) > 0:
        stop_bot()
        set_training_position(p['region'], p['x'], p['y'], p['z'])
        if radius != None:
            set_training_radius(radius)
        else:
            set_training_radius(100.0)
        threading.Timer(0.001, AttackMobs, [COUNT_MOBS_DELAY, False, p, radius]).start()
    else:
        log("[%s] Bu bölgede canavar yok. Yarıçap: %s" % (pName, str(radius) if radius != None else "Max."))
    return 0

def GetDimensionalHole(Name):
    searchByName = Name != ''
    items = get_inventory()['items']
    for slot, item in enumerate(items):
        if item:
            match = False
            if searchByName:
                match = (Name == item['name'])
            else:
                itemData = get_item(item['model'])
                match = (itemData['tid1'] == 3 and itemData['tid2'] == 12 and itemData['tid3'] == 7)
            if match:
                item['slot'] = slot
                return item
    return None

def GetDimensionalPillarUID(Name):
    npcs = get_npcs()
    if npcs:
        for uid, npc in npcs.items():
            item = get_item(npc['model'])
            if item and item['name'] == Name:
                return uid
    return 0

def EnterToDimensional(Name):
    uid = GetDimensionalPillarUID(Name)
    if uid:
        log('[%s] Boyutsal delik seçiliyor...' % pName)
        packet = struct.pack('I', uid)
        inject_joymax(0x7045, packet, False)
        time.sleep(1.0)
        log('[%s] Boyutsal deliğe giriliyor...' % pName)
        inject_joymax(0x704B, packet, False)
        packet += struct.pack('H', 3)
        inject_joymax(0x705A, packet, False)
        threading.Timer(5.0, start_bot).start()
        return
    log('[%s] "%s" yakınınızda bulunamadı!' % (pName, Name))

def GoDimensionalThread(Name):
    if dimensionalItemActivated:
        Name = dimensionalItemActivated['name']
        log('[%s] %s hala açık!' % (pName, '"' + Name + '"' if Name else 'Boyutsal Delik'))
        EnterToDimensional(Name)
        return
    item = GetDimensionalHole(Name)
    if item:
        log('[%s] "%s" kullanılıyor...' % (pName, item['name']))
        p = struct.pack('B', item['slot'])
        locale = get_locale()
        if locale in [56, 18, 61]:
            p += b'\x30\x0C\x0C\x07'
        else:
            p += b'\x6C\x3E'
        global itemUsedByPlugin
        itemUsedByPlugin = item
        inject_joymax(0x704C, p, True)
    else:
        log('[%s] %s envanterinizde bulunamadı' % (pName, '"' + Name + '"' if Name else 'Boyutsal Delik'))

def GoDimensional(args):
    stop_bot()
    name = ''
    if len(args) > 1:
        name = args[1]
    threading.Timer(0.001, GoDimensionalThread, [name]).start()
    return 0

def btnAddMob_clicked():
    global lstMobsData
    text = QtBind.text(gui, tbxMobs)
    if text and not ListContains(text, lstMobsData):
        lstMobsData.append(text)
        QtBind.append(gui, lstMobs, text)
        QtBind.setText(gui, tbxMobs, "")
        saveConfigs()
        log('[%s] Canavar eklendi [%s]' % (pName, text))

def btnRemMob_clicked():
    global lstMobsData
    selected = QtBind.text(gui, lstMobs)
    if selected:
        lstMobsData.remove(selected)
        QtBind.remove(gui, lstMobs, selected)
        saveConfigs()
        log('[%s] Canavar kaldırıldı [%s]' % (pName, selected))

def Checkbox_Checked(checked, gListName, mobType):
    gListReference = globals()[gListName]
    if checked:
        gListReference.append(mobType)
    else:
        gListReference.remove(mobType)
    saveConfigs()

def cbxIgnoreGeneral_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 0)
def cbxOnlyCountGeneral_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 0)

def cbxIgnoreChampion_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 1)
def cbxOnlyCountChampion_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 1)

def cbxIgnoreGiant_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 4)
def cbxOnlyCountGiant_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 4)

def cbxIgnoreTitan_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 5)
def cbxOnlyCountTitan_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 5)

def cbxIgnoreStrong_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 6)
def cbxOnlyCountStrong_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 6)

def cbxIgnoreElite_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 7)
def cbxOnlyCountElite_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 7)

def cbxIgnoreUnique_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 8)
def cbxOnlyCountUnique_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 8)

def cbxIgnoreParty_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 16)
def cbxOnlyCountParty_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 16)

def cbxIgnoreChampionParty_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 17)
def cbxOnlyCountChampionParty_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 17)

def cbxIgnoreGiantParty_clicked(checked):
    Checkbox_Checked(checked, "lstIgnore", 20)
def cbxOnlyCountGiantParty_clicked(checked):
    Checkbox_Checked(checked, "lstOnlyCount", 20)

def cbxAcceptForgottenWorld_checked(checked):
    saveConfigs()

def loadDefaultConfig():
    global lstMobsData, lstIgnore, lstOnlyCount
    lstMobsData = []
    QtBind.clear(gui, lstMobs)
    lstIgnore = []
    QtBind.setChecked(gui, cbxIgnoreGeneral, False)
    QtBind.setChecked(gui, cbxIgnoreChampion, False)
    QtBind.setChecked(gui, cbxIgnoreGiant, False)
    QtBind.setChecked(gui, cbxIgnoreTitan, False)
    QtBind.setChecked(gui, cbxIgnoreStrong, False)
    QtBind.setChecked(gui, cbxIgnoreElite, False)
    QtBind.setChecked(gui, cbxIgnoreUnique, False)
    QtBind.setChecked(gui, cbxIgnoreParty, False)
    QtBind.setChecked(gui, cbxIgnoreChampionParty, False)
    QtBind.setChecked(gui, cbxIgnoreGiantParty, False)
    lstOnlyCount = []
    QtBind.setChecked(gui, cbxOnlyCountGeneral, False)
    QtBind.setChecked(gui, cbxOnlyCountChampion, False)
    QtBind.setChecked(gui, cbxOnlyCountGiant, False)
    QtBind.setChecked(gui, cbxOnlyCountTitan, False)
    QtBind.setChecked(gui, cbxOnlyCountStrong, False)
    QtBind.setChecked(gui, cbxOnlyCountElite, False)
    QtBind.setChecked(gui, cbxOnlyCountUnique, False)
    QtBind.setChecked(gui, cbxOnlyCountParty, False)
    QtBind.setChecked(gui, cbxOnlyCountChampionParty, False)
    QtBind.setChecked(gui, cbxOnlyCountGiantParty, False)
    QtBind.setChecked(gui, cbxAcceptForgottenWorld, False)

def loadConfigs():
    loadDefaultConfig()
    if isJoined() and os.path.exists(getConfig()):
        data = {}
        with open(getConfig(), "r") as f:
            data = json.load(f)
        if "Ignore Names" in data:
            global lstMobsData
            lstMobsData = data["Ignore Names"]
            for name in lstMobsData:
                QtBind.append(gui, lstMobs, name)
        if "Ignore Types" in data:
            global lstIgnore
            for t in data["Ignore Types"]:
                if t == 8:
                    QtBind.setChecked(gui, cbxIgnoreUnique, True)
                elif t == 7:
                    QtBind.setChecked(gui, cbxIgnoreElite, True)
                elif t == 6:
                    QtBind.setChecked(gui, cbxIgnoreStrong, True)
                elif t == 5:
                    QtBind.setChecked(gui, cbxIgnoreTitan, True)
                elif t == 4:
                    QtBind.setChecked(gui, cbxIgnoreGiant, True)
                elif t == 1:
                    QtBind.setChecked(gui, cbxIgnoreChampion, True)
                elif t == 0:
                    QtBind.setChecked(gui, cbxIgnoreGeneral, True)
                elif t == 16:
                    QtBind.setChecked(gui, cbxIgnoreParty, True)
                elif t == 17:
                    QtBind.setChecked(gui, cbxIgnoreChampionParty, True)
                elif t == 20:
                    QtBind.setChecked(gui, cbxIgnoreGiantParty, True)
                else:
                    continue
                lstIgnore.append(t)
        if "OnlyCount Types" in data:
            global lstOnlyCount
            for t in data["OnlyCount Types"]:
                if t == 8:
                    QtBind.setChecked(gui, cbxOnlyCountUnique, True)
                elif t == 7:
                    QtBind.setChecked(gui, cbxOnlyCountElite, True)
                elif t == 6:
                    QtBind.setChecked(gui, cbxOnlyCountStrong, True)
                elif t == 5:
                    QtBind.setChecked(gui, cbxOnlyCountTitan, True)
                elif t == 4:
                    QtBind.setChecked(gui, cbxOnlyCountGiant, True)
                elif t == 1:
                    QtBind.setChecked(gui, cbxOnlyCountChampion, True)
                elif t == 0:
                    QtBind.setChecked(gui, cbxOnlyCountGeneral, True)
                elif t == 16:
                    QtBind.setChecked(gui, cbxOnlyCountParty, True)
                elif t == 17:
                    QtBind.setChecked(gui, cbxOnlyCountChampionParty, True)
                elif t == 20:
                    QtBind.setChecked(gui, cbxOnlyCountGiantParty, True)
                else:
                    continue
                lstOnlyCount.append(t)
        if 'Accept ForgottenWorld' in data and data['Accept ForgottenWorld']:
            QtBind.setChecked(gui, cbxAcceptForgottenWorld, True)

def saveConfigs():
    if isJoined():
        data = {}
        data['OnlyCount Types'] = lstOnlyCount
        data['Ignore Types'] = lstIgnore
        data['Ignore Names'] = lstMobsData
        data['Accept ForgottenWorld'] = QtBind.isChecked(gui, cbxAcceptForgottenWorld)
        with open(getConfig(), "w") as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

# ______________________________ Script Komutları (TR_ScriptCommands) ______________________________ #

def _script_cmds_ResetSkip():
    global _script_cmds_SkipCommand
    _script_cmds_SkipCommand = False

def LeaveParty(args):
    if get_party():
        inject_joymax(0x7061, b'', False)
        log('[%s] Partiden çıkılıyor' % pName)
    return 0

def Notification(args):
    if len(args) == 3:
        title, message = args[1], args[2]
        show_notification(title, message)
        return 0
    log('[%s] Hatalı Bildirim komutu' % pName)
    return 0

def NotifyList(args):
    if len(args) == 2:
        create_notification(args[1])
        return 0
    log('[%s] Hatalı NotifyList komutu' % pName)
    return 0

def PlaySound(args):
    if len(args) < 2:
        return 0
    fname = args[1]
    if os.path.exists(_script_cmds_path + fname):
        play_wav(_script_cmds_path + fname)
        log('[%s] [%s] oynatılıyor' % (pName, fname))
        return 0
    log('[%s] [%s] ses dosyası mevcut değil' % (pName, fname))
    return 0

def SetScript(args):
    if len(args) < 2:
        return 0
    name = args[1]
    if os.path.exists(_script_cmds_path + name):
        set_training_script(_script_cmds_path + name)
        log('[%s] Komut [%s] olarak değiştirildi' % (pName, name))
        return 0
    log('[%s] [%s] komutu mevcut değil' % (pName, name))
    return 0

def CloseBot(args):
    global _script_cmds_CloseBotAt, _script_cmds_CheckCloseTime
    _script_cmds_CheckCloseTime = True
    if len(args) == 1:
        _script_cmds_Terminate()
        return 0
    if len(args) < 3:
        return 0
    typ, tm = args[1], args[2]
    if typ == 'in':
        _script_cmds_CloseBotAt = str(datetime.now() + timedelta(minutes=int(tm)))[11:16]
        log('[%s] Bot [%s] da kapatılacak' % (pName, _script_cmds_CloseBotAt))
    elif typ == 'at':
        _script_cmds_CloseBotAt = tm
        log('[%s] Bot [%s] da kapatılacak' % (pName, _script_cmds_CloseBotAt))
    return 0

def _script_cmds_Terminate():
    log('[%s] Bot kapatılıyor...' % pName)
    os.kill(os.getpid(), 9)

def GoClientless(args):
    pid = (get_client() or {}).get('pid')
    if pid:
        os.kill(pid, signal.SIGTERM)
        return 0
    log('[%s] İstemci açık değil!' % pName)
    return 0

def StartBot(args):
    global _script_cmds_StartBotAt, _script_cmds_CheckStartTime, _script_cmds_SkipCommand
    if _script_cmds_SkipCommand:
        _script_cmds_SkipCommand = False
        return 0
    stop_bot()
    if len(args) < 3:
        return 0
    typ, tm = args[1], args[2]
    _script_cmds_CheckStartTime = True
    if typ == 'in':
        _script_cmds_StartBotAt = str(datetime.now() + timedelta(minutes=int(tm)))[11:16]
        log('[%s] Bot [%s] da başlatılacak' % (pName, _script_cmds_StartBotAt))
    elif typ == 'at':
        _script_cmds_StartBotAt = tm
        log('[%s] Bot [%s] da başlatılacak' % (pName, _script_cmds_StartBotAt))
    return 0

def StopStart(args):
    global _script_cmds_SkipCommand
    if _script_cmds_SkipCommand:
        _script_cmds_SkipCommand = False
        return 0
    stop_bot()
    threading.Timer(1.0, start_bot, ()).start()
    threading.Timer(30.0, _script_cmds_ResetSkip, ()).start()
    _script_cmds_SkipCommand = True
    return 0

def StartTrace(args):
    global _script_cmds_SkipCommand
    if _script_cmds_SkipCommand:
        _script_cmds_SkipCommand = False
        return 0
    if len(args) == 2:
        stop_bot()
        player = args[1]
        if start_trace(player):
            log('[%s] [%s] takip ediliyor' % (pName, player))
            return 0
        log('[%s] Oyuncu [%s] yakın değil.. Devam ediyor' % (pName, player))
        _script_cmds_SkipCommand = True
        threading.Timer(1.0, start_bot, ()).start()
        threading.Timer(30.0, _script_cmds_ResetSkip, ()).start()
        return 0
    log('[%s] Hatalı StartTrace formatı' % pName)
    return 0

def RemoveSkill(args):
    if len(args) < 2:
        return 0
    rem_skill = args[1]
    skills = get_active_skills()
    if skills:
        for sid, skill in skills.items():
            if skill.get('name') == rem_skill:
                packet = b'\x01\x05' + struct.pack('<I', sid) + b'\x00'
                inject_joymax(0x7074, packet, False)
                log('[%s] [%s] yeteneği kaldırılıyor' % (pName, rem_skill))
                return 0
    log('[%s] Yetenek aktif değil' % pName)
    return 0

def Drop(args):
    if len(args) < 2:
        return 0
    drop_item = args[1]
    inv = get_inventory()
    if not inv or 'items' not in inv:
        return 0
    for slot, item in enumerate(inv['items']):
        if item and item.get('name') == drop_item:
            p = b'\x07' + struct.pack('B', slot)
            log('[%s] [%s][%s] eşyası bırakılıyor' % (pName, item.get('quantity', 1), drop_item))
            inject_joymax(0x7034, p, True)
            return 0
    log('[%s] Bırakılacak eşya yok' % pName)
    return 0

def OpenphBot(args):
    if len(args) < 2:
        return 0
    cmdargs = args[1]
    if os.path.exists(_script_cmds_path + "phBot.exe"):
        subprocess.Popen(_script_cmds_path + "phBot.exe " + cmdargs)
        log('[%s] Yeni bir bot açılıyor' % pName)
        return 0
    log('[%s] Geçersiz bot yolu' % pName)
    return 0

def DismountPet(args):
    if len(args) < 2:
        return 0
    pet_type = args[1].lower()
    if pet_type == 'pick':
        log('[%s] Pick pet inemez' % pName)
        return 0
    pets = get_pets()
    if pets:
        for pid, pet in pets.items():
            if pet.get('type') == pet_type:
                p = b'\x00' + struct.pack('I', pid)
                inject_joymax(0x70CB, p, False)
                return 0
    return 0

def UnsummonPet(args):
    if len(args) < 2:
        return 0
    pet_type = args[1].lower()
    pets = get_pets()
    if pets:
        for pid, pet in pets.items():
            if pet.get('type') == pet_type:
                p = struct.pack('I', pid)
                if pet_type in ('transport', 'horse'):
                    inject_joymax(0x70C6, p, False)
                else:
                    inject_joymax(0x7116, p, False)
                log('[%s] [%s] pet geri çağrılıyor' % (pName, pet_type))
                return 0
    return 0

def ResetWeapons(args):
    items = 'all'
    if len(args) == 2:
        items = args[1].lower()
    cfg_path = get_config_dir()
    char_data = get_character_data()
    if not char_data:
        return 0
    profile = get_profile()
    cfg_file = "%s_%s.%s.json" % (char_data['server'], char_data['name'], profile) if profile else "%s_%s.json" % (char_data['server'], char_data['name'])
    cfg_path = os.path.join(cfg_path, cfg_file)
    if not os.path.exists(cfg_path):
        return 0
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if 'Inventory' not in cfg:
            cfg['Inventory'] = {"Primary": 0, "Secondary": 0, "Shield": 0}
        if items == 'all':
            cfg['Inventory'] = {"Primary": 0, "Secondary": 0, "Shield": 0}
        elif items == 'primary':
            cfg['Inventory']['Primary'] = 0
        elif items == 'secondary':
            cfg['Inventory']['Secondary'] = 0
        elif items == 'shield':
            cfg['Inventory']['Shield'] = 0
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(cfg, indent=4, ensure_ascii=False))
        log('[%s] Silahlar sıfırlandı' % pName)
        set_profile(profile)
    except Exception:
        pass
    return 0

def SetArea(args):
    if len(args) == 2:
        set_training_area(args[1])
        log('[%s] Eğitim alanı [%s] olarak değiştirildi' % (pName, args[1]))
        return 0
    log('[%s] Lütfen bir eğitim alanı ismi belirtin' % pName)
    return 0

def _script_cmds_CalcRadiusFromME(px, py):
    my = get_position()
    if not my:
        return 999
    return ((my['x'] - px) ** 2 + (my['y'] - py) ** 2) ** 0.5

def ExchangePlayer(args):
    if len(args) != 2:
        log('[%s] Lütfen takas yapılacak bir oyuncu belirtin' % pName)
        return 0
    player_name = args[1]
    party = get_party()
    if not party:
        log('[%s] Partide değilsiniz, takas yapılamaz' % pName)
        return 0
    for key, player in party.items():
        if player.get('name') == player_name:
            radius = _script_cmds_CalcRadiusFromME(player['x'], player['y'])
            if player.get('player_id', 0) <= 0 or radius > 20:
                log('[%s] Oyuncu [%s] menzil dışında! Takas yapılamaz' % (pName, player['name']))
                return 0
            log('[%s] [%s] ile takas başlatılıyor' % (pName, player['name']))
            p = struct.pack('<I', player['player_id'])
            inject_joymax(0x7081, p, True)
            return 0
    log('[%s] Oyuncu [%s] partide değil! Takas yapılamaz' % (pName, player_name))
    return 0

def ChangeBotOption(args):
    if len(args) < 4 or len(args) > 6:
        log('[%s] Hatalı format, ayar değiştirilemiyor.' % pName)
        return 0
    value = args[1]
    cfg_path = get_config_dir()
    char_data = get_character_data()
    if not char_data:
        return 0
    profile = get_profile()
    cfg_file = "%s_%s.%s.json" % (char_data['server'], char_data['name'], profile) if profile else "%s_%s.json" % (char_data['server'], char_data['name'])
    cfg_path = os.path.join(cfg_path, cfg_file)
    if not os.path.exists(cfg_path):
        return 0
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        keys = args[2:]
        try:
            cur = cfg
            for k in keys[:-1]:
                cur = cur[k]
            if isinstance(cur.get(keys[-1]), list):
                cur[keys[-1]].append(value)
            else:
                cur[keys[-1]] = value
        except (KeyError, TypeError):
            log('[%s] Hatalı json anahtarı, ayar değiştirilemiyor' % pName)
            return 0
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(cfg, indent=4, ensure_ascii=False))
        log('[%s] Ayarlar başarıyla değiştirildi' % pName)
        set_profile(profile)
    except Exception:
        pass
    return 0

def _script_cmds_GetPackets(name):
    global _script_cmds_ExecutedPackets
    custom_path = _script_cmds_path + "CustomNPC.json"
    if not os.path.exists(custom_path):
        return
    with open(custom_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if name in data:
        _script_cmds_ExecutedPackets = data[name].get('Packets', [])

def _script_cmds_SaveNPCPackets(name, packets=None):
    if packets is None:
        packets = []
    custom_path = _script_cmds_path + "CustomNPC.json"
    data = {}
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[name] = {"Packets": packets}
    with open(custom_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))
    log('[%s] Özel NPC Komutu Kaydedildi' % pName)

def CustomNPC(args):
    global _script_cmds_SkipCommand, _script_cmds_StopBot
    if _script_cmds_SkipCommand:
        _script_cmds_SkipCommand = False
        return 0
    if len(args) < 2:
        log('[%s] Geçersiz komut, CustomNPC,savedname,state kullanın' % pName)
        return 0
    _script_cmds_StopBot = True
    if len(args) == 3:
        state = args[2].lower()
        _script_cmds_StopBot = (state == 'true')
    if _script_cmds_StopBot:
        stop_bot()
    name = args[1]
    _script_cmds_GetPackets(name)
    threading.Timer(0.5, _script_cmds_InjectPackets, ()).start()
    return 0

def _script_cmds_InjectPackets():
    global _script_cmds_Index, _script_cmds_ExecutedPackets
    if not _script_cmds_ExecutedPackets:
        return
    parts = _script_cmds_ExecutedPackets[_script_cmds_Index].split(':')
    opcode = int(parts[0], 16)
    data_str = parts[1].replace(' ', '') if len(parts) > 1 else ''
    data = bytearray()
    for i in range(0, len(data_str), 2):
        data.append(int(data_str[i:i+2], 16))
    inject_joymax(opcode, bytes(data), False)
    if _script_cmds_cbxShowPackets is not None and QtBind.isChecked(gui, _script_cmds_cbxShowPackets):
        log('[%s] Enjekte Edildi (Opcode) 0x%02X (Veri) %s' % (pName, opcode, 'None' if not data else ' '.join('%02X' % x for x in data)))
    num_packets = len(_script_cmds_ExecutedPackets) - 1
    if _script_cmds_Index < num_packets:
        _script_cmds_Index += 1
        threading.Timer(2.0, _script_cmds_InjectPackets, ()).start()
    else:
        global _script_cmds_SkipCommand
        log('[%s] Özel NPC Komutu Tamamlandı' % pName)
        _script_cmds_Index = 0
        _script_cmds_ExecutedPackets = []
        threading.Timer(30.0, _script_cmds_ResetSkip, ()).start()
        _script_cmds_SkipCommand = True
        if _script_cmds_StopBot:
            start_bot()

gui = QtBind.init(__name__, pName)

# Lisans kontrol sistemi
_license_valid_cache = False
_protected_buttons = {}  # {tab_number: [button_refs]}

def _is_license_valid():
    """Lisans geçerli mi kontrol eder"""
    global _license_valid_cache
    return _license_valid_cache

def _update_license_status(is_valid):
    """Lisans durumunu günceller ve butonları enable/disable eder"""
    global _license_valid_cache
    _license_valid_cache = is_valid
    _update_all_buttons_state()

def _update_all_buttons_state():
    """Tüm korumalı butonların durumunu günceller"""
    is_valid = _is_license_valid()
    for tab_num, buttons in _protected_buttons.items():
        for btn in buttons:
            try:
                QtBind.setEnabled(gui, btn, is_valid)
            except:
                pass

TAB_OFFSCREEN = -3000
_tab1_widgets = []
_tab2_widgets = []
_tab3_widgets = []
_tab4_widgets = []
_tab5_widgets = []
_tab6_widgets = []
_tab7_widgets = []
_tab8_widgets = []
_current_tab = 1
_tab_scroll_offset = 0

def _tab_move(widget_list, offscreen):
    for w, x, y in widget_list:
        try:
            QtBind.move(gui, w, TAB_OFFSCREEN if offscreen else x, TAB_OFFSCREEN if offscreen else y)
        except Exception:
            pass

def _show_tab1():
    global _current_tab
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab1_widgets, False)
    _current_tab = 1
    _tab_apply_scroll()

def _show_tab2():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab2_widgets, False)
    _current_tab = 2
    _tab_apply_scroll()

def _show_tab3():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab3_widgets, False)
    _current_tab = 3
    _tab_apply_scroll()

def _show_tab4():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab4_widgets, False)
    _current_tab = 4
    _tab_apply_scroll()

def _show_tab5():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab5_widgets, False)
    _current_tab = 5
    _tab_apply_scroll()

def _show_tab6():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab6_widgets, False)
    _current_tab = 6
    _tab_apply_scroll()

def _add_tab1(w, x, y):
    _tab1_widgets.append((w, x, y))

def _add_tab2(w, x, y):
    _tab2_widgets.append((w, x, y))

def _add_tab3(w, x, y):
    _tab3_widgets.append((w, x, y))

def _add_tab4(w, x, y):
    _tab4_widgets.append((w, x, y))

def _add_tab5(w, x, y):
    _tab5_widgets.append((w, x, y))

def _add_tab6(w, x, y):
    _tab6_widgets.append((w, x, y))

def _show_tab7():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab7_widgets, False)
    _current_tab = 7
    _tab_apply_scroll()

def _show_tab8():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, False)
    _current_tab = 8
    _tab_apply_scroll()

def _add_tab7(w, x, y):
    _tab7_widgets.append((w, x, y))

def _add_tab8(w, x, y):
    _tab8_widgets.append((w, x, y))

# Tab bar yapılandırması
_tab_bar_y = 10
_tab_bar_x = 10
_tab_visible_width = 552
_tab_scroll_offset = 0

_tab_original_positions = [10, 125, 208, 303, 383, 463, 551, 643]
_tab_widths = [115, 83, 95, 80, 80, 88, 92, 60]

_tab_btn1 = QtBind.createButton(gui, '_show_tab1', 'Banka/Çanta Birleştir', 10, _tab_bar_y)
_tab_btn2 = QtBind.createButton(gui, '_show_tab2', 'Auto Dungeon', 125, _tab_bar_y)
_tab_btn3 = QtBind.createButton(gui, '_show_tab3', 'Garden Dungeon', 208, _tab_bar_y)
_tab_btn4 = QtBind.createButton(gui, '_show_tab4', 'Auto Hwt', 303, _tab_bar_y)
_tab_btn5 = QtBind.createButton(gui, '_show_tab5', 'Oto Kervan', 383, _tab_bar_y)
_tab_btn6 = QtBind.createButton(gui, '_show_tab6', 'Script Komutları', 463, _tab_bar_y)
_tab_btn7 = QtBind.createButton(gui, '_show_tab7', 'Envanter Sayacı', 551, _tab_bar_y)
_tab_btn8 = QtBind.createButton(gui, '_show_tab8', 'Hakkımda', 643, _tab_bar_y)

_tab_buttons = [_tab_btn1, _tab_btn2, _tab_btn3, _tab_btn4, _tab_btn5, _tab_btn6, _tab_btn7, _tab_btn8]

def _tab_apply_scroll():
    for i in range(len(_tab_buttons)):
        new_x = _tab_original_positions[i] - _tab_scroll_offset
        if new_x > _tab_visible_width:
            new_x = TAB_OFFSCREEN
        try:
            QtBind.move(gui, _tab_buttons[i], new_x, _tab_bar_y)
        except Exception:
            pass

def _tab_scroll_left():
    global _tab_scroll_offset
    for i in range(len(_tab_buttons) - 1, -1, -1):
        btn_x = _tab_original_positions[i] - _tab_scroll_offset
        if btn_x < 0:
            _tab_scroll_offset = _tab_original_positions[i]
            _tab_apply_scroll()
            return
    _tab_scroll_offset = 0
    _tab_apply_scroll()

def _tab_scroll_right():
    global _tab_scroll_offset
    for i in range(len(_tab_buttons)):
        btn_x = _tab_original_positions[i] - _tab_scroll_offset
        btn_end = btn_x + _tab_widths[i]
        if btn_end > _tab_visible_width:
            _tab_scroll_offset = _tab_original_positions[i] + _tab_widths[i] - _tab_visible_width
            _tab_apply_scroll()
            return
    total_width = _tab_original_positions[-1] + _tab_widths[-1]
    max_scroll = max(0, total_width - _tab_visible_width)
    _tab_scroll_offset = max_scroll
    _tab_apply_scroll()

_scroll_bg = QtBind.createList(gui, 552, _tab_bar_y, 148, 22)
_scroll_btn_left = QtBind.createButton(gui, '_tab_scroll_left', 'Geri', 552, _tab_bar_y)
_scroll_btn_right = QtBind.createButton(gui, '_tab_scroll_right', 'İleri', 630, _tab_bar_y)

_tab_apply_scroll()

_content_y = _tab_bar_y + 28
_content_container_h = 270
_tab_bar_w = 700
QtBind.createList(gui, _tab_bar_x, _content_y, _tab_bar_w, _content_container_h)

_jewel_y = _content_y + 12
_jewel_w = 280
_jewel_h = 62
_jewel_x = _tab_bar_x + (_tab_bar_w - _jewel_w) // 2

_jewel_container = QtBind.createList(gui, _jewel_x, _jewel_y, _jewel_w, _jewel_h)
_add_tab1(_jewel_container, _jewel_x, _jewel_y)
_add_tab1(QtBind.createLabel(gui, 'So-Ok Event Kullanma', _jewel_x + 70, _jewel_y + 8), _jewel_x + 70, _jewel_y + 8)
_btn_jewel_start = QtBind.createButton(gui, 'jewel_start', 'Başla', _jewel_x + 60, _jewel_y + 32)
_add_tab1(_btn_jewel_start, _jewel_x + 60, _jewel_y + 32)
_btn_jewel_stop = QtBind.createButton(gui, 'jewel_stop', 'Durdur', _jewel_x + 140, _jewel_y + 32)
_add_tab1(_btn_jewel_stop, _jewel_x + 140, _jewel_y + 32)

# Tab 1 butonlarını koruma listesine ekle
_protected_buttons[1] = [_btn_jewel_start, _btn_jewel_stop]

_row2_y = _jewel_y + _jewel_h + 12
_container_w = 280
_container_h = 160
_container_gap = 30
_total_w = _container_w * 2 + _container_gap
_container_start_x = _tab_bar_x + (_tab_bar_w - _total_w) // 2

_inv_container_x = _container_start_x
_bank_container_x = _container_start_x + _container_w + _container_gap

_inv_container = QtBind.createList(gui, _inv_container_x, _row2_y, _container_w, _container_h)
_add_tab1(_inv_container, _inv_container_x, _row2_y)
_add_tab1(QtBind.createLabel(gui, 'Çanta İşlemleri', _inv_container_x + (_container_w - 100) // 2, _row2_y + 8), _inv_container_x + (_container_w - 100) // 2, _row2_y + 8)

_iy1 = _row2_y + 32
_frame2 = QtBind.createList(gui, _inv_container_x + 12, _iy1, _container_w - 24, 50)
_add_tab1(_frame2, _inv_container_x + 12, _iy1)
_add_tab1(QtBind.createLabel(gui, 'Çantayı Birleştir', _inv_container_x + (_container_w - 100) // 2, _iy1 + 5), _inv_container_x + (_container_w - 100) // 2, _iy1 + 5)
_btn_merge_start = QtBind.createButton(gui, 'merge_start', 'Başla', _inv_container_x + (_container_w - 160) // 2, _iy1 + 25)
_add_tab1(_btn_merge_start, _inv_container_x + (_container_w - 160) // 2, _iy1 + 25)
_btn_merge_stop = QtBind.createButton(gui, 'merge_stop', 'Durdur', _inv_container_x + (_container_w - 160) // 2 + 80, _iy1 + 25)
_add_tab1(_btn_merge_stop, _inv_container_x + (_container_w - 160) // 2 + 80, _iy1 + 25)
_protected_buttons[1].extend([_btn_merge_start, _btn_merge_stop])

_iy2 = _iy1 + 58
_frame3 = QtBind.createList(gui, _inv_container_x + 12, _iy2, _container_w - 24, 50)
_add_tab1(_frame3, _inv_container_x + 12, _iy2)
_add_tab1(QtBind.createLabel(gui, 'Çantayı Sırala', _inv_container_x + (_container_w - 90) // 2, _iy2 + 5), _inv_container_x + (_container_w - 90) // 2, _iy2 + 5)
_btn_sort_start = QtBind.createButton(gui, 'sort_start', 'Başla', _inv_container_x + (_container_w - 160) // 2, _iy2 + 25)
_add_tab1(_btn_sort_start, _inv_container_x + (_container_w - 160) // 2, _iy2 + 25)
_btn_sort_stop = QtBind.createButton(gui, 'sort_stop', 'Durdur', _inv_container_x + (_container_w - 160) // 2 + 80, _iy2 + 25)
_add_tab1(_btn_sort_stop, _inv_container_x + (_container_w - 160) // 2 + 80, _iy2 + 25)
_protected_buttons[1].extend([_btn_sort_start, _btn_sort_stop])

_bank_container = QtBind.createList(gui, _bank_container_x, _row2_y, _container_w, _container_h)
_add_tab1(_bank_container, _bank_container_x, _row2_y)
_add_tab1(QtBind.createLabel(gui, 'Banka İşlemleri', _bank_container_x + (_container_w - 100) // 2, _row2_y + 8), _bank_container_x + (_container_w - 100) // 2, _row2_y + 8)
_add_tab1(QtBind.createLabel(gui, 'Banka NPC yakındaysa otomatik açılır.', _bank_container_x + (_container_w - 220) // 2 + 25, _row2_y + 24), _bank_container_x + (_container_w - 220) // 2 + 25, _row2_y + 24)

_by1 = _row2_y + 46
_store_merge_frame = QtBind.createList(gui, _bank_container_x + 12, _by1, _container_w - 24, 50)
_add_tab1(_store_merge_frame, _bank_container_x + 12, _by1)
_add_tab1(QtBind.createLabel(gui, 'Bankayı Birleştir', _bank_container_x + (_container_w - 105) // 2, _by1 + 5), _bank_container_x + (_container_w - 105) // 2, _by1 + 5)
_btn_bank_merge_start = QtBind.createButton(gui, 'bank_merge_start', 'Başla', _bank_container_x + (_container_w - 160) // 2, _by1 + 25)
_add_tab1(_btn_bank_merge_start, _bank_container_x + (_container_w - 160) // 2, _by1 + 25)
_btn_bank_merge_stop = QtBind.createButton(gui, 'bank_merge_stop', 'Durdur', _bank_container_x + (_container_w - 160) // 2 + 80, _by1 + 25)
_add_tab1(_btn_bank_merge_stop, _bank_container_x + (_container_w - 160) // 2 + 80, _by1 + 25)
_protected_buttons[1].extend([_btn_bank_merge_start, _btn_bank_merge_stop])

_by2 = _by1 + 58
_store_sort_frame = QtBind.createList(gui, _bank_container_x + 12, _by2, _container_w - 24, 50)
_add_tab1(_store_sort_frame, _bank_container_x + 12, _by2)
_add_tab1(QtBind.createLabel(gui, 'Bankayı Sırala', _bank_container_x + (_container_w - 95) // 2, _by2 + 5), _bank_container_x + (_container_w - 95) // 2, _by2 + 5)
_btn_bank_sort_start = QtBind.createButton(gui, 'bank_sort_start', 'Başla', _bank_container_x + (_container_w - 160) // 2, _by2 + 25)
_add_tab1(_btn_bank_sort_start, _bank_container_x + (_container_w - 160) // 2, _by2 + 25)
_btn_bank_sort_stop = QtBind.createButton(gui, 'bank_sort_stop', 'Durdur', _bank_container_x + (_container_w - 160) // 2 + 80, _by2 + 25)
_add_tab1(_btn_bank_sort_stop, _bank_container_x + (_container_w - 160) // 2 + 80, _by2 + 25)
_protected_buttons[1].extend([_btn_bank_sort_start, _btn_bank_sort_stop])

# Tab 2 - Auto Dungeon
_t2_y = _content_y + 10
_t2_x = _tab_bar_x + 20

# Sol taraf - Canavar isimleri
lblMobs = QtBind.createLabel(gui, '#  Sayılmayacak canavar adları  #\n#       Canavar Sayacından       #', _t2_x, _t2_y)
_add_tab2(lblMobs, _t2_x, _t2_y)
tbxMobs = QtBind.createLineEdit(gui, "", _t2_x, _t2_y + 35, 100, 20)
_add_tab2(tbxMobs, _t2_x, _t2_y + 35)
lstMobs = QtBind.createList(gui, _t2_x, _t2_y + 56, 176, 170)
_add_tab2(lstMobs, _t2_x, _t2_y + 56)
btnAddMob = QtBind.createButton(gui, 'btnAddMob_clicked', "    Ekle    ", _t2_x + 101, _t2_y + 34)
_add_tab2(btnAddMob, _t2_x + 101, _t2_y + 34)
btnRemMob = QtBind.createButton(gui, 'btnRemMob_clicked', "   Kaldır   ", _t2_x + 49, _t2_y + 226)
_add_tab2(btnRemMob, _t2_x + 49, _t2_y + 226)

# Orta - Canavar Sayacı tercihleri
_t2_mid_x = _t2_x + 210
lblPreferences = QtBind.createLabel(gui, '#  Canavar Sayacı tercihleri  #', _t2_mid_x, _t2_y)
_add_tab2(lblPreferences, _t2_mid_x, _t2_y)

_y = _t2_y + 26
lblGeneral = QtBind.createLabel(gui, 'General (0)', _t2_mid_x, _y)
_add_tab2(lblGeneral, _t2_mid_x, _y)
cbxIgnoreGeneral = QtBind.createCheckBox(gui, 'cbxIgnoreGeneral_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreGeneral, _t2_mid_x + 105, _y)
cbxOnlyCountGeneral = QtBind.createCheckBox(gui, 'cbxOnlyCountGeneral_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountGeneral, _t2_mid_x + 165, _y)

_y += 20
lblChampion = QtBind.createLabel(gui, 'Champion (1)', _t2_mid_x, _y)
_add_tab2(lblChampion, _t2_mid_x, _y)
cbxIgnoreChampion = QtBind.createCheckBox(gui, 'cbxIgnoreChampion_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreChampion, _t2_mid_x + 105, _y)
cbxOnlyCountChampion = QtBind.createCheckBox(gui, 'cbxOnlyCountChampion_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountChampion, _t2_mid_x + 165, _y)

_y += 20
lblGiant = QtBind.createLabel(gui, 'Giant (4)', _t2_mid_x, _y)
_add_tab2(lblGiant, _t2_mid_x, _y)
cbxIgnoreGiant = QtBind.createCheckBox(gui, 'cbxIgnoreGiant_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreGiant, _t2_mid_x + 105, _y)
cbxOnlyCountGiant = QtBind.createCheckBox(gui, 'cbxOnlyCountGiant_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountGiant, _t2_mid_x + 165, _y)

_y += 20
lblTitan = QtBind.createLabel(gui, 'Titan (5)', _t2_mid_x, _y)
_add_tab2(lblTitan, _t2_mid_x, _y)
cbxIgnoreTitan = QtBind.createCheckBox(gui, 'cbxIgnoreTitan_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreTitan, _t2_mid_x + 105, _y)
cbxOnlyCountTitan = QtBind.createCheckBox(gui, 'cbxOnlyCountTitan_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountTitan, _t2_mid_x + 165, _y)

_y += 20
lblStrong = QtBind.createLabel(gui, 'Strong (6)', _t2_mid_x, _y)
_add_tab2(lblStrong, _t2_mid_x, _y)
cbxIgnoreStrong = QtBind.createCheckBox(gui, 'cbxIgnoreStrong_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreStrong, _t2_mid_x + 105, _y)
cbxOnlyCountStrong = QtBind.createCheckBox(gui, 'cbxOnlyCountStrong_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountStrong, _t2_mid_x + 165, _y)

_y += 20
lblElite = QtBind.createLabel(gui, 'Elite (7)', _t2_mid_x, _y)
_add_tab2(lblElite, _t2_mid_x, _y)
cbxIgnoreElite = QtBind.createCheckBox(gui, 'cbxIgnoreElite_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreElite, _t2_mid_x + 105, _y)
cbxOnlyCountElite = QtBind.createCheckBox(gui, 'cbxOnlyCountElite_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountElite, _t2_mid_x + 165, _y)

_y += 20
lblUnique = QtBind.createLabel(gui, 'Unique (8)', _t2_mid_x, _y)
_add_tab2(lblUnique, _t2_mid_x, _y)
cbxIgnoreUnique = QtBind.createCheckBox(gui, 'cbxIgnoreUnique_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreUnique, _t2_mid_x + 105, _y)
cbxOnlyCountUnique = QtBind.createCheckBox(gui, 'cbxOnlyCountUnique_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountUnique, _t2_mid_x + 165, _y)

_y += 20
lblParty = QtBind.createLabel(gui, 'Party (16)', _t2_mid_x, _y)
_add_tab2(lblParty, _t2_mid_x, _y)
cbxIgnoreParty = QtBind.createCheckBox(gui, 'cbxIgnoreParty_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreParty, _t2_mid_x + 105, _y)
cbxOnlyCountParty = QtBind.createCheckBox(gui, 'cbxOnlyCountParty_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountParty, _t2_mid_x + 165, _y)

_y += 20
lblChampionParty = QtBind.createLabel(gui, 'ChampionParty (17)', _t2_mid_x, _y)
_add_tab2(lblChampionParty, _t2_mid_x, _y)
cbxIgnoreChampionParty = QtBind.createCheckBox(gui, 'cbxIgnoreChampionParty_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreChampionParty, _t2_mid_x + 105, _y)
cbxOnlyCountChampionParty = QtBind.createCheckBox(gui, 'cbxOnlyCountChampionParty_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountChampionParty, _t2_mid_x + 165, _y)

_y += 20
lblGiantParty = QtBind.createLabel(gui, 'GiantParty (20)', _t2_mid_x, _y)
_add_tab2(lblGiantParty, _t2_mid_x, _y)
cbxIgnoreGiantParty = QtBind.createCheckBox(gui, 'cbxIgnoreGiantParty_clicked', 'Yoksay', _t2_mid_x + 105, _y)
_add_tab2(cbxIgnoreGiantParty, _t2_mid_x + 105, _y)
cbxOnlyCountGiantParty = QtBind.createCheckBox(gui, 'cbxOnlyCountGiantParty_clicked', 'Sadece Say', _t2_mid_x + 165, _y)
_add_tab2(cbxOnlyCountGiantParty, _t2_mid_x + 165, _y)

_y += 30
cbxAcceptForgottenWorld = QtBind.createCheckBox(gui, 'cbxAcceptForgottenWorld_checked', 'Unutulmuş Dünya davetlerini kabul et', _t2_mid_x, _y)
_add_tab2(cbxAcceptForgottenWorld, _t2_mid_x, _y)

# Sağ taraf - Canavar Sayacı
_t2_right_x = _t2_mid_x + 260
lblMonsterCounter = QtBind.createLabel(gui, '#       Canavar Sayacı       #', _t2_right_x, _t2_y)
_add_tab2(lblMonsterCounter, _t2_right_x, _t2_y)
lstMonsterCounter = QtBind.createList(gui, _t2_right_x, _t2_y + 23, 197, 237)
_add_tab2(lstMonsterCounter, _t2_right_x, _t2_y + 23)
QtBind.append(gui, lstMonsterCounter, 'İsim (Tür)')

# Tab 3 - Garden Dungeon
_t3_y = _content_y + 10
_t3_x = _tab_bar_x + 20

_gd_container_w = 380
_gd_container_h = 240
_gd_container_x = _tab_bar_x + (_tab_bar_w - _gd_container_w) // 2
_gd_container_y = _content_y + 15

_gd_container = QtBind.createList(gui, _gd_container_x, _gd_container_y, _gd_container_w, _gd_container_h)
_add_tab3(_gd_container, _gd_container_x, _gd_container_y)

_gd_title_x = _gd_container_x + 20
_gd_title_y = _gd_container_y + 15

# Nasıl Çalışır bölümü
_gd_howto_y = _gd_title_y
_add_tab3(QtBind.createLabel(gui, 'Nasıl Çalışır?', _gd_title_x, _gd_howto_y), _gd_title_x, _gd_howto_y)
_add_tab3(QtBind.createLabel(gui, '1 - Garden Dungeon\'a gir', _gd_title_x + 10, _gd_howto_y + 20), _gd_title_x + 10, _gd_howto_y + 20)
_add_tab3(QtBind.createLabel(gui, '2 - Script gir (isteğe bağlı) ya da direkt Başlat\'a bas', _gd_title_x + 10, _gd_howto_y + 36), _gd_title_x + 10, _gd_howto_y + 36)

_gd_script_y = _gd_howto_y + 65
_add_tab3(QtBind.createLabel(gui, 'Script Dosya Yolu (boş bırakırsan varsayılan):', _gd_title_x, _gd_script_y), _gd_title_x, _gd_script_y)
tbxGardenScriptPath = QtBind.createLineEdit(gui, "", _gd_title_x, _gd_script_y + 18, 310, 20)
_add_tab3(tbxGardenScriptPath, _gd_title_x, _gd_script_y + 18)

# Script türü seçim butonları (üstte)
_gd_type_y = _gd_script_y + 48
_gd_btn_center_x = _gd_container_x + (_gd_container_w - 170) // 2
_add_tab3(QtBind.createButton(gui, 'garden_dungeon_select_wizz_cleric', 'Wizz/Cleric', _gd_btn_center_x, _gd_type_y), _gd_btn_center_x, _gd_type_y)
_add_tab3(QtBind.createButton(gui, 'garden_dungeon_select_normal', 'Normal', _gd_btn_center_x + 85, _gd_type_y), _gd_btn_center_x + 85, _gd_type_y)

# Başla/Durdur butonları (altta, hizalı)
_gd_btn_y = _gd_type_y + 30
_add_tab3(QtBind.createButton(gui, 'garden_dungeon_start', '  Başla  ', _gd_btn_center_x, _gd_btn_y), _gd_btn_center_x, _gd_btn_y)
_add_tab3(QtBind.createButton(gui, 'garden_dungeon_stop', ' Durdur ', _gd_btn_center_x + 85, _gd_btn_y), _gd_btn_center_x + 85, _gd_btn_y)

_gd_status_y = _gd_btn_y + 30
lblGardenScriptStatus = QtBind.createLabel(gui, 'Durum: Hazır', _gd_title_x, _gd_status_y)
_add_tab3(lblGardenScriptStatus, _gd_title_x, _gd_status_y)

_gd_note_y = _gd_status_y + 22
_add_tab3(QtBind.createLabel(gui, 'Script türünü seç, sonra Başlat', _gd_title_x, _gd_note_y), _gd_title_x, _gd_note_y)

# Tab 4 - Auto Hwt
_hwt_container_w = 380
_hwt_container_h = 240
_hwt_container_x = _tab_bar_x + (_tab_bar_w - _hwt_container_w) // 2
_hwt_container_y = _content_y + 15

_hwt_container = QtBind.createList(gui, _hwt_container_x, _hwt_container_y, _hwt_container_w, _hwt_container_h)
_add_tab4(_hwt_container, _hwt_container_x, _hwt_container_y)

_hwt_title_x = _hwt_container_x + 20
_hwt_title_y = _hwt_container_y + 15

_add_tab4(QtBind.createLabel(gui, 'Auto Hwt', _hwt_title_x, _hwt_title_y), _hwt_title_x, _hwt_title_y)
_add_tab4(QtBind.createLabel(gui, 'Yakında eklenecek...', _hwt_title_x, _hwt_title_y + 30), _hwt_title_x, _hwt_title_y + 30)

# Tab 5 - Oto Kervan (GitHub'dan script listesi, seçilen ile Başla/Durdur)
_kervan_x = _tab_bar_x + 30
_kervan_y = _content_y + 20

# Aktif profil gösterimi
_kervan_profile_y = _kervan_y
_add_tab5(QtBind.createLabel(gui, 'Aktif Profil:', _kervan_x, _kervan_profile_y), _kervan_x, _kervan_profile_y)
lblKervanProfile = QtBind.createLabel(gui, 'Yükleniyor...', _kervan_x + 75, _kervan_profile_y)
_add_tab5(lblKervanProfile, _kervan_x + 75, _kervan_profile_y)

# Script listesi
_kervan_list_y = _kervan_profile_y + 25
_add_tab5(QtBind.createLabel(gui, 'Script listesi:', _kervan_x, _kervan_list_y), _kervan_x, _kervan_list_y)
lstKervanScripts = QtBind.createList(gui, _kervan_x, _kervan_list_y + 20, 400, 120)
_add_tab5(lstKervanScripts, _kervan_x, _kervan_list_y + 20)
QtBind.append(gui, lstKervanScripts, '(Önce "Yenile" ile listeyi yükleyin)')

# Yenile / Başla / Durdur
_kervan_btn_y = _kervan_list_y + 145
_add_tab5(QtBind.createButton(gui, 'kervan_refresh_list', ' Yenile ', _kervan_x, _kervan_btn_y), _kervan_x, _kervan_btn_y)
_add_tab5(QtBind.createButton(gui, 'kervan_start', ' Başla ', _kervan_x + 80, _kervan_btn_y), _kervan_x + 80, _kervan_btn_y)
_add_tab5(QtBind.createButton(gui, 'kervan_stop', ' Durdur ', _kervan_x + 160, _kervan_btn_y), _kervan_x + 160, _kervan_btn_y)

lblKervanStatus = QtBind.createLabel(gui, 'Durum: Hazır', _kervan_x, _kervan_btn_y + 28)
_add_tab5(lblKervanStatus, _kervan_x, _kervan_btn_y + 28)

def _caravan_init_load():
    """Init sonrası karavan profilini (yoksa) oluşturur, ardından script listesini arka planda yükler."""
    time.sleep(2)
    try:
        _caravan_ensure_karavan_profile_on_init()
        kervan_refresh_list()
    except Exception:
        pass
threading.Thread(target=_caravan_init_load, name=pName + '_caravan_init', daemon=True).start()

# Tab 6 - Script Komutları (TR_ScriptCommands)
_sc_x = _tab_bar_x + 20
_sc_y = _content_y + 10
_sc_display_w = 310
_sc_display_h = 180
_sc_btn_row_y = _sc_y + 220
# Liste genişliğinde 3 buton eşit aralıklı: her slot = _sc_display_w / 3
_sc_btn_slot = _sc_display_w // 3
_add_tab6(QtBind.createLabel(gui, 'Kayıt İsmi', _sc_x, _sc_y), _sc_x, _sc_y)
_script_cmds_SaveName = QtBind.createLineEdit(gui, "", _sc_x + 70, _sc_y - 2, 120, 20)
_add_tab6(_script_cmds_SaveName, _sc_x + 70, _sc_y - 2)
_script_cmds_RecordBtn = QtBind.createButton(gui, 'script_cmds_button_start', ' Kaydı Başlat ', _sc_x + 210, _sc_y - 2)
_add_tab6(_script_cmds_RecordBtn, _sc_x + 210, _sc_y - 2)
_script_cmds_Display = QtBind.createList(gui, _sc_x, _sc_y + 30, _sc_display_w, _sc_display_h)
_add_tab6(_script_cmds_Display, _sc_x, _sc_y + 30)
# Üç buton: stroke (liste) genişliği baz alınarak eşit aralıklı (slot 0, 1, 2)
_script_cmds_ShowCommandsBtn = QtBind.createButton(gui, 'script_cmds_button_ShowCmds', ' Komutları Göster ', _sc_x + 0 * _sc_btn_slot, _sc_btn_row_y)
_add_tab6(_script_cmds_ShowCommandsBtn, _sc_x + 0 * _sc_btn_slot, _sc_btn_row_y)
_script_cmds_DeleteCommandsBtn = QtBind.createButton(gui, 'script_cmds_button_DelCmds', '   Komutu Sil   ', _sc_x + 1 * _sc_btn_slot + 5, _sc_btn_row_y)
_add_tab6(_script_cmds_DeleteCommandsBtn, _sc_x + 1 * _sc_btn_slot + 10, _sc_btn_row_y)
_script_cmds_ShowPacketsBtn = QtBind.createButton(gui, 'script_cmds_button_ShowPackets', ' Paketleri Göster ', _sc_x + 2 * _sc_btn_slot, _sc_btn_row_y)
_add_tab6(_script_cmds_ShowPacketsBtn, _sc_x + 2 * _sc_btn_slot, _sc_btn_row_y)
_script_cmds_cbxShowPackets = QtBind.createCheckBox(gui, 'script_cmds_cbxAuto_clicked', 'Paketleri Göster', _sc_x + _sc_display_w + 15, _sc_y - 2)
_add_tab6(_script_cmds_cbxShowPackets, _sc_x + _sc_display_w + 15, _sc_y - 2)
# Açıklama: checkbox altı, strokelu alanın sağına; başlık + metin biraz aşağıda
_sc_desc_x = _sc_x + _sc_display_w + 15
_sc_desc_y0 = _sc_y + 38
_sc_desc_line_h = 14
_add_tab6(QtBind.createLabel(gui, 'Nedir / Nasıl çalışır?', _sc_desc_x, _sc_desc_y0), _sc_desc_x, _sc_desc_y0)
_add_tab6(QtBind.createLabel(gui, '1 - Custom NPC, FGW, ışınlanma, özel işlemler için', _sc_desc_x, _sc_desc_y0 + _sc_desc_line_h + 4), _sc_desc_x, _sc_desc_y0 + _sc_desc_line_h + 4)
_add_tab6(QtBind.createLabel(gui, '   komut dosyasını otomatik oluşturur.', _sc_desc_x, _sc_desc_y0 + 2 * _sc_desc_line_h + 4), _sc_desc_x, _sc_desc_y0 + 2 * _sc_desc_line_h + 4)
_add_tab6(QtBind.createLabel(gui, '2 - Script esnasında kullanırsa bunları gerçekleştirir.', _sc_desc_x, _sc_desc_y0 + 3 * _sc_desc_line_h + 4), _sc_desc_x, _sc_desc_y0 + 3 * _sc_desc_line_h + 4)
_add_tab6(QtBind.createLabel(gui, 'Örn: FGW giriş, FGW partisindeki üyeleri çekme.', _sc_desc_x, _sc_desc_y0 + 4 * _sc_desc_line_h + 4), _sc_desc_x, _sc_desc_y0 + 4 * _sc_desc_line_h + 4)

def script_cmds_button_start():
    global _script_cmds_BtnStart, _script_cmds_RecordedPackets, _script_cmds_Recording
    if len(QtBind.text(gui, _script_cmds_SaveName)) <= 0:
        log('[%s] Lütfen Özel Komut için bir isim girin' % pName)
        return
    if not _script_cmds_BtnStart:
        _script_cmds_BtnStart = True
        QtBind.setText(gui, _script_cmds_RecordBtn, ' Kaydı Durdur ')
        log('[%s] Kayda başlandı, lütfen kayıt için NPC seçin' % pName)
    else:
        log('[%s] Kayıt Tamamlandı' % pName)
        name = QtBind.text(gui, _script_cmds_SaveName)
        _script_cmds_SaveNPCPackets(name, _script_cmds_RecordedPackets)
        _script_cmds_BtnStart = False
        QtBind.setText(gui, _script_cmds_RecordBtn, ' Kaydı Başlat ')
        _script_cmds_Recording = False
        _script_cmds_RecordedPackets = []
        threading.Timer(1.0, script_cmds_button_ShowCmds, ()).start()

def script_cmds_button_ShowCmds():
    QtBind.clear(gui, _script_cmds_Display)
    custom_path = _script_cmds_path + "CustomNPC.json"
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for name in data:
                QtBind.append(gui, _script_cmds_Display, name)
    else:
        log('[%s] Şu anda kaydedilmiş komut yok' % pName)

def script_cmds_button_DelCmds():
    name = QtBind.text(gui, _script_cmds_Display)
    QtBind.clear(gui, _script_cmds_Display)
    custom_path = _script_cmds_path + "CustomNPC.json"
    if not name:
        return
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if name in data:
            del data[name]
            with open(custom_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=4, ensure_ascii=False))
            log('[%s] Özel NPC Komutu [%s] silindi' % (pName, name))
        else:
            log('[%s] Özel NPC Komutu [%s] mevcut değil' % (pName, name))
        threading.Timer(1.0, script_cmds_button_ShowCmds, ()).start()

def script_cmds_button_ShowPackets():
    name = QtBind.text(gui, _script_cmds_Display)
    QtBind.clear(gui, _script_cmds_Display)
    custom_path = _script_cmds_path + "CustomNPC.json"
    if not name or not os.path.exists(custom_path):
        return
    with open(custom_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if name in data:
        for packet in data[name].get('Packets', []):
            QtBind.append(gui, _script_cmds_Display, packet)

def script_cmds_cbxAuto_clicked(checked):
    pass

# Tab 7 - Envanter Sayacı (TR_InventoryCounter)
_inv_cnt_name = 'Santa-So-Ok-DaRKWoLVeS_EnvanterSayaci'
_inv_cnt_inGame = None
_inv_cnt_selected_chat_channel = "PrivateSender"
_inv_cnt_target_private_name = ""

_ic_x = _tab_bar_x + 15
_ic_y = _content_y + 8
_ic_list_w = 430
_ic_list_h = 195
_inv_cnt_btn_row1_y = _ic_y + 2
_inv_cnt_btn_dx = 82
_inv_cnt_btnkarakter = QtBind.createButton(gui, 'inv_cnt_btnkarakter_clicked', ' Karakter ', _ic_x, _inv_cnt_btn_row1_y)
_add_tab7(_inv_cnt_btnkarakter, _ic_x, _inv_cnt_btn_row1_y)
_inv_cnt_btnelixir = QtBind.createButton(gui, 'inv_cnt_btnelixir_clicked', ' Elixir ', _ic_x + _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_add_tab7(_inv_cnt_btnelixir, _ic_x + _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_inv_cnt_btnevent = QtBind.createButton(gui, 'inv_cnt_btnevent_clicked', ' Event ', _ic_x + 2 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_add_tab7(_inv_cnt_btnevent, _ic_x + 2 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_inv_cnt_btncoin = QtBind.createButton(gui, 'inv_cnt_btncoin_clicked', ' Coin ', _ic_x + 3 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_add_tab7(_inv_cnt_btncoin, _ic_x + 3 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_inv_cnt_btnstone = QtBind.createButton(gui, 'inv_cnt_btnstone_clicked', ' Stone ', _ic_x + 4 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_add_tab7(_inv_cnt_btnstone, _ic_x + 4 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_inv_cnt_btnfgw = QtBind.createButton(gui, 'inv_cnt_btnfgw_clicked', ' FGW ', _ic_x + 5 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_add_tab7(_inv_cnt_btnfgw, _ic_x + 5 * _inv_cnt_btn_dx, _inv_cnt_btn_row1_y)
_inv_cnt_btnegpty = QtBind.createButton(gui, 'inv_cnt_btnegpty_clicked', ' Egpty ', _ic_x, _inv_cnt_btn_row1_y + 22)
_add_tab7(_inv_cnt_btnegpty, _ic_x, _inv_cnt_btn_row1_y + 22)
_inv_cnt_btnstall = QtBind.createButton(gui, 'inv_cnt_btnstall_clicked', ' Stall ', _ic_x + _inv_cnt_btn_dx, _inv_cnt_btn_row1_y + 22)
_add_tab7(_inv_cnt_btnstall, _ic_x + _inv_cnt_btn_dx, _inv_cnt_btn_row1_y + 22)
_ic_right_x = _ic_x + _ic_list_w + 65
_inv_cnt_tbxLeaders = QtBind.createLineEdit(gui, "", _ic_right_x, _ic_y, 85, 20)
_add_tab7(_inv_cnt_tbxLeaders, _ic_right_x, _ic_y)
_inv_cnt_btnAddLeader = QtBind.createButton(gui, 'inv_cnt_btnAddLeader_clicked', "Lider Ekle", _ic_right_x + 95, _ic_y - 2)
_add_tab7(_inv_cnt_btnAddLeader, _ic_right_x + 95, _ic_y - 2)
_inv_cnt_lstLeaders = QtBind.createList(gui, _ic_right_x, _ic_y + 22, 85, 65)
_add_tab7(_inv_cnt_lstLeaders, _ic_right_x, _ic_y + 22)
_inv_cnt_btnRemLeader = QtBind.createButton(gui, 'inv_cnt_btnRemLeader_clicked', "Lider Sil", _ic_right_x + 95, _ic_y + 22)
_add_tab7(_inv_cnt_btnRemLeader, _ic_right_x + 95, _ic_y + 22)
_inv_cnt_btnClearInfo = QtBind.createButton(gui, 'inv_cnt_btnClearInfo_clicked', "Temizle", _ic_right_x + 95, _ic_y + 88)
_add_tab7(_inv_cnt_btnClearInfo, _ic_right_x + 95, _ic_y + 88)
_ic_chat_y = _ic_y + 95
_add_tab7(QtBind.createLabel(gui, 'Yanıt Kanalı:', _ic_right_x, _ic_chat_y), _ic_right_x, _ic_chat_y)
_inv_cnt_cbxAllChat = QtBind.createCheckBox(gui, "inv_cnt_cbxAllChat_clicked", "Genel", _ic_right_x, _ic_chat_y + 20)
_add_tab7(_inv_cnt_cbxAllChat, _ic_right_x, _ic_chat_y + 20)
_inv_cnt_cbxPartyChat = QtBind.createCheckBox(gui, "inv_cnt_cbxPartyChat_clicked", "Parti", _ic_right_x, _ic_chat_y + 36)
_add_tab7(_inv_cnt_cbxPartyChat, _ic_right_x, _ic_chat_y + 36)
_inv_cnt_cbxGuildChat = QtBind.createCheckBox(gui, "inv_cnt_cbxGuildChat_clicked", "Guild", _ic_right_x, _ic_chat_y + 52)
_add_tab7(_inv_cnt_cbxGuildChat, _ic_right_x, _ic_chat_y + 52)
_inv_cnt_cbxUnionChat = QtBind.createCheckBox(gui, "inv_cnt_cbxUnionChat_clicked", "Birlik", _ic_right_x, _ic_chat_y + 68)
_add_tab7(_inv_cnt_cbxUnionChat, _ic_right_x, _ic_chat_y + 68)
_inv_cnt_cbxPrivateChatSender = QtBind.createCheckBox(gui, "inv_cnt_cbxPrivateChatSender_clicked", "Özel (Lider)", _ic_right_x, _ic_chat_y + 84)
_add_tab7(_inv_cnt_cbxPrivateChatSender, _ic_right_x, _ic_chat_y + 84)
_inv_cnt_cbxPrivateChatTarget = QtBind.createCheckBox(gui, "inv_cnt_cbxPrivateChatTarget_clicked", "Özel (Hedef)", _ic_right_x, _ic_chat_y + 100)
_add_tab7(_inv_cnt_cbxPrivateChatTarget, _ic_right_x, _ic_chat_y + 100)
_inv_cnt_tbxTargetPrivate = QtBind.createLineEdit(gui, "", _ic_right_x, _ic_chat_y + 122, 85, 20)
_add_tab7(_inv_cnt_tbxTargetPrivate, _ic_right_x, _ic_chat_y + 122)
_inv_cnt_btnSaveChatSettings = QtBind.createButton(gui, 'inv_cnt_btnSaveChatSettings_clicked', "Kaydet", _ic_right_x + 95, _ic_chat_y + 20)
_add_tab7(_inv_cnt_btnSaveChatSettings, _ic_right_x + 95, _ic_chat_y + 20)
_inv_cnt_lstInfo = QtBind.createList(gui, _ic_x, _ic_y + 50, _ic_list_w, _ic_list_h)
_add_tab7(_inv_cnt_lstInfo, _ic_x, _ic_y + 50)
QtBind.append(gui, _inv_cnt_lstInfo, "   Envanter Sayacı - Lider ekleyip sohbetten komut gönderin (ENV, DEPO, GOLD, EXP, SOX vb.).")
QtBind.append(gui, _inv_cnt_lstInfo, "   Komut listesi için üstteki butonlara tıklayın.")

def inv_cnt_getPath():
    return get_config_dir() + _inv_cnt_name + "\\"

def inv_cnt_getConfig():
    return inv_cnt_getPath() + _inv_cnt_inGame['server'] + "_" + _inv_cnt_inGame['name'] + ".json"

def inv_cnt_isJoined():
    global _inv_cnt_inGame
    _inv_cnt_inGame = get_character_data()
    if not (_inv_cnt_inGame and "name" in _inv_cnt_inGame and _inv_cnt_inGame["name"]):
        _inv_cnt_inGame = None
    return _inv_cnt_inGame

def inv_cnt_loadConfigs():
    global _inv_cnt_selected_chat_channel, _inv_cnt_target_private_name
    QtBind.clear(gui, _inv_cnt_lstLeaders)
    if inv_cnt_isJoined():
        cfg = inv_cnt_getConfig()
        log('[%s] [Envanter Sayacı] Config dosyası aranıyor: %s' % (pName, cfg))
        if os.path.exists(cfg):
            try:
                with open(cfg, "r", encoding='utf-8') as f:
                    data = json.load(f)
                if "Leaders" in data:
                    log('[%s] [Envanter Sayacı] %d lider yüklendi: %s' % (pName, len(data["Leaders"]), data["Leaders"]))
                    for nickname in data["Leaders"]:
                        QtBind.append(gui, _inv_cnt_lstLeaders, nickname)
                else:
                    log('[%s] [Envanter Sayacı] Config dosyasında "Leaders" anahtarı yok' % pName)
                _inv_cnt_selected_chat_channel = data.get("ChatChannel", "PrivateSender")
                _inv_cnt_target_private_name = data.get("TargetPrivateName", "")
                QtBind.setChecked(gui, _inv_cnt_cbxAllChat, _inv_cnt_selected_chat_channel == "All")
                QtBind.setChecked(gui, _inv_cnt_cbxPartyChat, _inv_cnt_selected_chat_channel == "Party")
                QtBind.setChecked(gui, _inv_cnt_cbxGuildChat, _inv_cnt_selected_chat_channel == "Guild")
                QtBind.setChecked(gui, _inv_cnt_cbxUnionChat, _inv_cnt_selected_chat_channel == "Union")
                QtBind.setChecked(gui, _inv_cnt_cbxPrivateChatSender, _inv_cnt_selected_chat_channel == "PrivateSender")
                QtBind.setChecked(gui, _inv_cnt_cbxPrivateChatTarget, _inv_cnt_selected_chat_channel == "PrivateTarget")
                QtBind.setText(gui, _inv_cnt_tbxTargetPrivate, _inv_cnt_target_private_name)
            except Exception as e:
                log('[%s] [Envanter Sayacı] Config yüklenirken hata: %s' % (pName, e))
                _inv_cnt_selected_chat_channel = "PrivateSender"
                _inv_cnt_target_private_name = ""
                QtBind.setChecked(gui, _inv_cnt_cbxPrivateChatSender, True)
                QtBind.setText(gui, _inv_cnt_tbxTargetPrivate, "")
        else:
            log('[%s] [Envanter Sayacı] Config dosyası bulunamadı: %s' % (pName, cfg))
            _inv_cnt_selected_chat_channel = "PrivateSender"
            _inv_cnt_target_private_name = ""
            QtBind.setChecked(gui, _inv_cnt_cbxPrivateChatSender, True)
            QtBind.setText(gui, _inv_cnt_tbxTargetPrivate, "")
    else:
        log('[%s] [Envanter Sayacı] Oyuna giriş yapılmamış, config yüklenemedi' % pName)

def inv_cnt_saveConfigs():
    global _inv_cnt_target_private_name
    if not inv_cnt_isJoined():
        return
    if _inv_cnt_inGame:
        cfg = inv_cnt_getConfig()
        data = {}
        if os.path.exists(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = {"Leaders": QtBind.getItems(gui, _inv_cnt_lstLeaders)}
        _inv_cnt_target_private_name = QtBind.text(gui, _inv_cnt_tbxTargetPrivate)
        data["ChatChannel"] = _inv_cnt_selected_chat_channel
        data["TargetPrivateName"] = _inv_cnt_target_private_name
        data["Leaders"] = QtBind.getItems(gui, _inv_cnt_lstLeaders)
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=False)
        except Exception as e:
            log('[%s] [Envanter Sayacı] Config yazılırken hata: %s' % (pName, e))

def inv_cnt_btnkarakter_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- EXP : Suanki LV ve EXP bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- SP : Suan ki SP Miktarını belirtir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- GOLD : Envanter Altın Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- GOLDGUILD : Guild Deposundaki Altın Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- GOLDDEPO : Depodaki Altın Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENV : Envanterin boş yuva sayısını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- DEPO : Depodaki boş yuva sayısını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- JOBINFO : JOB Nick, Job Seviye, JOB Tipi Ve JOB Exp miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- JOBBOX : Meslek çantasındaki doluluğu bildirir.(Uzmanlik)')
    QtBind.append(gui, _inv_cnt_lstInfo, '- SOX : Sox Miktarını Bildirir.(Giyilmişler ve Job Setler Haric)')

def inv_cnt_btnelixir_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- INCELX : Incomplete Intensifying Elixir miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8ELX : Lv.8 Intensifying Elixir miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9ELX : Lv.9 Intensifying Elixir miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10ELX : Lv.10 Intensifying Elixir miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11ELX : Lv.11 Intensifying Elixir miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENH12 : 12th Grade Enhancer miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENH13 : 13th Grade Enhancer miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENH14 : 14th Grade Enhancer miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENH15 : 15th Grade Enhancer miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENH16 : 16th Grade Enhancer miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENH17 : 17th Grade Enhancer miktarını bildirir.')

def inv_cnt_btnevent_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- FLOWER : Tüm ciceklerin miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ZERK : Berserker Regeneration Potion miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- PANDORA : Pandora Box miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- MONSTER : Monster Summon Scroll Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- CATA : Alchemy Catalyst miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ICE : Dondurma miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- LUCKYBOX : Lucky Box miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- PLEDGE : Pledge Sag ve Sol miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ALIBABA : AliBaba Seal miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- RUBBER : Rubber Piece miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- THANKS : Thanks event Harf miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- FLAKE : Snow Flake miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- HALLOWEN : Halloween Caddy miktarını bildirir.')

def inv_cnt_btncoin_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- COIN : Envanterdeki Gold/Silver/Iron/Copper/Arena Coin miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- COMBATI : Coin of Combativeness (Party) ve Coin of Combativeness (Individual)')
    QtBind.append(gui, _inv_cnt_lstInfo, 'Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- TOKEN1 : Monk\'s Token miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- TOKEN2 : Soldier\'s Token miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- TOKEN3 : General\'s Token miktarını bildirir.')

def inv_cnt_btnstone_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8BLUE : 8DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8BLUE2 : 8DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9BLUE : 9DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9BLUE2 : 9DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10BLUE : 10DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10BLUE2 : 10DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11BLUE : 11DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11BLUE2 : 11DG Blue Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8STAT : 8DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8STAT2 : 8DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9STAT : 9DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9STAT2 : 9DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10STAT : 10DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10STAT2 : 10DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11STAT : 11DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11STAT2 : 11DG Stat Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8LUCK : 8DG Luck Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9LUCK : 9DG Luck Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10LUCK : 10DG Luck Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11LUCK : 11DG Luck Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8STEADY : 8DG Steady Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9STEADY : 9DG Steady Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10STEADY : 10DG Steady Stonelerin Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11STEADY : 11DG Steady Stonelerin Miktarını bildirir.')

def inv_cnt_btnfgw_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8FGW1 : (8DG SUN) Kolay Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 8FGW2 : (8DG SUN) Zor Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9FGW1 : (9DG SUN) Kolay Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 9FGW2 : (9DG SUN) Zor Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10FGW1 : (10DG MOON) Kolay Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 10FGW2 : (10DG MOON) Zor Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11FGW1 : (11DG EGYPY A) Kolay Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- 11FGW2 : (11DG EGPTY A) Zor Düşen Kartların miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- FADED : Faded Bead Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- PETSTR : Fellow Pet için Increase Strength Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- PETINT : Fellow Pet için Increase Intelligence Miktarını Bildirir.')

def inv_cnt_btnegpty_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- SETA : Egpty A Grade Eşya Miktarını Bildirir.(Giyilmişler Haric)')
    QtBind.append(gui, _inv_cnt_lstInfo, ' Sadece Drop Sayısını bildirir.(Silah - Kıyafet - Kalkan - Yüzük)')
    QtBind.append(gui, _inv_cnt_lstInfo, '- SETB : Egpty B Grade Eşya Miktarını Bildirir.(Giyilmişler Haric)')
    QtBind.append(gui, _inv_cnt_lstInfo, ' Sadece Drop Sayısını bildirir.(Silah - Kıyafet - Kalkan - Yüzük)')

def inv_cnt_btnstall_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- GLOBALSC : Global chatting Miktarını Bildiri.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- REVSC : Reverse Return Scroll Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- CLOCKSC : Clock of Reincarnation Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- DEVILSC : Extension gear Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- PREPLUS : Premium Gold Time PLUS Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- HAMMER : Repair Hammer Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ASTRAL : Magic stone of Astral Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- IMMORTAL : Magic stone of immortal Miktarını Bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- ENVANTERSC : Inventory expansion item miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- STORAGESC : Storage expansion item miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- JOBBLUE : Sealed Magic Rune miktarını belirtir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- JOBARTI : Sealed Reinforcement Rune miktarını belirler.')

def inv_cnt_btnClearInfo_clicked():
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.clear(gui, _inv_cnt_lstLeaders)
    QtBind.append(gui, _inv_cnt_lstInfo, "   TR_InventoryCounter - Lider ekleyip sohbetten komut gönderin (ENV, DEPO, GOLD, EXP, SOX vb.).")
    QtBind.append(gui, _inv_cnt_lstInfo, "   Komut listesi için üstteki butonlara tıklayın.")
    
    # Config'den de liderleri temizle
    if inv_cnt_isJoined():
        cfg = inv_cnt_getConfig()
        if os.path.exists(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["Leaders"] = []
                with open(cfg, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=False)
            except Exception as e:
                log('[%s] [Envanter Sayacı] Temizleme sırasında config hatası: %s' % (pName, e))
    
    log('[%s] [Envanter Sayacı] Bilgi ve lider listesi temizlendi.' % pName)

def inv_cnt_lstLeaders_exist(nickname):
    nickname_lower = nickname.lower()
    for player in QtBind.getItems(gui, _inv_cnt_lstLeaders):
        if player.lower() == nickname_lower:
            return True
    return False

def inv_cnt_btnAddLeader_clicked():
    if not inv_cnt_isJoined():
        log('[%s] [Envanter Sayacı] Oyuna giriş yapılmamış.' % pName)
        return
    player = QtBind.text(gui, _inv_cnt_tbxLeaders)
    if player and not inv_cnt_lstLeaders_exist(player):
        cfg = inv_cnt_getConfig()
        data = {}
        if os.path.exists(cfg):
            try:
                with open(cfg, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                log('[%s] [Envanter Sayacı] Config okunurken hata: %s' % (pName, e))
                data = {}
        if "Leaders" not in data:
            data['Leaders'] = []
        if player not in data['Leaders']:
            data['Leaders'].append(player)
            try:
                with open(cfg, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=False)
                QtBind.append(gui, _inv_cnt_lstLeaders, player)
                QtBind.setText(gui, _inv_cnt_tbxLeaders, "")
                log('[%s] [Envanter Sayacı] Lider eklendi: [%s]' % (pName, player))
            except Exception as e:
                log('[%s] [Envanter Sayacı] Config yazılamadı: %s' % (pName, e))
        else:
            log('[%s] [Envanter Sayacı] Lider zaten listede: [%s]' % (pName, player))
            QtBind.setText(gui, _inv_cnt_tbxLeaders, "")

def inv_cnt_btnRemLeader_clicked():
    if not inv_cnt_isJoined():
        return
    selected = QtBind.text(gui, _inv_cnt_lstLeaders)
    if not selected:
        return
    cfg = inv_cnt_getConfig()
    data = {"Leaders": []}
    if os.path.exists(cfg):
        try:
            with open(cfg, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "Leaders" in data and selected in data["Leaders"]:
                data["Leaders"].remove(selected)
                with open(cfg, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=False)
                QtBind.remove(gui, _inv_cnt_lstLeaders, selected)
                log('[%s] [Envanter Sayacı] Lider silindi: [%s]' % (pName, selected))
        except Exception as e:
            log('[%s] [Envanter Sayacı] Lider silinirken hata: %s' % (pName, e))

def inv_cnt_update_selected_channel(channel_name):
    global _inv_cnt_selected_chat_channel
    _inv_cnt_selected_chat_channel = channel_name
    QtBind.setChecked(gui, _inv_cnt_cbxAllChat, channel_name == "All")
    QtBind.setChecked(gui, _inv_cnt_cbxPartyChat, channel_name == "Party")
    QtBind.setChecked(gui, _inv_cnt_cbxGuildChat, channel_name == "Guild")
    QtBind.setChecked(gui, _inv_cnt_cbxUnionChat, channel_name == "Union")
    QtBind.setChecked(gui, _inv_cnt_cbxPrivateChatSender, channel_name == "PrivateSender")
    QtBind.setChecked(gui, _inv_cnt_cbxPrivateChatTarget, channel_name == "PrivateTarget")

def inv_cnt_cbxAllChat_clicked(checked):
    if checked:
        inv_cnt_update_selected_channel("All")

def inv_cnt_cbxPartyChat_clicked(checked):
    if checked:
        inv_cnt_update_selected_channel("Party")

def inv_cnt_cbxGuildChat_clicked(checked):
    if checked:
        inv_cnt_update_selected_channel("Guild")

def inv_cnt_cbxUnionChat_clicked(checked):
    if checked:
        inv_cnt_update_selected_channel("Union")

def inv_cnt_cbxPrivateChatSender_clicked(checked):
    if checked:
        inv_cnt_update_selected_channel("PrivateSender")

def inv_cnt_cbxPrivateChatTarget_clicked(checked):
    if checked:
        inv_cnt_update_selected_channel("PrivateTarget")

def inv_cnt_btnSaveChatSettings_clicked():
    inv_cnt_saveConfigs()
    log('[%s] [Envanter Sayacı] Sohbet ayarları kaydedildi.' % pName)

def _inv_cnt_send_response(command_sender, message):
    global _inv_cnt_selected_chat_channel
    ch = _inv_cnt_selected_chat_channel
    try:
        if ch == "All":
            phBotChat.All(message)
        elif ch == "Party":
            if get_party():
                phBotChat.Party(message)
            else:
                phBotChat.Private(command_sender, "(Partide degil) " + message)
        elif ch == "Guild":
            if get_guild():
                phBotChat.Guild(message)
            else:
                phBotChat.Private(command_sender, "(Guildde degil) " + message)
        elif ch == "Union":
            if get_guild():
                phBotChat.Union(message)
            else:
                phBotChat.Private(command_sender, "(Guildde degil) " + message)
        elif ch == "PrivateSender":
            phBotChat.Private(command_sender, message)
        elif ch == "PrivateTarget":
            target_name = QtBind.text(gui, _inv_cnt_tbxTargetPrivate)
            if target_name:
                phBotChat.Private(target_name, message)
            else:
                phBotChat.Private(command_sender, "(Hedef bos!)")
        else:
            phBotChat.Private(command_sender, message)
    except Exception as e:
        log('[%s] [Envanter Sayacı] Gönderim hatası: %s' % (pName, e))
        try:
            phBotChat.Private(command_sender, message)
        except Exception:
            pass

def _inv_cnt_get_sox_counts():
    sox_inv = sox_pet = sox_storage = 0
    def is_sox(item):
        if item and item.get('servername'):
            sn = item['servername']
            return 'RARE' in sn and 'EVENT' not in sn and 'ARCHEMY' not in sn and 'ITEM_TRADE' not in sn
        return False
    inv = get_inventory()
    if inv and inv.get('items'):
        for item in inv['items'][13:]:
            if is_sox(item):
                sox_inv += 1
    pets = get_pets()
    if pets:
        for p_info in pets.values():
            if p_info.get('type') == 'pick' and p_info.get('items'):
                for item in p_info['items']:
                    if is_sox(item):
                        sox_pet += 1
    st = get_storage()
    if st and st.get('items'):
        for item in st['items']:
            if is_sox(item):
                sox_storage += 1
    return sox_inv, sox_pet, sox_storage

def _inv_cnt_checkInv(arg, player):
    try:
        _inv_cnt_checkInv_impl(arg, player)
    except Exception as e:
        log('[%s] [Envanter Sayacı] checkInv hatası: %s' % (pName, e))
        _inv_cnt_send_response(player, "Komut islenirken hata olustu.")

def _inv_cnt_checkInv_impl(arg, player):
    # Tüm değişkenleri başlat
    weapon1 = weapon2 = weapon3 = weapon4 = weapon5 = 0
    protector1 = protector2 = protector3 = protector4 = protector5 = 0
    accessory1 = accessory2 = accessory3 = accessory4 = accessory5 = 0
    shield1 = shield2 = shield3 = shield4 = shield5 = 0
    eweapon1 = eweapon2 = eweapon3 = eweapon4 = eweapon5 = eweapon6 = 0
    eprotector1 = eprotector2 = eprotector3 = eprotector4 = eprotector5 = eprotector6 = 0
    eaccessory1 = eaccessory2 = eaccessory3 = eaccessory4 = eaccessory5 = eaccessory6 = 0
    eshield1 = eshield2 = eshield3 = eshield4 = eshield5 = eshield6 = 0
    arena = qgold = silver = iron = copper = 0
    combativeness1 = combativeness2 = 0
    flowerevil = flowerillusion = flowerlife = flowerenergy = flowerwhirling = 0
    catalyst = berserker = pandora = ms = luckybox = 0
    pledge1 = pledge2 = alibabaseal = rubber = snowflake = halloweencandy = 0
    T1 = T2 = T3 = T4 = T5 = T6 = 0
    cream = lamp = dLamp = 0
    master8 = strikes8 = discipline8 = penetration8 = dodging8 = stamina8 = magic8 = fogs8 = air8 = fire8 = immunity8 = revival8 = 0
    master9 = strikes9 = discipline9 = penetration9 = dodging9 = stamina9 = magic9 = fogs9 = air9 = fire9 = immunity9 = revival9 = 0
    master10 = strikes10 = discipline10 = penetration10 = dodging10 = stamina10 = magic10 = fogs10 = air10 = fire10 = immunity10 = revival10 = 0
    master11 = strikes11 = discipline11 = penetration11 = dodging11 = stamina11 = magic11 = fogs11 = air11 = fire11 = immunity11 = revival11 = 0
    str8 = int8 = courage8 = warriors8 = philosophy8 = meditation8 = challenge8 = focus8 = flesh8 = life8 = mind8 = spirit8 = dodgings8 = agility8 = training8 = prayer8 = 0
    str9 = int9 = courage9 = warriors9 = philosophy9 = meditation9 = challenge9 = focus9 = flesh9 = life9 = mind9 = spirit9 = dodgings9 = agility9 = training9 = prayer9 = 0
    str10 = int10 = courage10 = warriors10 = philosophy10 = meditation10 = challenge10 = focus10 = flesh10 = life10 = mind10 = spirit10 = dodgings10 = agility10 = training10 = prayer10 = 0
    str11 = int11 = courage11 = warriors11 = philosophy11 = meditation11 = challenge11 = focus11 = flesh11 = life11 = mind11 = spirit11 = dodgings11 = agility11 = training11 = prayer11 = 0
    luckst8 = steadyst8 = luckst9 = steadyst9 = luckst10 = steadyst10 = luckst11 = steadyst11 = 0
    astral8 = immortal8 = astral9 = immortal9 = astral10 = immortal10 = astral11 = immortal11 = 0
    card1 = card2 = card3 = card4 = card5 = card6 = card7 = card8 = 0
    card9 = card10 = card11 = card12 = card13 = card14 = card15 = card16 = 0
    card17 = card18 = card19 = card20 = card21 = card22 = card23 = card24 = 0
    card25 = card26 = card27 = card28 = card29 = card30 = card31 = card32 = 0
    faded = petstr = petint = 0
    aGrade = bGrade = 0
    chatglobal = chatglobalvip = reversesc = clocksc = devilres = preplus = repairhammer = inventorysc = storagesc = 0
    jobblue = jobartı = token1 = token2 = token3 = 0

    # Item'ları topla
    inventory = get_inventory()
    storage = get_storage()
    pets = get_pets()
    inventory_items = []
    storage_items = []
    pet_items = []
    if inventory and 'items' in inventory:
        inventory_items = inventory['items'][13:]
    if storage and 'items' in storage:
        storage_items = storage['items']
    if pets:
        for p in pets.keys():
            pet = pets[p]
            if pet['type'] in 'pick':
                pet_items.extend(pet.get('items', []))
    all_items = inventory_items + storage_items + pet_items
    
    # Item sayımı yap
    if all_items:
        for item in all_items:
            if item is not None and 'name' in item:
                q = item.get('quantity', 1)
                name = item['name']
                sname = item.get('servername', '')
                
                # Elixir/Enhancer
                if "Incomplete" in name and "Weapon" in name: weapon5 += q
                if "Incomplete" in name and "Armor" in name: protector5 += q
                if "Incomplete" in name and "Accessory" in name: accessory5 += q
                if "Incomplete" in name and "Shield" in name: shield5 += q
                if "Lv.8" in name and "Weapon" in name: weapon1 += q
                if "Lv.8" in name and "Armor" in name: protector1 += q
                if "Lv.8" in name and "Accessory" in name: accessory1 += q
                if "Lv.8" in name and "Shield" in name: shield1 += q
                if "Lv.9" in name and "Weapon" in name: weapon2 += q
                if "Lv.9" in name and "Armor" in name: protector2 += q
                if "Lv.9" in name and "Accessory" in name: accessory2 += q
                if "Lv.9" in name and "Shield" in name: shield2 += q
                if "Lv.10" in name and "Weapon" in name: weapon3 += q
                if "Lv.10" in name and "Armor" in name: protector3 += q
                if "Lv.10" in name and "Accessory" in name: accessory3 += q
                if "Lv.10" in name and "Shield" in name: shield3 += q
                if "Lv.11" in name and "Weapon" in name: weapon4 += q
                if "Lv.11" in name and "Armor" in name: protector4 += q
                if "Lv.11" in name and "Accessory" in name: accessory4 += q
                if "Lv.11" in name and "Shield" in name: shield4 += q
                if "12th Grade Enhancer" in name and "Weapon" in name: eweapon1 += q
                if "12th Grade Enhancer" in name and "Armor" in name: eprotector1 += q
                if "12th Grade Enhancer" in name and "Accessory" in name: eaccessory1 += q
                if "12th Grade Enhancer" in name and "Shield" in name: eshield1 += q
                if "13th Grade Enhancer" in name and "Weapon" in name: eweapon2 += q
                if "13th Grade Enhancer" in name and "Armor" in name: eprotector2 += q
                if "13th Grade Enhancer" in name and "Accessory" in name: eaccessory2 += q
                if "13th Grade Enhancer" in name and "Shield" in name: eshield2 += q
                if "14th Grade Enhancer" in name and "Weapon" in name: eweapon3 += q
                if "14th Grade Enhancer" in name and "Armor" in name: eprotector3 += q
                if "14th Grade Enhancer" in name and "Accessory" in name: eaccessory3 += q
                if "14th Grade Enhancer" in name and "Shield" in name: eshield3 += q
                if "15th Grade Enhancer" in name and "Weapon" in name: eweapon4 += q
                if "15th Grade Enhancer" in name and "Armor" in name: eprotector4 += q
                if "15th Grade Enhancer" in name and "Accessory" in name: eaccessory4 += q
                if "15th Grade Enhancer" in name and "Shield" in name: eshield4 += q
                if "16th Grade Enhancer" in name and "Weapon" in name: eweapon5 += q
                if "16th Grade Enhancer" in name and "Armor" in name: eprotector5 += q
                if "16th Grade Enhancer" in name and "Accessory" in name: eaccessory5 += q
                if "16th Grade Enhancer" in name and "Shield" in name: eshield5 += q
                if "17th Grade Enhancer" in name and "Weapon" in name: eweapon6 += q
                if "17th Grade Enhancer" in name and "Armor" in name: eprotector6 += q
                if "17th Grade Enhancer" in name and "Accessory" in name: eaccessory6 += q
                if "17th Grade Enhancer" in name and "Shield" in name: eshield6 += q
                
                # Flowers
                if "Flower" in name and "Evil" in name: flowerevil += q
                if "Flower" in name and "Illusion" in name: flowerillusion += q
                if "Flower" in name and "Life" in name: flowerlife += q
                if "Flower" in name and "Energy" in name: flowerenergy += q
                if "Flower" in name and "Whirling" in name: flowerwhirling += q
                
                # Coins
                if "ITEM_ETC_ARENA_COIN" in sname: arena += q
                if "ITEM_ETC_SD_TOKEN_04" in sname: qgold += q
                if "ITEM_ETC_SD_TOKEN_03" in sname: silver += q
                if "ITEM_ETC_SD_TOKEN_02" in sname: iron += q
                if "ITEM_ETC_SD_TOKEN_01" in sname: copper += q
                if "ITEM_ETC_SURVIVAL_ARENA_PARTY_COIN" in sname: combativeness1 += q
                if "ITEM_ETC_SURVIVAL_ARENA_SOLO_COIN" in sname: combativeness2 += q
                
                # Alchemy catalyst
                if "Alchemy catalyst" in name: catalyst += q
                
                # Berserker
                if "Berserker Regeneration Potion" in name: berserker += q
                
                # Pandora, Lucky Box, Monster Scroll
                if "ITEM_ETC_E060517_MON_GENERATION_BOX" in sname or "ITEM_EVENT_GENERATION_BOX" in sname or "ITEM_EVENT_RENT_E100222_MON_GENERATION_BOX" in sname:
                    pandora += q
                if "ITEM_ETC_E060517_SUMMON_PARTY_SCROLL" in sname or "ITEM_ETC_E060526_SUMMON_PARTY_SCROLL_A" in sname or "ITEM_EVENT_RENT_E100222_SUMMON_SCROLL" in sname:
                    ms += q
                if "ITEM_ETC_E090121_LUCKYBOX" in sname or "ITEM_ETC_E120118_LUCKYBOX" in sname:
                    luckybox += q
                
                # Pledge
                if "ITEM_ETC_E070523_LEFT_HEART" in sname: pledge1 += q
                if "ITEM_ETC_E070523_RIGHT_HEART" in sname: pledge2 += q
                
                # AliBaba, Rubber, Snow, Halloween
                if "AliBaba Seal" in name: alibabaseal += q
                if "Rubber Piece" in name: rubber += q
                if "T (Event Item)" in name: T1 += q
                if "H (Event Item)" in name: T2 += q
                if "A (Event Item)" in name: T3 += q
                if "N (Event Item)" in name: T4 += q
                if "K (Event Item)" in name: T5 += q
                if "S (Event Item)" in name: T6 += q
                if "Snow flake" in name: snowflake += q
                if "Halloween Candy" in name: halloweencandy += q
                
                # Ice cream, Lamps
                if "ITEM_ETC_E090722_" in sname and "ICECREAM" in sname: cream += q
                if "Genie's Lamp" in name: lamp += q
                if "Dirty Lamp" in name: dLamp += q
                
                # Egpty Sets
                if 'SET_A_RARE' in sname: aGrade += 1
                if 'SET_B_RARE' in sname: bGrade += 1
                
                # Scrolls & Items
                if "ITEM_MALL_GLOBAL_CHATTING" in sname or "ITEM_ETC_GLOBAL_CHATTING_BASIC" in sname or "ITEM_EVENT_RENT_GLOBAL_CHATTING" in sname or "ITEM_EVENT_GLOBAL_CHATTING" in sname or "ITEM_EVENT_GLOBAL_CHATTING_SUPPORT" in sname:
                    chatglobal += q
                if "ITEM_MALL_GLOBAL_CHATTING_2" in sname or "ITEM_EVENT_GLOBAL_CHATTING_2" in sname:
                    chatglobalvip += q
                if "ITEM_MALL_REVERSE_RETURN_SCROLL" in sname or "ITEM_EVENT_REVERSE_RETURN_SCROLL" in sname or "ITEM_EVENT_RENT_REVERSE_RETURN_SCROLL" in sname or "ITEM_EVENT_REVERSE_RETURN_SCROLL_BASIC" in sname or "ITEM_EVENT_REVERSE_RETURN_SCROLL_SUPPORT" in sname:
                    reversesc += q
                if "ITEM_COS_P_EXTENSION" in sname or "ITEM_EVENT_RENT_COS_P_EXTENSION" in sname or "ITEM_COS_P_EXTENSION_1D" in sname or "ITEM_EVENT_COS_P_EXTENSION_3D" in sname or "ITEM_EVENT_COS_P_EXTENSION_7D" in sname:
                    clocksc += q
                if "ITEM_MALL_NASRUN_EXTENSION" in sname or "ITEM_EVENT_NASRUN_EXTENSION" in sname or "ITEM_EVENT_RENT_NASRUN_EXTENSION" in sname or "ITEM_EVENT_NASRUN_EXTENSION_3DAY" in sname or "ITEM_EVENT_NASRUN_EXTENSION_7DAY" in sname or "ITEM_EVENT_NASRUN_EXTENSION_28DAY" in sname:
                    devilres += q
                if "ITEM_MALL_PREMIUM_GOLDTIME" in sname or "ITEM_MALL_PREMIUM_GLOBAL_GOLDTIME" in sname or "ITEM_MALL_PREMIUM_GLOBAL_GOLDTIME_PLUS" in sname or "ITEM_EVENT_PREMIUM_GOLDTIME" in sname or "ITEM_EVENT_PREMIUM_GLOBAL_GOLDTIME_PLUS" in sname or "ITEM_ETC_PREMIUM_GLOBAL_GOLDTIME_PLUS_SUPPORT" in sname or "ITEM_MALL_PREMIUM_GLOBAL_GOLDTIME_PLUS_2" in sname:
                    preplus += q
                if "ITEM_MALL_REPAIR_HAMMER" in sname or "ITEM_EVENT_REPAIR_HAMMER" in sname or "ITEM_EVENT_REPAIR_HAMMER_SUPPORT" in sname:
                    repairhammer += q
                if "ITEM_MALL_INVENTORY_ADDITION" in sname or "ITEM_EVENT_INVENTORY_ADDITION" in sname:
                    inventorysc += q
                if "ITEM_MALL_WAREHOUSE_ADDITION" in sname or "ITEM_EVENT_WAREHOUSE_ADDITION" in sname:
                    storagesc += q
                if "ITEM_MALL_TRADE_MAGICRUNE_SEAL" in sname or "ITEM_EVENT_TRADE_MAGICRUNE_SEAL" in sname:
                    jobblue += q
                if "ITEM_MALL_TRADE_STRENTHRUNE_SEAL" in sname or "ITEM_EVENT_TRADE_STRENTHRUNE_SEAL" in sname:
                    jobartı += q
                
                # Astral & Immortal stones
                if "Magic stone of Astral" in name and "(Lvl.08)" in name: astral8 += q
                if "Magic stone of Astral" in name and "(Lvl.09)" in name: astral9 += q
                if "Magic stone of Astral" in name and "(Lvl.10)" in name: astral10 += q
                if "Magic stone of Astral" in name and "(Lvl.11)" in name: astral11 += q
                if "Magic stone of immortal" in name and "(Lvl.08)" in name: immortal8 += q
                if "Magic stone of immortal" in name and "(Lvl.09)" in name: immortal9 += q
                if "Magic stone of immortal" in name and "(Lvl.10)" in name: immortal10 += q
                if "Magic stone of immortal" in name and "(Lvl.11)" in name: immortal11 += q
                
                # Tokens
                if "ITEM_ETC_LEVEL_TOKEN_01" in sname: token1 += q
                if "ITEM_ETC_LEVEL_TOKEN_02" in sname: token2 += q
                if "ITEM_ETC_LEVEL_TOKEN_03" in sname: token3 += q
                
                # Pet STR/INT
                if "Increase Strength" in name or "Gücü Arttır" in name: petstr += q
                if "Increase Intelligence" in name or "Zekayı Arttır" in name: petint += q
                
                # Faded bead
                if "ITEM_ETC_SKILLPOINT_STONE" in sname: faded += q
    
    # Response'ları gönder
    if arg == "ElixirInc":
        _inv_cnt_send_response(player, "Incomplete Weapon %d , Incomplete Armor %d , Incomplete Shield %d , Incomplete Accessory %d" % (weapon5, protector5, shield5, accessory5))
    elif arg == "Elixir8":
        _inv_cnt_send_response(player, "8DG Elixir; Weapon %d , Armor %d , Shield %d , Accessory %d" % (weapon1, protector1, shield1, accessory1))
    elif arg == "Elixir9":
        _inv_cnt_send_response(player, "9DG Elixir; Weapon %d , Armor %d , Shield %d , Accessory %d" % (weapon2, protector2, shield2, accessory2))
    elif arg == "Elixir10":
        _inv_cnt_send_response(player, "10DG Elixir; Weapon %d , Armor %d , Shield %d , Accessory %d" % (weapon3, protector3, shield3, accessory3))
    elif arg == "Elixir11":
        _inv_cnt_send_response(player, "11DG Elixir; Weapon %d , Armor %d , Shield %d , Accessory %d" % (weapon4, protector4, shield4, accessory4))
    elif arg == "Enhancer12":
        _inv_cnt_send_response(player, "12DG ENHANCER; Weapon %d , Armor %d , Shield %d , Accessory %d" % (eweapon1, eprotector1, eshield1, eaccessory1))
    elif arg == "Enhancer13":
        _inv_cnt_send_response(player, "13DG ENHANCER; Weapon %d , Armor %d , Shield %d , Accessory %d" % (eweapon2, eprotector2, eshield2, eaccessory2))
    elif arg == "Enhancer14":
        _inv_cnt_send_response(player, "14DG ENHANCER; Weapon %d , Armor %d , Shield %d , Accessory %d" % (eweapon3, eprotector3, eshield3, eaccessory3))
    elif arg == "Enhancer15":
        _inv_cnt_send_response(player, "15DG ENHANCER; Weapon %d , Armor %d , Shield %d , Accessory %d" % (eweapon4, eprotector4, eshield4, eaccessory4))
    elif arg == "Enhancer16":
        _inv_cnt_send_response(player, "16DG ENHANCER; Weapon %d , Armor %d , Shield %d , Accessory %d" % (eweapon5, eprotector5, eshield5, eaccessory5))
    elif arg == "Enhancer17":
        _inv_cnt_send_response(player, "17DG ENHANCER; Weapon %d , Armor %d , Shield %d , Accessory %d" % (eweapon6, eprotector6, eshield6, eaccessory6))
    elif arg == "Flowerall":
        _inv_cnt_send_response(player, "Flower; Life %d , Energy %d , Evil %d , Illusion %d , Whirling %d" % (flowerlife, flowerenergy, flowerevil, flowerillusion, flowerwhirling))
    elif arg == "Combatii":
        _inv_cnt_send_response(player, "Coin of Combativeness (Party) %d , Coin of Combativeness (Individual) %d" % (combativeness1, combativeness2))
    elif arg == "Coin":
        _inv_cnt_send_response(player, "Gold Coin %d , Silver Coin %d , Iron Coin %d , Copper Coin %d , Arena Coin %d" % (qgold, silver, iron, copper, arena))
    elif arg == "Catalyst":
        _inv_cnt_send_response(player, "Alchemy Catalyst %d" % catalyst)
    elif arg == "Cream":
        _inv_cnt_send_response(player, "Ice Cream %d" % cream)
    elif arg == "luckyboxx":
        _inv_cnt_send_response(player, "Lucky Box %d" % luckybox)
    elif arg == "Pledges":
        _inv_cnt_send_response(player, "Pledge of Love(Left) %d , Pledge of Love(Right) %d" % (pledge1, pledge2))
    elif arg == "Pandora":
        _inv_cnt_send_response(player, "Pandora %d" % pandora)
    elif arg == "alibabaseall":
        _inv_cnt_send_response(player, "AliBaba Seal %d" % alibabaseal)
    elif arg == "Rubberr":
        _inv_cnt_send_response(player, "Rubber Piece %d" % rubber)
    elif arg == "Thanks":
        _inv_cnt_send_response(player, "T > %d , H > %d , A > %d , N > %d , K > %d , S > %d" % (T1, T2, T3, T4, T5, T6))
    elif arg == "Snoww":
        _inv_cnt_send_response(player, "Snow flake %d" % snowflake)
    elif arg == "halloweencandyy":
        _inv_cnt_send_response(player, "Halloween Candy %d" % halloweencandy)
    elif arg == "Zerk":
        _inv_cnt_send_response(player, "Berserker Regeneration Potion %d" % berserker)
    elif arg == "Ms":
        _inv_cnt_send_response(player, "Monster Summon Scroll %d" % ms)
    elif arg == "Lamp":
        _inv_cnt_send_response(player, "Genie's Lamp %d -- Dirty Lamp %d" % (lamp, dLamp))
    elif arg == "faded":
        _inv_cnt_send_response(player, "Faded Bead %d" % faded)
    elif arg == "SetA":
        _inv_cnt_send_response(player, "%d Parca Egpty A Esyasi" % aGrade)
    elif arg == "SetB":
        _inv_cnt_send_response(player, "%d Parca Egpty B Esyasi" % bGrade)
    elif arg == "chatglobal":
        _inv_cnt_send_response(player, "Global Chat %d" % chatglobal)
    elif arg == "chatglobalvip":
        _inv_cnt_send_response(player, "Global Chat VIP %d" % chatglobalvip)
    elif arg == "reversesc":
        _inv_cnt_send_response(player, "Reverse Return Scroll %d" % reversesc)
    elif arg == "clocksc":
        _inv_cnt_send_response(player, "Clock of Reincarnation %d" % clocksc)
    elif arg == "devilres":
        _inv_cnt_send_response(player, "Extension gear %d" % devilres)
    elif arg == "preplus":
        _inv_cnt_send_response(player, "Premium Gold Time PLUS %d" % preplus)
    elif arg == "repairhammer":
        _inv_cnt_send_response(player, "Repair hammer %d" % repairhammer)
    elif arg == "astral":
        _inv_cnt_send_response(player, "Astral (Lvl.8)= %d , (Lvl.9)= %d , (Lvl.10)= %d , (Lvl.11)= %d" % (astral8, astral9, astral10, astral11))
    elif arg == "immortal":
        _inv_cnt_send_response(player, "Immortal (Lvl.8)= %d , (Lvl.9)= %d , (Lvl.10)= %d , (Lvl.11)= %d" % (immortal8, immortal9, immortal10, immortal11))
    elif arg == "inventorysc":
        _inv_cnt_send_response(player, "Inventory expansion item %d" % inventorysc)
    elif arg == "storagesc":
        _inv_cnt_send_response(player, "Storage expansion item %d" % storagesc)
    elif arg == "jobblue":
        _inv_cnt_send_response(player, "Sealed Magic Rune %d" % jobblue)
    elif arg == "jobartı":
        _inv_cnt_send_response(player, "Sealed Reinforcement Rune %d" % jobartı)
    elif arg == "token1":
        _inv_cnt_send_response(player, "Monk's Token %d" % token1)
    elif arg == "token2":
        _inv_cnt_send_response(player, "Soldier's Token %d" % token2)
    elif arg == "token3":
        _inv_cnt_send_response(player, "General's Token %d" % token3)
    elif arg == "petstr":
        _inv_cnt_send_response(player, "Increase Strength %d" % petstr)
    elif arg == "petint":
        _inv_cnt_send_response(player, "Increase Intelligence %d" % petint)

def _inv_cnt_handle_chat(t, player, msg):
    if not (player and inv_cnt_lstLeaders_exist(player)) and t != 100:
        return
    msg = (msg or "").strip().upper()
    if msg == "ENV":
        try:
            inv_data = get_inventory()
            if inv_data and 'items' in inv_data and 'size' in inv_data:
                total = inv_data['size']
                eq_slots = 13
                inv_count = total - eq_slots
                items = inv_data['items']
                if inv_count > 0 and len(items) >= total:
                    free = sum(1 for item in items[eq_slots:total] if not item or item == {})
                    occ = inv_count - free
                    _inv_cnt_send_response(player, "Bos Alan: %d ----> Dolu: %d/%d (Toplam: %d)" % (free, occ, inv_count, total))
                else:
                    _inv_cnt_send_response(player, "Envanter hesaplanamadi.")
            else:
                _inv_cnt_send_response(player, "Envanter bilgisi alinamadi.")
        except Exception as e:
            _inv_cnt_send_response(player, "ENV hatasi.")
    elif msg == "DEPO":
        try:
            st = get_storage()
            if st and 'items' in st and 'size' in st:
                size = st['size']
                items = st['items']
                free = items[:size].count({}) if size else 0
                occ = size - free
                _inv_cnt_send_response(player, "Depo Bos: %d ----> Dolu: %d/%d" % (free, occ, size))
            else:
                _inv_cnt_send_response(player, "Depo bilgisi alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "DEPO hatasi.")
    elif msg == "EXP":
        try:
            data = get_character_data()
            if data and 'current_exp' in data and 'level' in data and 'max_exp' in data and data['max_exp'] > 0:
                pct = (100.0 * data['current_exp']) / data['max_exp']
                _inv_cnt_send_response(player, "Seviye: %s - EXP: %.2f%%" % (data['level'], pct))
            else:
                _inv_cnt_send_response(player, "EXP alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "EXP hatasi.")
    elif msg == "GOLD":
        try:
            data = get_character_data()
            if data and 'gold' in data:
                _inv_cnt_send_response(player, "Envanterde %s Altin." % ("{:,}".format(data['gold'])))
            else:
                _inv_cnt_send_response(player, "Altin bilgisi alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "GOLD hatasi.")
    elif msg == "GOLDDEPO":
        try:
            st = get_storage()
            if st and 'gold' in st:
                _inv_cnt_send_response(player, "Depoda %s Altin." % ("{:,}".format(st['gold'])))
            else:
                _inv_cnt_send_response(player, "Depo altin alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "GOLDDEPO hatasi.")
    elif msg == "SP":
        try:
            data = get_character_data()
            if data and 'sp' in data:
                _inv_cnt_send_response(player, "Su an %s Skill Point." % ("{:,}".format(data['sp'])))
            else:
                _inv_cnt_send_response(player, "SP alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "SP hatasi.")
    elif msg == "SOX":
        try:
            inv_c, pet_c, st_c = _inv_cnt_get_sox_counts()
            _inv_cnt_send_response(player, "Envanter ( %d ) , Pet ( %d ) , Depo ( %d )" % (inv_c, pet_c, st_c))
        except Exception:
            _inv_cnt_send_response(player, "SOX hatasi.")
    elif msg == "JOBINFO":
        try:
            data = get_character_data()
            if data:
                jn = data.get('job_name', 'N/A')
                jl = data.get('job_level', 0)
                jt = data.get('job_type', 'N/A')
                jcur = data.get('job_current_exp', 0)
                jmax = data.get('job_max_exp', 1)
                pct = (100.0 * jcur / jmax) if jmax else 0
                _inv_cnt_send_response(player, "JOB: %s, Lv %s, Tip: %s, Exp: %.2f%%" % (jn, jl, jt, pct))
            else:
                _inv_cnt_send_response(player, "JOB bilgisi alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "JOBINFO hatasi.")
    elif msg == "GOLDGUILD":
        try:
            gs = get_guild_storage()
            if gs and 'gold' in gs:
                _inv_cnt_send_response(player, "Guild Deposunda %s Altin." % ("{:,}".format(gs['gold'])))
            else:
                _inv_cnt_send_response(player, "Guild depo alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "GOLDGUILD hatasi.")
    elif msg == "JOBBOX":
        try:
            pouch = get_job_pouch()
            if pouch and pouch.get("items") is not None:
                items = pouch["items"]
                total_q = sum((it.get("quantity") or 0) for it in items if it)
                _inv_cnt_send_response(player, "Specialty -> %d / %d (%d slot)" % (total_q, len(items) * 5, len(items)))
            else:
                _inv_cnt_send_response(player, "Meslek cantasi alinamadi.")
        except Exception:
            _inv_cnt_send_response(player, "JOBBOX hatasi.")
    elif msg == "INCELX":
        _inv_cnt_checkInv("ElixirInc", player)
    elif msg == "8ELX":
        _inv_cnt_checkInv("Elixir8", player)
    elif msg == "9ELX":
        _inv_cnt_checkInv("Elixir9", player)
    elif msg == "10ELX":
        _inv_cnt_checkInv("Elixir10", player)
    elif msg == "11ELX":
        _inv_cnt_checkInv("Elixir11", player)
    elif msg == "ENH12":
        _inv_cnt_checkInv("Enhancer12", player)
    elif msg == "ENH13":
        _inv_cnt_checkInv("Enhancer13", player)
    elif msg == "ENH14":
        _inv_cnt_checkInv("Enhancer14", player)
    elif msg == "ENH15":
        _inv_cnt_checkInv("Enhancer15", player)
    elif msg == "ENH16":
        _inv_cnt_checkInv("Enhancer16", player)
    elif msg == "ENH17":
        _inv_cnt_checkInv("Enhancer17", player)
    elif msg == "8BLUE":
        _inv_cnt_checkInv("8Blue", player)
    elif msg == "9BLUE":
        _inv_cnt_checkInv("9Blue", player)
    elif msg == "10BLUE":
        _inv_cnt_checkInv("10Blue", player)
    elif msg == "11BLUE":
        _inv_cnt_checkInv("11Blue", player)
    elif msg == "8BLUE2":
        _inv_cnt_checkInv("8Blue2", player)
    elif msg == "9BLUE2":
        _inv_cnt_checkInv("9Blue2", player)
    elif msg == "10BLUE2":
        _inv_cnt_checkInv("10Blue2", player)
    elif msg == "11BLUE2":
        _inv_cnt_checkInv("11Blue2", player)
    elif msg == "8STAT":
        _inv_cnt_checkInv("8Stat", player)
    elif msg == "9STAT":
        _inv_cnt_checkInv("9Stat", player)
    elif msg == "10STAT":
        _inv_cnt_checkInv("10Stat", player)
    elif msg == "11STAT":
        _inv_cnt_checkInv("11Stat", player)
    elif msg == "8STAT2":
        _inv_cnt_checkInv("8Stat2", player)
    elif msg == "9STAT2":
        _inv_cnt_checkInv("9Stat2", player)
    elif msg == "10STAT2":
        _inv_cnt_checkInv("10Stat2", player)
    elif msg == "11STAT2":
        _inv_cnt_checkInv("11Stat2", player)
    elif msg == "FLOWER":
        _inv_cnt_checkInv("Flowerall", player)
    elif msg == "PANDORA":
        _inv_cnt_checkInv("Pandora", player)
    elif msg == "8LUCK":
        _inv_cnt_checkInv("luck8", player)
    elif msg == "9LUCK":
        _inv_cnt_checkInv("luck9", player)
    elif msg == "10LUCK":
        _inv_cnt_checkInv("luck10", player)
    elif msg == "11LUCK":
        _inv_cnt_checkInv("luck11", player)
    elif msg == "8STEADY":
        _inv_cnt_checkInv("steady8", player)
    elif msg == "9STEADY":
        _inv_cnt_checkInv("steady9", player)
    elif msg == "10STEADY":
        _inv_cnt_checkInv("steady10", player)
    elif msg == "11STEADY":
        _inv_cnt_checkInv("steady11", player)
    elif msg == "MONSTER":
        _inv_cnt_checkInv("Ms", player)
    elif msg == "ICE":
        _inv_cnt_checkInv("Cream", player)
    elif msg == "LUCKYBOX":
        _inv_cnt_checkInv("luckyboxx", player)
    elif msg == "PLEDGE":
        _inv_cnt_checkInv("Pledges", player)
    elif msg == "ALIBABA":
        _inv_cnt_checkInv("alibabaseall", player)
    elif msg == "RUBBER":
        _inv_cnt_checkInv("Rubberr", player)
    elif msg == "THANKS":
        _inv_cnt_checkInv("Thanks", player)
    elif msg == "FLAKE":
        _inv_cnt_checkInv("Snoww", player)
    elif msg == "HALLOWEN":
        _inv_cnt_checkInv("halloweencandyy", player)
    elif msg == "ZERK":
        _inv_cnt_checkInv("Zerk", player)
    elif msg == "LAMP":
        _inv_cnt_checkInv("Lamp", player)
    elif msg == "COIN":
        _inv_cnt_checkInv("Coin", player)
    elif msg == "COMBATI":
        _inv_cnt_checkInv("Combatii", player)
    elif msg == "CATA":
        _inv_cnt_checkInv("Catalyst", player)
    elif msg == "8FGW1":
        _inv_cnt_checkInv("fgw8dgeasy", player)
    elif msg == "8FGW2":
        _inv_cnt_checkInv("fgw8dghard", player)
    elif msg == "9FGW1":
        _inv_cnt_checkInv("fgw9dgeasy", player)
    elif msg == "9FGW2":
        _inv_cnt_checkInv("fgw9dghard", player)
    elif msg == "10FGW1":
        _inv_cnt_checkInv("fgw10dgeasy", player)
    elif msg == "10FGW2":
        _inv_cnt_checkInv("fgw10dghard", player)
    elif msg == "11FGW1":
        _inv_cnt_checkInv("fgw11dgeasy", player)
    elif msg == "11FGW2":
        _inv_cnt_checkInv("fgw11dghard", player)
    elif msg == "FADED":
        _inv_cnt_checkInv("faded", player)
    elif msg == "SETA":
        _inv_cnt_checkInv("SetA", player)
    elif msg == "SETB":
        _inv_cnt_checkInv("SetB", player)
    elif msg == "GLOBALSC":
        _inv_cnt_checkInv("chatglobal", player)
    elif msg == "VIPGLOBAL":
        _inv_cnt_checkInv("chatglobalvip", player)
    elif msg == "REVSC":
        _inv_cnt_checkInv("reversesc", player)
    elif msg == "CLOCKSC":
        _inv_cnt_checkInv("clocksc", player)
    elif msg == "DEVILSC":
        _inv_cnt_checkInv("devilres", player)
    elif msg == "PREPLUS":
        _inv_cnt_checkInv("preplus", player)
    elif msg == "HAMMER":
        _inv_cnt_checkInv("repairhammer", player)
    elif msg == "ASTRAL":
        _inv_cnt_checkInv("astral", player)
    elif msg == "IMMORTAL":
        _inv_cnt_checkInv("immortal", player)
    elif msg == "ENVANTERSC":
        _inv_cnt_checkInv("inventorysc", player)
    elif msg == "STORAGESC":
        _inv_cnt_checkInv("storagesc", player)
    elif msg == "JOBBLUE":
        _inv_cnt_checkInv("jobblue", player)
    elif msg == "JOBARTI":
        _inv_cnt_checkInv("jobartı", player)
    elif msg == "TOKEN1":
        _inv_cnt_checkInv("token1", player)
    elif msg == "TOKEN2":
        _inv_cnt_checkInv("token2", player)
    elif msg == "TOKEN3":
        _inv_cnt_checkInv("token3", player)
    elif msg == "PETSTR":
        _inv_cnt_checkInv("petstr", player)
    elif msg == "PETINT":
        _inv_cnt_checkInv("petint", player)

# Tab 8 - Hakkımda
_t3_x = _tab_bar_x + 20
_t3_y = _content_y + 20

# Sürüm ve butonlar (Sol)
_version_y = _t3_y
_add_tab8(QtBind.createLabel(gui, 'Sürüm: v' + pVersion, _t3_x, _version_y), _t3_x, _version_y)

_btn_y = _version_y + 26
_add_tab8(QtBind.createButton(gui, 'check_update', 'Kontrol', _t3_x, _btn_y), _t3_x, _btn_y)
_add_tab8(QtBind.createButton(gui, 'do_auto_update', 'Güncelle', _t3_x + 85, _btn_y), _t3_x + 85, _btn_y)

_status_y = _btn_y + 30
_update_label_ref = QtBind.createLabel(gui, 'Güncelleme kontrol ediliyor...                    ', _t3_x, _status_y)
_add_tab8(_update_label_ref, _t3_x, _status_y)

# Author ve Lisans Bilgileri (Sağ - Tek container)
_right_section_x = _tab_bar_x + 425
_right_section_y = _t3_y
_right_section_w = 260
_right_section_h = 210

_right_container = QtBind.createList(gui, _right_section_x, _right_section_y, _right_section_w, _right_section_h)
_add_tab8(_right_container, _right_section_x, _right_section_y)

# Author
_author_label_x = _right_section_x + 8
_author_label_y = _right_section_y + 8
_add_tab8(QtBind.createLabel(gui, 'Author:', _author_label_x, _author_label_y), _author_label_x, _author_label_y)
_add_tab8(QtBind.createLabel(gui, 'V i S K i   DaRK_WoLVeS <3', _author_label_x + 5, _author_label_y + 18), _author_label_x + 5, _author_label_y + 18)

# Lisans Key
_license_key_y = _author_label_y + 43
_add_tab8(QtBind.createLabel(gui, 'Lisans Key:', _author_label_x, _license_key_y), _author_label_x, _license_key_y)
_tbx_license_key = QtBind.createLineEdit(gui, "", _author_label_x, _license_key_y + 18, 240, 18)
_add_tab8(_tbx_license_key, _author_label_x, _license_key_y + 18)
_btn_save_license = QtBind.createButton(gui, '_save_license_key_clicked', 'Kaydet', _author_label_x, _license_key_y + 39)
_add_tab8(_btn_save_license, _author_label_x, _license_key_y + 39)
_btn_clear_license = QtBind.createButton(gui, '_clear_license_key_clicked', 'Temizle', _author_label_x + 160, _license_key_y + 39)
_add_tab8(_btn_clear_license, _author_label_x + 160, _license_key_y + 39)

# IP Adresi
_ip_y = _license_key_y + 71
_add_tab8(QtBind.createLabel(gui, 'IP:', _author_label_x, _ip_y), _author_label_x, _ip_y)
_lbl_user_ip = QtBind.createLabel(gui, 'Alınıyor...', _author_label_x + 25, _ip_y)
_add_tab8(_lbl_user_ip, _author_label_x + 25, _ip_y)
_btn_refresh_ip = QtBind.createButton(gui, '_refresh_ip_clicked', 'Yenile', _author_label_x + 160, _ip_y - 6)
_add_tab8(_btn_refresh_ip, _author_label_x + 160, _ip_y - 6)

# Sunucu Durumu
_server_status_y = _ip_y + 24
# Label'ı en uzun olası metinle oluştur (sonra setText ile değiştirilecek)
_lbl_server_status = QtBind.createLabel(gui, 'Sunucu: Kontrol ediliyor...          ', _author_label_x, _server_status_y)
_add_tab8(_lbl_server_status, _author_label_x, _server_status_y)

# Error mesajı (sadece hata durumunda görünür)
_error_msg_y = _server_status_y + 18
_lbl_error_msg1 = QtBind.createLabel(gui, '', _author_label_x, _error_msg_y)
_add_tab8(_lbl_error_msg1, _author_label_x, _error_msg_y)
_lbl_error_msg2 = QtBind.createLabel(gui, '', _author_label_x, _error_msg_y + 14)
_add_tab8(_lbl_error_msg2, _author_label_x, _error_msg_y + 14)

# Plugin Özellikleri (Güncelleme durumunun altında)
_features_y = _status_y + 30
_add_tab8(QtBind.createLabel(gui, 'Plugin Özellikleri:', _t3_x, _features_y), _t3_x, _features_y)

# Sol sütun
_col1_x = _t3_x
_add_tab8(QtBind.createLabel(gui, '• So-Ok Event otomatik kullanma', _col1_x, _features_y + 18), _col1_x, _features_y + 18)
_add_tab8(QtBind.createLabel(gui, '• Çanta/Banka birleştir ve sırala', _col1_x, _features_y + 34), _col1_x, _features_y + 34)
_add_tab8(QtBind.createLabel(gui, '• Auto Dungeon sistemi', _col1_x, _features_y + 50), _col1_x, _features_y + 50)
_add_tab8(QtBind.createLabel(gui, '• Garden Dungeon otomatik', _col1_x, _features_y + 66), _col1_x, _features_y + 66)
_add_tab8(QtBind.createLabel(gui, '• Auto Hwt sistemi', _col1_x, _features_y + 82), _col1_x, _features_y + 82)

# Sağ sütun  
_col2_x = _t3_x + 240
_add_tab8(QtBind.createLabel(gui, '• Oto Kervan sistemi', _col2_x, _features_y + 18), _col2_x, _features_y + 18)
_add_tab8(QtBind.createLabel(gui, '• Script Komutları', _col2_x, _features_y + 34), _col2_x, _features_y + 34)
_add_tab8(QtBind.createLabel(gui, '• Envanter Sayacı', _col2_x, _features_y + 50), _col2_x, _features_y + 50)
_add_tab8(QtBind.createLabel(gui, '• Otomatik güncelleme', _col2_x, _features_y + 66), _col2_x, _features_y + 66)

_tab_move(_tab2_widgets, True)
_tab_move(_tab3_widgets, True)
_tab_move(_tab4_widgets, True)
_tab_move(_tab5_widgets, True)
_tab_move(_tab6_widgets, True)
_tab_move(_tab7_widgets, True)
_tab_move(_tab8_widgets, True)

log('[%s] v%s yüklendi.' % (pName, pVersion))
try:
    inv_cnt_path = get_config_dir() + _inv_cnt_name + "\\"
    if not os.path.exists(inv_cnt_path):
        os.makedirs(inv_cnt_path)
except Exception:
    pass

# Sunucu bilgilerini yükle ve IP'yi al
_init_server_credentials()

threading.Thread(target=_check_update_thread, name=pName + '_update_auto', daemon=True).start()
threading.Thread(target=_check_script_updates_thread, name=pName + '_script_update', daemon=True).start()

# Auto Dungeon klasörünü oluştur
if not os.path.exists(getPath()):
    os.makedirs(getPath())
    log('[%s] %s klasörü oluşturuldu' % (pName, pName))

# ______________________________ Events ______________________________ #

def event_loop():
    """Script Komutları: StartBot/CloseBot zamanlama kontrolü"""
    global _script_cmds_delay_counter, _script_cmds_CheckStartTime, _script_cmds_CheckCloseTime, _script_cmds_SkipCommand
    if _script_cmds_CheckStartTime:
        _script_cmds_delay_counter += 500
        if _script_cmds_delay_counter >= 60000:
            _script_cmds_delay_counter = 0
            current_time = str(datetime.now())[11:16]
            if current_time == _script_cmds_StartBotAt:
                _script_cmds_CheckStartTime = False
                _script_cmds_SkipCommand = True
                log('[%s] Bot başlatılıyor' % pName)
                start_bot()
    elif _script_cmds_CheckCloseTime:
        _script_cmds_delay_counter += 500
        if _script_cmds_delay_counter >= 60000:
            _script_cmds_delay_counter = 0
            current_time = str(datetime.now())[11:16]
            if current_time == _script_cmds_CloseBotAt:
                _script_cmds_CheckCloseTime = False
                _script_cmds_Terminate()

def handle_silkroad(opcode, data):
    """Script Komutları: Özel NPC paket kaydı"""
    global _script_cmds_Recording, _script_cmds_BtnStart, _script_cmds_RecordedPackets
    if data is None:
        return True
    if _script_cmds_BtnStart:
        if opcode == 0x7045 or opcode == 0x7C45:
            _script_cmds_Recording = True
            log('[%s] Kayıt Başladı' % pName)
            _script_cmds_RecordedPackets.append("0x" + '%02X' % opcode + ":" + ' '.join('%02X' % x for x in data))
            if _script_cmds_cbxShowPackets is not None and QtBind.isChecked(gui, _script_cmds_cbxShowPackets):
                log('[%s] Kaydedildi (Opcode) 0x%02X (Veri) %s' % (pName, opcode, 'None' if not data else ' '.join('%02X' % x for x in data)))
        if _script_cmds_Recording:
            if opcode != 0x7045 and opcode != 0x7C45:
                _script_cmds_RecordedPackets.append("0x" + '%02X' % opcode + ":" + ' '.join('%02X' % x for x in data))
                if _script_cmds_cbxShowPackets is not None and QtBind.isChecked(gui, _script_cmds_cbxShowPackets):
                    log('[%s] Kaydedildi (Opcode) 0x%02X (Veri) %s' % (pName, opcode, 'None' if not data else ' '.join('%02X' % x for x in data)))
    return True

def joined_game():
    loadConfigs()
    inv_cnt_loadConfigs()
    
    # IP'yi güncelle ve lisans doğrula (oyuna girişte)
    def _joined_validate():
        _fetch_and_update_ip_ui()
        if _server_license_key:
            time.sleep(1)
            _validate_license_and_update_ui()
        else:
            # Lisans yoksa butonları pasif tut
            _update_license_status(False)
    
    threading.Thread(target=_joined_validate, name=pName + '_joined_validate', daemon=True).start()

def handle_chat(t, player, msg):
    _inv_cnt_handle_chat(t, player, msg)

def handle_joymax(opcode, data):
    # SERVER_DIMENSIONAL_INVITATION_REQUEST
    if opcode == 0x751A:
        if QtBind.isChecked(gui, cbxAcceptForgottenWorld):
            packet = data[:4]
            packet += b'\x00\x00\x00\x00'
            packet += b'\x01'
            inject_joymax(0x751C, packet, False)
            log('[%s] Unutulmuş Dünya daveti kabul edildi!' % pName)
    # SERVER_INVENTORY_ITEM_USE
    elif opcode == 0xB04C:
        global itemUsedByPlugin
        if itemUsedByPlugin:
            if data[0] == 1:
                log('[%s] "%s" açıldı' % (pName, itemUsedByPlugin['name']))
                global dimensionalItemActivated
                dimensionalItemActivated = itemUsedByPlugin
                def DimensionalCooldown():
                    global dimensionalItemActivated
                    dimensionalItemActivated = None
                threading.Timer(DIMENSIONAL_COOLDOWN_DELAY, DimensionalCooldown).start()
                threading.Timer(1.0, EnterToDimensional, [itemUsedByPlugin['name']]).start()
            else:
                log('[%s] "%s" açılamadı' % (pName, itemUsedByPlugin['name']))
            itemUsedByPlugin = None
    return True

# Envanter Sayacı config klasörünü oluştur
_inv_cnt_config_path = inv_cnt_getPath()
if not os.path.exists(_inv_cnt_config_path):
    try:
        os.makedirs(_inv_cnt_config_path)
        log('[%s] [Envanter Sayacı] Klasör oluşturuldu: %s' % (pName, _inv_cnt_config_path))
    except Exception as e:
        log('[%s] [Envanter Sayacı] Klasör oluşturulamadı: %s' % (pName, e))

# Plugin yüklendiğinde karakter oyundaysa config'i yükle
if inv_cnt_isJoined():
    inv_cnt_loadConfigs()
    log('[%s] [Envanter Sayacı] Config yüklendi (plugin init)' % pName)

