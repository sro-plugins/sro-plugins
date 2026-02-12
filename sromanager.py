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

pName = 'SROManager'
PLUGIN_FILENAME = 'sromanager.py'
pVersion = '1.7.0'

MOVE_DELAY = 0.25

# Auto Dungeon constants
DIMENSIONAL_COOLDOWN_DELAY = 7200  # saniye (2 saat)
WAIT_DROPS_DELAY_MAX = 10  # saniye
COUNT_MOBS_DELAY = 1.0  # saniye

GITHUB_REPO = 'sro-plugins/sro-plugins'
GITHUB_API_LATEST = 'https://api.github.com/repos/%s/releases/latest' % GITHUB_REPO
GITHUB_RELEASES_URL = 'https://github.com/%s/releases' % GITHUB_REPO
GITHUB_RAW_MAIN = 'https://raw.githubusercontent.com/%s/main/%s' % (GITHUB_REPO, PLUGIN_FILENAME)
GITHUB_BANK_FEATURES_URL = 'https://raw.githubusercontent.com/%s/main/feature/bank_features.py' % GITHUB_REPO
GITHUB_JEWEL_MERGE_SORT_URL = 'https://raw.githubusercontent.com/%s/main/feature/jewel_merge_sort.py' % GITHUB_REPO
GITHUB_AUTO_BASE_DUNGEON_URL = 'https://raw.githubusercontent.com/%s/main/feature/auto_base_dungeon.py' % GITHUB_REPO
GITHUB_GARDEN_DUNGEON_URL = 'https://raw.githubusercontent.com/%s/main/feature/garden_dungeon.py' % GITHUB_REPO
GITHUB_AUTO_HWT_URL = 'https://raw.githubusercontent.com/%s/main/feature/auto_hwt.py' % GITHUB_REPO
GITHUB_CARAVAN_URL = 'https://raw.githubusercontent.com/%s/main/feature/caravan.py' % GITHUB_REPO
GITHUB_SCRIPT_COMMANDS_URL = 'https://raw.githubusercontent.com/%s/main/feature/script_commands.py' % GITHUB_REPO
GITHUB_INVENTORY_COUNTER_URL = 'https://raw.githubusercontent.com/%s/main/feature/inventory_counter.py' % GITHUB_REPO
GITHUB_TARGET_SUPPORT_URL = 'https://raw.githubusercontent.com/%s/main/feature/target_support.py' % GITHUB_REPO
GITHUB_BLESS_QUEUE_URL = 'https://raw.githubusercontent.com/%s/main/feature/bless_queue.py' % GITHUB_REPO
GITHUB_SCRIPT_COMMAND_MAKER_URL = 'https://raw.githubusercontent.com/%s/main/feature/script_command_maker.py' % GITHUB_REPO
GITHUB_GARDEN_SCRIPT_URL = 'https://raw.githubusercontent.com/%s/main/sc/garden-dungeon.txt' % GITHUB_REPO
GITHUB_GARDEN_WIZZ_CLERIC_SCRIPT_URL = 'https://raw.githubusercontent.com/%s/main/sc/garden-dungeon-wizz-cleric.txt' % GITHUB_REPO
GITHUB_SCRIPT_VERSIONS_URL = 'https://raw.githubusercontent.com/%s/main/sc/versions.json' % GITHUB_REPO
# Oto Kervan: GitHub'daki karavan scriptleri klasörü (API ile liste, raw ile indirme)
# GitHub'da klasör yoksa veya 404 alırsa yerel "caravan" klasörü kullanılır (plugin yanında).
GITHUB_CARAVAN_FOLDER = 'caravan'
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
            headers={'User-Agent': 'phBot-SROManager/1.0'}
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
            headers={'User-Agent': 'phBot-SROManager/1.0'}
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

# Auto Dungeon: itemUsedByPlugin ve dimensionalItemActivated packet hook için ana pluginde kalır
itemUsedByPlugin = None
dimensionalItemActivated = None

# Script Komutları (Tab 6) path - namespace'te kullanılmak üzere loader'da enjekte edilir
_script_cmds_path = get_config_dir()[:-7]  # phBot ana klasör yolu

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
                headers={'User-Agent': 'phBot-SROManager/1.0'}
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
                'User-Agent': 'phBot-SROManager/' + pVersion,
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
            headers={'User-Agent': 'phBot-SROManager/1.0'}
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

def _download_caravan_script(filename):
    """GitHub'dan tek bir karavan scriptini indirir (Oto Kervan modülü yüklüyse oradan, yoksa yerel fallback)."""
    ns = _get_caravan_namespace()
    if ns and '_download_caravan_script' in ns:
        return ns['_download_caravan_script'](filename)
    try:
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), GITHUB_CARAVAN_FOLDER)
        if not os.path.exists(folder):
            os.makedirs(folder)
        script_path = os.path.join(folder, filename)
        path_encoded = urllib.parse.quote(GITHUB_CARAVAN_FOLDER, safe='')
        url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, path_encoded, filename)
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-SROManager/1.0'})
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
                'User-Agent': 'phBot-SROManager/1.0',
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
        req = urllib.request.Request(download_url, headers={'User-Agent': 'phBot-SROManager/1.0'})
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

# Tab 1 - Jewel / Birleştirme / Sıralama: GitHub'dan uzaktan
_jewel_merge_sort_namespace = None

def _get_jewel_merge_sort_namespace():
    global _jewel_merge_sort_namespace
    if _jewel_merge_sort_namespace is not None:
        return _jewel_merge_sort_namespace
    try:
        req = urllib.request.Request(
            GITHUB_JEWEL_MERGE_SORT_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Jewel/Birleştirme/Sıralama modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    namespace = {
        'log': log, 'pName': pName, 'threading': threading, 'time': time, 'struct': struct, 'copy': copy,
        'get_inventory': get_inventory, 'get_item': get_item, 'inject_joymax': inject_joymax,
        '_is_license_valid': _is_license_valid, 'MOVE_DELAY': MOVE_DELAY,
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Jewel/Birleştirme/Sıralama modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _jewel_merge_sort_namespace = namespace
    return _jewel_merge_sort_namespace

def _jms_call(name):
    ns = _get_jewel_merge_sort_namespace()
    if ns and name in ns:
        return ns[name]()
    return None

def jewel_start():
    _jms_call('jewel_start')

def jewel_stop():
    _jms_call('jewel_stop')

def merge_start():
    _jms_call('merge_start')

def merge_stop():
    _jms_call('merge_stop')

def sort_start():
    _jms_call('sort_start')

def sort_stop():
    _jms_call('sort_stop')

# Banka özellikleri: GitHub'dan indirilip cache'lenir, buton tıklanınca exec ile çalıştırılır (ana pluginde banka kodu yok)
_bank_features_namespace = None

def _get_bank_features_namespace():
    global _bank_features_namespace
    if _bank_features_namespace is not None:
        log('[%s] [Banka] Modül zaten yüklü (cache kullanılıyor).' % pName)
        return _bank_features_namespace
    log('[%s] [Banka] Modül cache\'de yok, GitHub\'dan indiriliyor: %s' % (pName, GITHUB_BANK_FEATURES_URL))
    try:
        req = urllib.request.Request(
            GITHUB_BANK_FEATURES_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
        log('[%s] [Banka] İndirme tamamlandı (%d byte), exec ile yükleniyor...' % (pName, len(code)))
    except Exception as ex:
        log('[%s] Banka özellikleri indirilemedi: %s' % (pName, str(ex)))
        return None
    jms_ns = _get_jewel_merge_sort_namespace()
    namespace = {
        'log': log,
        'pName': pName,
        'get_storage': get_storage,
        'get_item': get_item,
        'get_npcs': get_npcs,
        'inject_joymax': inject_joymax,
        '_is_license_valid': _is_license_valid,
        'NPC_STORAGE_SERVERNAMES': NPC_STORAGE_SERVERNAMES,
        'MOVE_DELAY': MOVE_DELAY,
        'struct': struct,
        'threading': threading,
        'time': time,
        'copy': copy,
    }
    if jms_ns:
        namespace['_array_sort_by_subkey'] = jms_ns.get('_array_sort_by_subkey')
        namespace['_array_get_subkey_filtered_keys'] = jms_ns.get('_array_get_subkey_filtered_keys')
    try:
        exec(code, namespace)
        log('[%s] [Banka] Modül yüklendi (exec tamamlandı), cache\'lendi.' % pName)
    except Exception as ex:
        log('[%s] Banka özellikleri yüklenemedi: %s' % (pName, str(ex)))
        return None
    _bank_features_namespace = namespace
    return _bank_features_namespace

def bank_merge_start():
    log('[%s] [Banka] bank_merge_start çağrıldı (wrapper).' % pName)
    ns = _get_bank_features_namespace()
    if ns and 'bank_merge_start' in ns:
        log('[%s] [Banka] Uzak bank_merge_start çalıştırılıyor.' % pName)
        ns['bank_merge_start']()
    else:
        log('[%s] Banka birleştirme kullanılamıyor.' % pName)

def bank_merge_stop():
    log('[%s] [Banka] bank_merge_stop çağrıldı (wrapper).' % pName)
    ns = _get_bank_features_namespace()
    if ns and 'bank_merge_stop' in ns:
        log('[%s] [Banka] Uzak bank_merge_stop çalıştırılıyor.' % pName)
        ns['bank_merge_stop']()

def bank_sort_start():
    log('[%s] [Banka] bank_sort_start çağrıldı (wrapper).' % pName)
    ns = _get_bank_features_namespace()
    if ns and 'bank_sort_start' in ns:
        log('[%s] [Banka] Uzak bank_sort_start çalıştırılıyor.' % pName)
        ns['bank_sort_start']()
    else:
        log('[%s] Banka sıralama kullanılamıyor.' % pName)

def bank_sort_stop():
    log('[%s] [Banka] bank_sort_stop çağrıldı (wrapper).' % pName)
    ns = _get_bank_features_namespace()
    if ns and 'bank_sort_stop' in ns:
        log('[%s] [Banka] Uzak bank_sort_stop çalıştırılıyor.' % pName)
        ns['bank_sort_stop']()

# Auto Dungeon (Tab 2): GitHub'dan indirilip exec ile çalıştırılır (ana pluginde Tab2 fonksiyon kodu yok)
_auto_dungeon_namespace = None

def _set_item_used_by_plugin(item):
    global itemUsedByPlugin
    itemUsedByPlugin = item

def _get_dimensional_item_activated():
    return dimensionalItemActivated

def _get_auto_dungeon_namespace():
    global _auto_dungeon_namespace
    if _auto_dungeon_namespace is not None:
        return _auto_dungeon_namespace
    log('[%s] [Auto-Dungeon] Modül indiriliyor: %s' % (pName, GITHUB_AUTO_BASE_DUNGEON_URL))
    try:
        req = urllib.request.Request(
            GITHUB_AUTO_BASE_DUNGEON_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Auto Dungeon modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    g = globals()
    namespace = {
        'gui': g['gui'], 'QtBind': QtBind, 'log': log, 'pName': pName,
        'get_config_dir': get_config_dir, 'get_character_data': get_character_data,
        'get_drops': get_drops, 'get_monsters': get_monsters, 'get_position': get_position,
        'start_bot': start_bot, 'stop_bot': stop_bot, 'set_training_position': set_training_position,
        'set_training_radius': set_training_radius, 'move_to': move_to,
        'get_inventory': get_inventory, 'get_item': get_item, 'get_npcs': get_npcs,
        'inject_joymax': inject_joymax, 'get_locale': get_locale, 'get_party': get_party,
        'sqlite3': sqlite3, 'struct': struct, 'time': time, 'threading': threading,
        'json': json, 'os': os,
        'WAIT_DROPS_DELAY_MAX': WAIT_DROPS_DELAY_MAX, 'COUNT_MOBS_DELAY': COUNT_MOBS_DELAY,
        '_is_license_valid': _is_license_valid,
        'set_item_used_by_plugin': _set_item_used_by_plugin,
        'get_dimensional_item_activated': _get_dimensional_item_activated,
        'lstMobs': g.get('lstMobs'), 'tbxMobs': g.get('tbxMobs'), 'lstMonsterCounter': g.get('lstMonsterCounter'),
        'cbxIgnoreGeneral': g.get('cbxIgnoreGeneral'), 'cbxOnlyCountGeneral': g.get('cbxOnlyCountGeneral'),
        'cbxIgnoreChampion': g.get('cbxIgnoreChampion'), 'cbxOnlyCountChampion': g.get('cbxOnlyCountChampion'),
        'cbxIgnoreGiant': g.get('cbxIgnoreGiant'), 'cbxOnlyCountGiant': g.get('cbxOnlyCountGiant'),
        'cbxIgnoreTitan': g.get('cbxIgnoreTitan'), 'cbxOnlyCountTitan': g.get('cbxOnlyCountTitan'),
        'cbxIgnoreStrong': g.get('cbxIgnoreStrong'), 'cbxOnlyCountStrong': g.get('cbxOnlyCountStrong'),
        'cbxIgnoreElite': g.get('cbxIgnoreElite'), 'cbxOnlyCountElite': g.get('cbxOnlyCountElite'),
        'cbxIgnoreUnique': g.get('cbxIgnoreUnique'), 'cbxOnlyCountUnique': g.get('cbxOnlyCountUnique'),
        'cbxIgnoreParty': g.get('cbxIgnoreParty'), 'cbxOnlyCountParty': g.get('cbxOnlyCountParty'),
        'cbxIgnoreChampionParty': g.get('cbxIgnoreChampionParty'), 'cbxOnlyCountChampionParty': g.get('cbxOnlyCountChampionParty'),
        'cbxIgnoreGiantParty': g.get('cbxIgnoreGiantParty'), 'cbxOnlyCountGiantParty': g.get('cbxOnlyCountGiantParty'),
        'cbxAcceptForgottenWorld': g.get('cbxAcceptForgottenWorld'),
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Auto Dungeon modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _auto_dungeon_namespace = namespace
    return _auto_dungeon_namespace

def _auto_dungeon_call(name, *args, **kwargs):
    ns = _get_auto_dungeon_namespace()
    if ns and name in ns:
        fn = ns[name]
        return fn(*args, **kwargs) if args or kwargs else fn()
    return None

def btnAddMob_clicked():
    _auto_dungeon_call('btnAddMob_clicked')

def btnRemMob_clicked():
    _auto_dungeon_call('btnRemMob_clicked')

def cbxIgnoreGeneral_clicked(checked):
    _auto_dungeon_call('cbxIgnoreGeneral_clicked', checked)
def cbxOnlyCountGeneral_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountGeneral_clicked', checked)
def cbxIgnoreChampion_clicked(checked):
    _auto_dungeon_call('cbxIgnoreChampion_clicked', checked)
def cbxOnlyCountChampion_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountChampion_clicked', checked)
def cbxIgnoreGiant_clicked(checked):
    _auto_dungeon_call('cbxIgnoreGiant_clicked', checked)
def cbxOnlyCountGiant_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountGiant_clicked', checked)
def cbxIgnoreTitan_clicked(checked):
    _auto_dungeon_call('cbxIgnoreTitan_clicked', checked)
def cbxOnlyCountTitan_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountTitan_clicked', checked)
def cbxIgnoreStrong_clicked(checked):
    _auto_dungeon_call('cbxIgnoreStrong_clicked', checked)
def cbxOnlyCountStrong_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountStrong_clicked', checked)
def cbxIgnoreElite_clicked(checked):
    _auto_dungeon_call('cbxIgnoreElite_clicked', checked)
def cbxOnlyCountElite_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountElite_clicked', checked)
def cbxIgnoreUnique_clicked(checked):
    _auto_dungeon_call('cbxIgnoreUnique_clicked', checked)
def cbxOnlyCountUnique_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountUnique_clicked', checked)
def cbxIgnoreParty_clicked(checked):
    _auto_dungeon_call('cbxIgnoreParty_clicked', checked)
def cbxOnlyCountParty_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountParty_clicked', checked)
def cbxIgnoreChampionParty_clicked(checked):
    _auto_dungeon_call('cbxIgnoreChampionParty_clicked', checked)
def cbxOnlyCountChampionParty_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountChampionParty_clicked', checked)
def cbxIgnoreGiantParty_clicked(checked):
    _auto_dungeon_call('cbxIgnoreGiantParty_clicked', checked)
def cbxOnlyCountGiantParty_clicked(checked):
    _auto_dungeon_call('cbxOnlyCountGiantParty_clicked', checked)

def cbxAcceptForgottenWorld_checked(checked):
    _auto_dungeon_call('cbxAcceptForgottenWorld_checked', checked)

def loadConfigs():
    ns = _get_auto_dungeon_namespace()
    if ns and 'loadConfigs' in ns:
        ns['loadConfigs']()

def AttackArea(args):
    ns = _get_auto_dungeon_namespace()
    if ns and 'AttackArea' in ns:
        return ns['AttackArea'](args)
    return 0

def GoDimensional(args):
    ns = _get_auto_dungeon_namespace()
    if ns and 'GoDimensional' in ns:
        return ns['GoDimensional'](args)
    return 0

def _call_remote_EnterToDimensional(name):
    ns = _get_auto_dungeon_namespace()
    if ns and 'EnterToDimensional' in ns:
        ns['EnterToDimensional'](name)

# Garden Dungeon (Tab 3): GitHub'dan indirilip exec ile çalıştırılır (ana pluginde Tab3 fonksiyon kodu yok)
_garden_dungeon_namespace = None

def _get_garden_dungeon_namespace():
    global _garden_dungeon_namespace
    if _garden_dungeon_namespace is not None:
        return _garden_dungeon_namespace
    try:
        req = urllib.request.Request(
            GITHUB_GARDEN_DUNGEON_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Garden Dungeon modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    g = globals()
    namespace = {
        'gui': g['gui'], 'QtBind': QtBind, 'log': log, 'pName': pName,
        'get_position': get_position, 'set_training_position': set_training_position,
        'set_training_radius': set_training_radius, 'set_training_script': set_training_script,
        'start_bot': start_bot, 'stop_bot': stop_bot, 'get_training_area': get_training_area,
        'os': os, 'time': time, 'threading': threading,
        '_download_garden_script': _download_garden_script,
        '_is_license_valid': _is_license_valid,
        'plugin_dir': os.path.dirname(os.path.abspath(__file__)),
        'tbxGardenScriptPath': g.get('tbxGardenScriptPath'),
        'lblGardenScriptStatus': g.get('lblGardenScriptStatus'),
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Garden Dungeon modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _garden_dungeon_namespace = namespace
    return _garden_dungeon_namespace

def garden_dungeon_select_normal():
    ns = _get_garden_dungeon_namespace()
    if ns and 'garden_dungeon_select_normal' in ns:
        ns['garden_dungeon_select_normal']()

def garden_dungeon_select_wizz_cleric():
    ns = _get_garden_dungeon_namespace()
    if ns and 'garden_dungeon_select_wizz_cleric' in ns:
        ns['garden_dungeon_select_wizz_cleric']()

def garden_dungeon_start():
    ns = _get_garden_dungeon_namespace()
    if ns and 'garden_dungeon_start' in ns:
        ns['garden_dungeon_start']()
    else:
        log('[%s] Garden Dungeon kullanılamıyor.' % pName)

def garden_dungeon_stop():
    ns = _get_garden_dungeon_namespace()
    if ns and 'garden_dungeon_stop' in ns:
        ns['garden_dungeon_stop']()

# Auto Hwt (Tab 4): GitHub'dan indirilip exec ile çalıştırılır (şu an placeholder)
_auto_hwt_namespace = None

def _get_auto_hwt_namespace():
    global _auto_hwt_namespace
    if _auto_hwt_namespace is not None:
        return _auto_hwt_namespace
    try:
        req = urllib.request.Request(
            GITHUB_AUTO_HWT_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Auto Hwt modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    namespace = {
        'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'gui': gui, 'QtBind': QtBind,
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Auto Hwt modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _auto_hwt_namespace = namespace
    return _auto_hwt_namespace

# ______________________________ Oto Kervan (Tab 5 - GitHub'dan uzaktan) ______________________________ #
_caravan_namespace = None

def _get_caravan_namespace():
    global _caravan_namespace
    if _caravan_namespace is not None:
        return _caravan_namespace
    try:
        req = urllib.request.Request(
            GITHUB_CARAVAN_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Oto Kervan modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    namespace = {
        'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'gui': gui, 'QtBind': QtBind, 'plugin_dir': plugin_dir,
        'get_config_dir': get_config_dir, 'get_config_path': get_config_path,
        'get_character_data': get_character_data, 'get_position': get_position,
        'get_training_area': get_training_area, 'set_training_area': set_training_area,
        'set_training_script': set_training_script, 'set_training_position': set_training_position,
        'set_training_radius': set_training_radius, 'start_bot': start_bot, 'stop_bot': stop_bot,
        'generate_script': generate_script,
        'lblKervanProfile': lblKervanProfile, 'lstKervanScripts': lstKervanScripts, 'lblKervanStatus': lblKervanStatus,
        'GITHUB_REPO': GITHUB_REPO, 'GITHUB_CARAVAN_FOLDER': GITHUB_CARAVAN_FOLDER,
        'GITHUB_CARAVAN_BRANCH': GITHUB_CARAVAN_BRANCH,
        'GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE': GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE,
        'GITHUB_CARAVAN_PROFILE_FOLDER': GITHUB_CARAVAN_PROFILE_FOLDER,
        'GITHUB_CARAVAN_PROFILE_JSON_FILENAME': GITHUB_CARAVAN_PROFILE_JSON_FILENAME,
        'GITHUB_CARAVAN_PROFILE_DB3_FILENAME': GITHUB_CARAVAN_PROFILE_DB3_FILENAME,
        'os': os, 'json': json, 'time': time, 'threading': threading,
        'urllib': urllib, 'shutil': shutil, 'copy': copy, 'math': math,
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Oto Kervan modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _caravan_namespace = namespace
    return _caravan_namespace

def kervan_refresh_list():
    ns = _get_caravan_namespace()
    if ns and 'kervan_refresh_list' in ns:
        ns['kervan_refresh_list']()
    else:
        log('[%s] Oto Kervan kullanılamıyor.' % pName)

def kervan_start():
    ns = _get_caravan_namespace()
    if ns and 'kervan_start' in ns:
        ns['kervan_start']()
    else:
        log('[%s] Oto Kervan kullanılamıyor.' % pName)

def kervan_stop():
    ns = _get_caravan_namespace()
    if ns and 'kervan_stop' in ns:
        ns['kervan_stop']()

# ______________________________ Script Komutları (Tab 6 - GitHub'dan uzaktan) ______________________________ #
_script_commands_namespace = None

def _get_script_commands_namespace():
    global _script_commands_namespace
    if _script_commands_namespace is not None:
        return _script_commands_namespace
    try:
        req = urllib.request.Request(
            GITHUB_SCRIPT_COMMANDS_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Script Komutları modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    script_cmds_path = get_config_dir()[:-7] if get_config_dir() else ''
    namespace = {
        'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'gui': gui, 'QtBind': QtBind, 'script_cmds_path': script_cmds_path,
        '_script_cmds_SaveName': _script_cmds_SaveName, '_script_cmds_RecordBtn': _script_cmds_RecordBtn,
        '_script_cmds_Display': _script_cmds_Display, '_script_cmds_cbxShowPackets': _script_cmds_cbxShowPackets,
        'get_party': get_party, 'inject_joymax': inject_joymax, 'show_notification': show_notification,
        'create_notification': create_notification, 'play_wav': play_wav, 'set_training_script': set_training_script,
        'get_client': get_client, 'start_bot': start_bot, 'stop_bot': stop_bot, 'start_trace': start_trace,
        'get_active_skills': get_active_skills, 'get_inventory': get_inventory, 'get_pets': get_pets,
        'get_config_dir': get_config_dir, 'get_character_data': get_character_data, 'get_profile': get_profile,
        'set_profile': set_profile, 'set_training_area': set_training_area, 'get_position': get_position,
        'os': os, 'json': json, 'struct': struct, 'threading': threading,
        'datetime': datetime, 'timedelta': timedelta, 'subprocess': subprocess, 'signal': signal,
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Script Komutları modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _script_commands_namespace = namespace
    return _script_commands_namespace

def _sc_ns_call(name, args=None, default=0):
    ns = _get_script_commands_namespace()
    if ns and name in ns:
        f = ns[name]
        if args is not None:
            return f(args)
        return f()
    return default

def LeaveParty(args):
    return _sc_ns_call('LeaveParty', args)

def Notification(args):
    return _sc_ns_call('Notification', args)

def NotifyList(args):
    return _sc_ns_call('NotifyList', args)

def PlaySound(args):
    return _sc_ns_call('PlaySound', args)

def SetScript(args):
    return _sc_ns_call('SetScript', args)

def CloseBot(args):
    return _sc_ns_call('CloseBot', args)

def GoClientless(args):
    return _sc_ns_call('GoClientless', args)

def StartBot(args):
    return _sc_ns_call('StartBot', args)

def StopStart(args):
    return _sc_ns_call('StopStart', args)

def StartTrace(args):
    return _sc_ns_call('StartTrace', args)

def RemoveSkill(args):
    return _sc_ns_call('RemoveSkill', args)

def Drop(args):
    return _sc_ns_call('Drop', args)

def OpenphBot(args):
    return _sc_ns_call('OpenphBot', args)

def DismountPet(args):
    return _sc_ns_call('DismountPet', args)

def UnsummonPet(args):
    return _sc_ns_call('UnsummonPet', args)

def ResetWeapons(args):
    return _sc_ns_call('ResetWeapons', args)

def SetArea(args):
    return _sc_ns_call('SetArea', args)

def ExchangePlayer(args):
    return _sc_ns_call('ExchangePlayer', args)

def ChangeBotOption(args):
    return _sc_ns_call('ChangeBotOption', args)

def CustomNPC(args):
    return _sc_ns_call('CustomNPC', args)

def sromanager(args):
    """Script-Command: Chat/Script -> paket eşlemesi (uzaktan modül)"""
    ns = _get_script_command_maker_namespace()
    if ns and 'sromanager' in ns:
        return ns['sromanager'](args)
    return 500

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

def cbxDoNothing():
    """Checkbox tıklamasında boş callback (durum sadece okunur)"""
    pass

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
_tab9_widgets = []
_tab10_widgets = []
_tab11_widgets = []
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
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
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
    _tab_move(_tab8_widgets, False)
    _current_tab = 8
    _tab_apply_scroll()

def _show_tab9():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, True)
    _tab_move(_tab9_widgets, False)
    _current_tab = 9
    _tab_apply_scroll()

def _add_tab7(w, x, y):
    _tab7_widgets.append((w, x, y))

def _add_tab8(w, x, y):
    _tab8_widgets.append((w, x, y))

def _add_tab9(w, x, y):
    _tab9_widgets.append((w, x, y))

def _show_tab10():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab11_widgets, True)
    _tab_move(_tab10_widgets, False)
    _current_tab = 10
    _tab_apply_scroll()

def _show_tab11():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, True)
    _tab_move(_tab8_widgets, True)
    _tab_move(_tab9_widgets, True)
    _tab_move(_tab10_widgets, True)
    _tab_move(_tab11_widgets, False)
    _current_tab = 11
    _tab_apply_scroll()

def _add_tab10(w, x, y):
    _tab10_widgets.append((w, x, y))

def _add_tab11(w, x, y):
    _tab11_widgets.append((w, x, y))

# Tab bar yapılandırması
_tab_bar_y = 10
_tab_bar_x = 10
_tab_visible_width = 552
_tab_scroll_offset = 0

# Sıra: Hakkımda, Banka/Çanta, Auto Dungeon, Garden, Auto Hwt, Oto Kervan, Script, Envanter, TargetSupport, Sıralı Bless, Script-Command
_tab_original_positions = [10, 90, 205, 288, 383, 463, 543, 631, 723, 807, 887]
_tab_widths = [80, 115, 83, 95, 80, 80, 88, 92, 85, 65, 115]

_tab_btn1 = QtBind.createButton(gui, '_show_tab1', 'Hakkımda', 10, _tab_bar_y)
_tab_btn2 = QtBind.createButton(gui, '_show_tab2', 'Banka/Çanta Birleştir', 90, _tab_bar_y)
_tab_btn3 = QtBind.createButton(gui, '_show_tab3', 'Auto Dungeon', 205, _tab_bar_y)
_tab_btn4 = QtBind.createButton(gui, '_show_tab4', 'Garden Dungeon', 288, _tab_bar_y)
_tab_btn5 = QtBind.createButton(gui, '_show_tab5', 'Auto Hwt', 383, _tab_bar_y)
_tab_btn6 = QtBind.createButton(gui, '_show_tab6', 'Oto Kervan', 463, _tab_bar_y)
_tab_btn7 = QtBind.createButton(gui, '_show_tab7', 'Script Komutları', 543, _tab_bar_y)
_tab_btn8 = QtBind.createButton(gui, '_show_tab8', 'Envanter Sayacı', 631, _tab_bar_y)
_tab_btn9 = QtBind.createButton(gui, '_show_tab9', 'TargetSupport', 723, _tab_bar_y)
_tab_btn10 = QtBind.createButton(gui, '_show_tab10', 'Sıralı Bless', 807, _tab_bar_y)
_tab_btn11 = QtBind.createButton(gui, '_show_tab11', 'Script - Command', 887, _tab_bar_y)

_tab_buttons = [_tab_btn1, _tab_btn2, _tab_btn3, _tab_btn4, _tab_btn5, _tab_btn6, _tab_btn7, _tab_btn8, _tab_btn9, _tab_btn10, _tab_btn11]

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
# Ana içerik container'ı oluşturulmadı (stroke yok) - orijinal Bless Queue gibi

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

# Tab 2 butonlarını lisans korumasına ekle
_protected_buttons[2] = [btnAddMob, btnRemMob, cbxIgnoreGeneral, cbxOnlyCountGeneral, cbxIgnoreChampion, cbxOnlyCountChampion,
    cbxIgnoreGiant, cbxOnlyCountGiant, cbxIgnoreTitan, cbxOnlyCountTitan, cbxIgnoreStrong, cbxOnlyCountStrong,
    cbxIgnoreElite, cbxOnlyCountElite, cbxIgnoreUnique, cbxOnlyCountUnique, cbxIgnoreParty, cbxOnlyCountParty,
    cbxIgnoreChampionParty, cbxOnlyCountChampionParty, cbxIgnoreGiantParty, cbxOnlyCountGiantParty, cbxAcceptForgottenWorld]

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
_btn_garden_wizz = QtBind.createButton(gui, 'garden_dungeon_select_wizz_cleric', 'Wizz/Cleric', _gd_btn_center_x, _gd_type_y)
_add_tab3(_btn_garden_wizz, _gd_btn_center_x, _gd_type_y)
_btn_garden_normal = QtBind.createButton(gui, 'garden_dungeon_select_normal', 'Normal', _gd_btn_center_x + 85, _gd_type_y)
_add_tab3(_btn_garden_normal, _gd_btn_center_x + 85, _gd_type_y)

# Başla/Durdur butonları (altta, hizalı)
_gd_btn_y = _gd_type_y + 30
_btn_garden_start = QtBind.createButton(gui, 'garden_dungeon_start', '  Başla  ', _gd_btn_center_x, _gd_btn_y)
_add_tab3(_btn_garden_start, _gd_btn_center_x, _gd_btn_y)
_btn_garden_stop = QtBind.createButton(gui, 'garden_dungeon_stop', ' Durdur ', _gd_btn_center_x + 85, _gd_btn_y)
_add_tab3(_btn_garden_stop, _gd_btn_center_x + 85, _gd_btn_y)

_gd_status_y = _gd_btn_y + 30
lblGardenScriptStatus = QtBind.createLabel(gui, 'Durum: Hazır', _gd_title_x, _gd_status_y)
_add_tab3(lblGardenScriptStatus, _gd_title_x, _gd_status_y)

_gd_note_y = _gd_status_y + 22
_add_tab3(QtBind.createLabel(gui, 'Script türünü seç, sonra Başlat', _gd_title_x, _gd_note_y), _gd_title_x, _gd_note_y)

# Tab 3 butonlarını lisans korumasına ekle
_protected_buttons[3] = [_btn_garden_wizz, _btn_garden_normal, _btn_garden_start, _btn_garden_stop]

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

# Tab 4 butonları lisans korumasına (şu an boş; özellik eklenince eklenecek)
_protected_buttons[4] = []

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
_btn_kervan_refresh = QtBind.createButton(gui, 'kervan_refresh_list', ' Yenile ', _kervan_x, _kervan_btn_y)
_add_tab5(_btn_kervan_refresh, _kervan_x, _kervan_btn_y)
_btn_kervan_start = QtBind.createButton(gui, 'kervan_start', ' Başla ', _kervan_x + 80, _kervan_btn_y)
_add_tab5(_btn_kervan_start, _kervan_x + 80, _kervan_btn_y)
_btn_kervan_stop = QtBind.createButton(gui, 'kervan_stop', ' Durdur ', _kervan_x + 160, _kervan_btn_y)
_add_tab5(_btn_kervan_stop, _kervan_x + 160, _kervan_btn_y)

lblKervanStatus = QtBind.createLabel(gui, 'Durum: Hazır', _kervan_x, _kervan_btn_y + 28)
_add_tab5(lblKervanStatus, _kervan_x, _kervan_btn_y + 28)

# Tab 5 butonları lisans korumasına
_protected_buttons[5] = [lblKervanProfile, lstKervanScripts, lblKervanStatus, _btn_kervan_refresh, _btn_kervan_start, _btn_kervan_stop]

def _caravan_init_load():
    """Init sonrası karavan profilini (yoksa) oluşturur, ardından script listesini arka planda yükler (uzaktan modül)."""
    time.sleep(2)
    try:
        ns = _get_caravan_namespace()
        if ns and '_caravan_ensure_karavan_profile_on_init' in ns:
            ns['_caravan_ensure_karavan_profile_on_init']()
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
    ns = _get_script_commands_namespace()
    if ns and 'script_cmds_button_start' in ns:
        ns['script_cmds_button_start']()
    else:
        log('[%s] Script Komutları kullanılamıyor.' % pName)

def script_cmds_button_ShowCmds():
    ns = _get_script_commands_namespace()
    if ns and 'script_cmds_button_ShowCmds' in ns:
        ns['script_cmds_button_ShowCmds']()

def script_cmds_button_DelCmds():
    ns = _get_script_commands_namespace()
    if ns and 'script_cmds_button_DelCmds' in ns:
        ns['script_cmds_button_DelCmds']()

def script_cmds_button_ShowPackets():
    ns = _get_script_commands_namespace()
    if ns and 'script_cmds_button_ShowPackets' in ns:
        ns['script_cmds_button_ShowPackets']()

def script_cmds_cbxAuto_clicked(checked):
    ns = _get_script_commands_namespace()
    if ns and 'script_cmds_cbxAuto_clicked' in ns:
        ns['script_cmds_cbxAuto_clicked'](checked)

# Tab 6 butonları lisans korumasına
_protected_buttons[6] = [_script_cmds_SaveName, _script_cmds_RecordBtn, _script_cmds_Display,
    _script_cmds_ShowCommandsBtn, _script_cmds_DeleteCommandsBtn, _script_cmds_ShowPacketsBtn,
    _script_cmds_cbxShowPackets]

# Tab 7 - Envanter Sayacı (TR_InventoryCounter) - mantık GitHub'dan uzaktan yüklenir
_inv_cnt_name = 'sromanager_EnvanterSayaci'

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

# Envanter Sayacı (Tab 7) - GitHub'dan uzaktan
_inventory_counter_namespace = None

def _get_inventory_counter_namespace():
    global _inventory_counter_namespace
    if _inventory_counter_namespace is not None:
        return _inventory_counter_namespace
    try:
        req = urllib.request.Request(
            GITHUB_INVENTORY_COUNTER_URL,
            headers={'User-Agent': 'phBot-SROManager/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode('utf-8')
    except Exception as ex:
        log('[%s] Envanter Sayacı modülü indirilemedi: %s' % (pName, str(ex)))
        return None
    namespace = {
        'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'gui': gui, 'QtBind': QtBind, 'os': os, 'json': json,
        'get_config_dir': get_config_dir, 'get_character_data': get_character_data,
        'phBotChat': phBotChat, 'get_party': get_party, 'get_guild': get_guild,
        'get_inventory': get_inventory, 'get_storage': get_storage, 'get_pets': get_pets,
        'get_guild_storage': get_guild_storage, 'get_job_pouch': get_job_pouch,
        '_inv_cnt_name': _inv_cnt_name,
        '_inv_cnt_lstLeaders': _inv_cnt_lstLeaders, '_inv_cnt_lstInfo': _inv_cnt_lstInfo,
        '_inv_cnt_tbxLeaders': _inv_cnt_tbxLeaders, '_inv_cnt_tbxTargetPrivate': _inv_cnt_tbxTargetPrivate,
        '_inv_cnt_cbxAllChat': _inv_cnt_cbxAllChat, '_inv_cnt_cbxPartyChat': _inv_cnt_cbxPartyChat,
        '_inv_cnt_cbxGuildChat': _inv_cnt_cbxGuildChat, '_inv_cnt_cbxUnionChat': _inv_cnt_cbxUnionChat,
        '_inv_cnt_cbxPrivateChatSender': _inv_cnt_cbxPrivateChatSender,
        '_inv_cnt_cbxPrivateChatTarget': _inv_cnt_cbxPrivateChatTarget,
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] Envanter Sayacı modülü yüklenemedi: %s' % (pName, str(ex)))
        return None
    _inventory_counter_namespace = namespace
    return _inventory_counter_namespace

def inv_cnt_getPath():
    return get_config_dir() + _inv_cnt_name + "\\"

def _inv_cnt_ns_call(name, *args):
    ns = _get_inventory_counter_namespace()
    if ns and name in ns:
        f = ns[name]
        return f(*args)
    return None

def inv_cnt_loadConfigs():
    _inv_cnt_ns_call('inv_cnt_loadConfigs')

def inv_cnt_saveConfigs():
    _inv_cnt_ns_call('inv_cnt_saveConfigs')

def inv_cnt_btnkarakter_clicked():
    _inv_cnt_ns_call('inv_cnt_btnkarakter_clicked')

def inv_cnt_btnelixir_clicked():
    _inv_cnt_ns_call('inv_cnt_btnelixir_clicked')

def inv_cnt_btnevent_clicked():
    _inv_cnt_ns_call('inv_cnt_btnevent_clicked')

def inv_cnt_btncoin_clicked():
    _inv_cnt_ns_call('inv_cnt_btncoin_clicked')

def inv_cnt_btnstone_clicked():
    _inv_cnt_ns_call('inv_cnt_btnstone_clicked')

def inv_cnt_btnfgw_clicked():
    _inv_cnt_ns_call('inv_cnt_btnfgw_clicked')

def inv_cnt_btnegpty_clicked():
    _inv_cnt_ns_call('inv_cnt_btnegpty_clicked')

def inv_cnt_btnstall_clicked():
    _inv_cnt_ns_call('inv_cnt_btnstall_clicked')

def inv_cnt_btnClearInfo_clicked():
    _inv_cnt_ns_call('inv_cnt_btnClearInfo_clicked')

def inv_cnt_btnAddLeader_clicked():
    _inv_cnt_ns_call('inv_cnt_btnAddLeader_clicked')

def inv_cnt_btnRemLeader_clicked():
    _inv_cnt_ns_call('inv_cnt_btnRemLeader_clicked')

def inv_cnt_cbxAllChat_clicked(checked):
    _inv_cnt_ns_call('inv_cnt_cbxAllChat_clicked', checked)

def inv_cnt_cbxPartyChat_clicked(checked):
    _inv_cnt_ns_call('inv_cnt_cbxPartyChat_clicked', checked)

def inv_cnt_cbxGuildChat_clicked(checked):
    _inv_cnt_ns_call('inv_cnt_cbxGuildChat_clicked', checked)

def inv_cnt_cbxUnionChat_clicked(checked):
    _inv_cnt_ns_call('inv_cnt_cbxUnionChat_clicked', checked)

def inv_cnt_cbxPrivateChatSender_clicked(checked):
    _inv_cnt_ns_call('inv_cnt_cbxPrivateChatSender_clicked', checked)

def inv_cnt_cbxPrivateChatTarget_clicked(checked):
    _inv_cnt_ns_call('inv_cnt_cbxPrivateChatTarget_clicked', checked)

def inv_cnt_btnSaveChatSettings_clicked():
    _inv_cnt_ns_call('inv_cnt_btnSaveChatSettings_clicked')

def _inv_cnt_handle_chat(t, player, msg):
    _inv_cnt_ns_call('_inv_cnt_handle_chat', t, player, msg)

# Tab 7 butonları lisans korumasına
_protected_buttons[7] = [_inv_cnt_btnkarakter, _inv_cnt_btnelixir, _inv_cnt_btnevent, _inv_cnt_btncoin,
    _inv_cnt_btnstone, _inv_cnt_btnfgw, _inv_cnt_btnegpty, _inv_cnt_btnstall, _inv_cnt_tbxLeaders,
    _inv_cnt_btnAddLeader, _inv_cnt_lstLeaders, _inv_cnt_btnRemLeader, _inv_cnt_btnClearInfo,
    _inv_cnt_cbxAllChat, _inv_cnt_cbxPartyChat, _inv_cnt_cbxGuildChat, _inv_cnt_cbxUnionChat,
    _inv_cnt_cbxPrivateChatSender, _inv_cnt_cbxPrivateChatTarget, _inv_cnt_tbxTargetPrivate,
    _inv_cnt_btnSaveChatSettings, _inv_cnt_lstInfo]

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
_add_tab8(QtBind.createLabel(gui, '• TargetSupport', _col2_x, _features_y + 82), _col2_x, _features_y + 82)
_add_tab8(QtBind.createLabel(gui, '• Sıralı Bless', _col2_x, _features_y + 98), _col2_x, _features_y + 98)

# TargetSupport (Tab 9)
_ts_x = _tab_bar_x + 20
_ts_y = _content_y + 10
_ts_cbxEnabled = QtBind.createCheckBox(gui, 'cbxDoNothing', 'Enabled', _ts_x, _ts_y)
_add_tab9(_ts_cbxEnabled, _ts_x, _ts_y)
_ts_cbxDefensive = QtBind.createCheckBox(gui, 'cbxDoNothing', 'Defensive Mode', _ts_x + 85, _ts_y)
_add_tab9(_ts_cbxDefensive, _ts_x + 85, _ts_y)
_add_tab9(QtBind.createLabel(gui, '* Lider listesi', _ts_x + 2, _ts_y + 25), _ts_x + 2, _ts_y + 25)
_ts_tbxLeaders = QtBind.createLineEdit(gui, "", _ts_x, _ts_y + 41, 100, 20)
_add_tab9(_ts_tbxLeaders, _ts_x, _ts_y + 41)
_ts_lvwLeaders = QtBind.createList(gui, _ts_x, _ts_y + 62, 176, 60)
_add_tab9(_ts_lvwLeaders, _ts_x, _ts_y + 62)
_ts_btnAddLeader = QtBind.createButton(gui, 'ts_btnAddLeader_clicked', "  Ekle  ", _ts_x + 107, _ts_y + 40)
_add_tab9(_ts_btnAddLeader, _ts_x + 107, _ts_y + 40)
_ts_btnRemLeader = QtBind.createButton(gui, 'ts_btnRemLeader_clicked', "  Sil  ", _ts_x + 55, _ts_y + 121)
_add_tab9(_ts_btnRemLeader, _ts_x + 55, _ts_y + 121)

# TargetSupport - Sağ taraf: Özellikler
_ts_features_x = _ts_x + 220
_ts_features_y = _ts_y
_add_tab9(QtBind.createLabel(gui, 'xTargetSupport Özellikleri', _ts_features_x, _ts_features_y), _ts_features_x, _ts_features_y)
_add_tab9(QtBind.createLabel(gui, '• Liderin saldırdığı düşmana anında otomatik saldırır', _ts_features_x, _ts_features_y + 20), _ts_features_x, _ts_features_y + 20)
_add_tab9(QtBind.createLabel(gui, '• Defensive: Liderinize saldırana otomatik döner', _ts_features_x, _ts_features_y + 36), _ts_features_x, _ts_features_y + 36)
_add_tab9(QtBind.createLabel(gui, '• Birden fazla oyuncu lider olarak ayarlanabilir', _ts_features_x, _ts_features_y + 52), _ts_features_x, _ts_features_y + 52)
_add_tab9(QtBind.createLabel(gui, '• Fortress War, Unique, Guild party senkron saldırı', _ts_features_x, _ts_features_y + 68), _ts_features_x, _ts_features_y + 68)
_add_tab9(QtBind.createLabel(gui, '• TARGET ON / OFF ile chat üzerinden yönetim', _ts_features_x, _ts_features_y + 84), _ts_features_x, _ts_features_y + 84)
_add_tab9(QtBind.createLabel(gui, '• Kapsamlı arayüz ve profil desteği', _ts_features_x, _ts_features_y + 100), _ts_features_x, _ts_features_y + 100)

# TargetSupport modülü
_target_support_namespace = None

def _get_target_support_namespace():
    global _target_support_namespace
    if _target_support_namespace is not None:
        return _target_support_namespace
    code = None
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(plugin_dir, 'feature', 'target_support.py')
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as ex:
            log('[%s] [TargetSupport] Yerel modül okunamadı: %s' % (pName, str(ex)))
    if not code:
        try:
            req = urllib.request.Request(
                GITHUB_TARGET_SUPPORT_URL,
                headers={'User-Agent': 'phBot-SROManager/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                code = r.read().decode('utf-8')
        except Exception as ex:
            log('[%s] [TargetSupport] Modül indirilemedi: %s' % (pName, str(ex)))
            return None
    namespace = {
        'gui': gui, 'QtBind': QtBind, 'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'get_config_dir': get_config_dir, 'get_character_data': get_character_data, 'get_party': get_party,
        'inject_joymax': inject_joymax, 'get_locale': get_locale, 'struct': struct, 'os': os, 'json': json,
        '_ts_cbxEnabled': _ts_cbxEnabled, '_ts_cbxDefensive': _ts_cbxDefensive,
        '_ts_tbxLeaders': _ts_tbxLeaders, '_ts_lvwLeaders': _ts_lvwLeaders,
    }
    try:
        exec(code, namespace)
    except Exception as ex:
        log('[%s] [TargetSupport] Modül yüklenemedi: %s' % (pName, str(ex)))
        return None
    _target_support_namespace = namespace
    return _target_support_namespace

def ts_btnAddLeader_clicked():
    ns = _get_target_support_namespace()
    if ns and 'ts_btnAddLeader_clicked' in ns:
        ns['ts_btnAddLeader_clicked']()

def ts_btnRemLeader_clicked():
    ns = _get_target_support_namespace()
    if ns and 'ts_btnRemLeader_clicked' in ns:
        ns['ts_btnRemLeader_clicked']()

# Sıralı Bless (Tab 10) - Bless Queue v1.4.3 layout, ekrana sığacak şekilde (LIST_H=105)
# Orijinal: LX1=10, LIST_W=220, LIST_H=120, LY=35, SHIFT_Y=20, PBX=240, LX2=340, QBX=570
_bq_x0 = _tab_bar_x
_bq_y0 = _content_y
_bq_LW = 220
_bq_LH = 105
_bq_LY = 35
_bq_SY = 20
_bq_LX1 = _bq_x0 + 10
_bq_PBX = _bq_LX1 + _bq_LW + 10
_bq_LX2 = _bq_PBX + 85 + 15
_bq_QBX = _bq_LX2 + _bq_LW + 10
_bq_BH = 22
_bq_BG = 4
_bq_BY = _bq_y0 + (_bq_LY + _bq_LH + 10) + _bq_SY

_bq_cbEnable = QtBind.createCheckBox(gui, 'bq_cb_enable_changed', 'Aktif (bu istemci)', _bq_x0 + 10, _bq_y0 + 10)
_add_tab10(_bq_cbEnable, _bq_x0 + 10, _bq_y0 + 10)
_add_tab10(QtBind.createLabel(gui, 'Sıralı Bless v1.4', _bq_x0 + 240, _bq_y0 + 12), _bq_x0 + 240, _bq_y0 + 12)
_add_tab10(QtBind.createLabel(gui, 'Parti', _bq_LX1, _bq_y0 + (_bq_LY - 15) + _bq_SY), _bq_LX1, _bq_y0 + (_bq_LY - 15) + _bq_SY)
_bq_lstParty = QtBind.createList(gui, _bq_LX1, _bq_y0 + _bq_LY + _bq_SY, _bq_LW, _bq_LH)
_add_tab10(_bq_lstParty, _bq_LX1, _bq_y0 + _bq_LY + _bq_SY)
_bq_btnRefresh = QtBind.createButton(gui, 'bq_btn_refresh', 'Yenile', _bq_PBX, _bq_y0 + (_bq_LY + 0 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnRefresh, _bq_PBX, _bq_y0 + (_bq_LY + 0 * (_bq_BH + _bq_BG)) + _bq_SY)
_bq_btnAddAll = QtBind.createButton(gui, 'bq_btn_add_all', 'Tümünü Ekle', _bq_PBX, _bq_y0 + (_bq_LY + 1 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnAddAll, _bq_PBX, _bq_y0 + (_bq_LY + 1 * (_bq_BH + _bq_BG)) + _bq_SY)
_bq_btnAddSel = QtBind.createButton(gui, 'bq_btn_add_selected', 'Ekle →', _bq_PBX, _bq_y0 + (_bq_LY + 2 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnAddSel, _bq_PBX, _bq_y0 + (_bq_LY + 2 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(QtBind.createLabel(gui, 'Bless Kuyruğu', _bq_LX2, _bq_y0 + (_bq_LY - 15) + _bq_SY), _bq_LX2, _bq_y0 + (_bq_LY - 15) + _bq_SY)
_bq_lstQueue = QtBind.createList(gui, _bq_LX2, _bq_y0 + _bq_LY + _bq_SY, _bq_LW, _bq_LH)
_add_tab10(_bq_lstQueue, _bq_LX2, _bq_y0 + _bq_LY + _bq_SY)
_bq_btnSendQueue = QtBind.createButton(gui, 'bq_btn_send_queue', 'Sırayı Gönder', _bq_QBX, _bq_y0 + (_bq_LY + 0 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnSendQueue, _bq_QBX, _bq_y0 + (_bq_LY + 0 * (_bq_BH + _bq_BG)) + _bq_SY)
_bq_btnRemSel = QtBind.createButton(gui, 'bq_btn_remove_selected', 'Sil', _bq_QBX, _bq_y0 + (_bq_LY + 1 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnRemSel, _bq_QBX, _bq_y0 + (_bq_LY + 1 * (_bq_BH + _bq_BG)) + _bq_SY)
_bq_btnUp = QtBind.createButton(gui, 'bq_btn_queue_up', 'Yukarı', _bq_QBX, _bq_y0 + (_bq_LY + 2 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnUp, _bq_QBX, _bq_y0 + (_bq_LY + 2 * (_bq_BH + _bq_BG)) + _bq_SY)
_bq_btnDown = QtBind.createButton(gui, 'bq_btn_queue_down', 'Aşağı', _bq_QBX, _bq_y0 + (_bq_LY + 3 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnDown, _bq_QBX, _bq_y0 + (_bq_LY + 3 * (_bq_BH + _bq_BG)) + _bq_SY)
_bq_btnClearQ = QtBind.createButton(gui, 'bq_btn_clear_q', 'Tümünü Sil', _bq_QBX, _bq_y0 + (_bq_LY + 4 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(_bq_btnClearQ, _bq_QBX, _bq_y0 + (_bq_LY + 4 * (_bq_BH + _bq_BG)) + _bq_SY)
_add_tab10(QtBind.createLabel(gui, 'BlessID:', _bq_x0 + 10, _bq_BY + 2), _bq_x0 + 10, _bq_BY + 2)
_bq_tbBlessId = QtBind.createLineEdit(gui, "0x2DF6", _bq_x0 + 60, _bq_BY, 80, 20)
_add_tab10(_bq_tbBlessId, _bq_x0 + 60, _bq_BY)
_bq_btnSaveBless = QtBind.createButton(gui, 'bq_btn_save_bless', 'Kaydet', _bq_x0 + 145, _bq_BY - 1)
_add_tab10(_bq_btnSaveBless, _bq_x0 + 145, _bq_BY - 1)
_bq_btnScanBless = QtBind.createButton(gui, 'bq_btn_scan_bless', 'Tara', _bq_x0 + 200, _bq_BY - 1)
_add_tab10(_bq_btnScanBless, _bq_x0 + 200, _bq_BY - 1)
_bq_btnStopBless = QtBind.createButton(gui, 'bq_btn_stop_bless', 'Durdur', _bq_x0 + 255, _bq_BY - 1)
_add_tab10(_bq_btnStopBless, _bq_x0 + 255, _bq_BY - 1)
_bq_cbSay = QtBind.createCheckBox(gui, 'bq_cb_say_changed', 'Partiye söyle', _bq_x0 + 10, _bq_BY + 28)
_add_tab10(_bq_cbSay, _bq_x0 + 10, _bq_BY + 28)
_add_tab10(QtBind.createLabel(gui, 'Spam:', _bq_LX2, _bq_BY + 2), _bq_LX2, _bq_BY + 2)
_bq_tbSpam = QtBind.createLineEdit(gui, "2.5", _bq_LX2 + 45, _bq_BY, 55, 20)
_add_tab10(_bq_tbSpam, _bq_LX2 + 45, _bq_BY)
_add_tab10(QtBind.createLabel(gui, 'Skip:', _bq_LX2 + 110, _bq_BY + 2), _bq_LX2 + 110, _bq_BY + 2)
_bq_tbSkip = QtBind.createLineEdit(gui, "15", _bq_LX2 + 155, _bq_BY, 55, 20)
_add_tab10(_bq_tbSkip, _bq_LX2 + 155, _bq_BY)
_add_tab10(QtBind.createLabel(gui, 'Süre:', _bq_LX2, _bq_BY + 28), _bq_LX2, _bq_BY + 28)
_bq_tbDur = QtBind.createLineEdit(gui, "45", _bq_LX2 + 45, _bq_BY + 26, 55, 20)
_add_tab10(_bq_tbDur, _bq_LX2 + 45, _bq_BY + 26)
_bq_btnSaveTimers = QtBind.createButton(gui, 'bq_btn_save_timers', 'Kaydet', _bq_LX2 + 110, _bq_BY + 25)
_add_tab10(_bq_btnSaveTimers, _bq_LX2 + 110, _bq_BY + 25)
_add_tab10(QtBind.createLabel(gui, 'Cleric Silah:', _bq_x0 + 10, _bq_y0 + 218), _bq_x0 + 10, _bq_y0 + 218)
_bq_cmbClericWeapon = QtBind.createCombobox(gui, _bq_x0 + 100, _bq_y0 + 216, 220, 20)
_add_tab10(_bq_cmbClericWeapon, _bq_x0 + 100, _bq_y0 + 216)
_add_tab10(QtBind.createLabel(gui, 'Ana Silah:', _bq_x0 + 10, _bq_y0 + 248), _bq_x0 + 10, _bq_y0 + 248)
_bq_cmbMainWeapon = QtBind.createCombobox(gui, _bq_x0 + 100, _bq_y0 + 246, 220, 20)
_add_tab10(_bq_cmbMainWeapon, _bq_x0 + 100, _bq_y0 + 246)
_bq_btnWRefresh = QtBind.createButton(gui, 'bq_btn_wrefresh', 'Yenile', _bq_x0 + 350, _bq_y0 + 226)
_add_tab10(_bq_btnWRefresh, _bq_x0 + 350, _bq_y0 + 226)
_bq_btnWSave = QtBind.createButton(gui, 'bq_btn_wsave', 'Kaydet', _bq_x0 + 450, _bq_y0 + 226)
_add_tab10(_bq_btnWSave, _bq_x0 + 450, _bq_y0 + 226)
_bq_btnHelpEN = QtBind.createButton(gui, 'bq_btn_help_en', 'Yardım', _bq_x0 + 520, _bq_y0 + 8)
_add_tab10(_bq_btnHelpEN, _bq_x0 + 520, _bq_y0 + 8)

# Bless Queue modülü
_bless_queue_namespace = None

def _get_bless_queue_namespace():
    global _bless_queue_namespace
    if _bless_queue_namespace is not None:
        return _bless_queue_namespace
    code = None
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(plugin_dir, 'feature', 'bless_queue.py')
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as ex:
            log('[%s] [Sıralı Bless] Yerel modül okunamadı: %s' % (pName, str(ex)))
    if not code:
        try:
            req = urllib.request.Request(
                GITHUB_BLESS_QUEUE_URL,
                headers={'User-Agent': 'phBot-SROManager/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                code = r.read().decode('utf-8')
        except Exception as ex:
            log('[%s] [Sıralı Bless] Modül indirilemedi: %s' % (pName, str(ex)))
            return None
    import ctypes
    namespace = {
        'gui': gui, 'QtBind': QtBind, 'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'get_config_dir': get_config_dir, 'get_character_data': get_character_data, 'get_party': get_party,
        'get_position': get_position, 'get_inventory': get_inventory, 'get_skills': get_skills,
        'inject_joymax': inject_joymax, 'struct': struct, 'os': os, 'json': json, 're': __import__('re'),
        'math': __import__('math'), 'threading': threading, 'time': time, 'phBotChat': phBotChat, 'ctypes': ctypes,
        'cbEnable': _bq_cbEnable, 'lstParty': _bq_lstParty, 'lstQueue': _bq_lstQueue,
        'tbBlessId': _bq_tbBlessId, 'tbSpam': _bq_tbSpam, 'tbSkip': _bq_tbSkip, 'tbDur': _bq_tbDur,
        'cbSay': _bq_cbSay, 'cmbClericWeapon': _bq_cmbClericWeapon, 'cmbMainWeapon': _bq_cmbMainWeapon,
        'btnRefresh': _bq_btnRefresh, 'btnAddAll': _bq_btnAddAll, 'btnAddSel': _bq_btnAddSel,
        'btnSendQueue': _bq_btnSendQueue, 'btnRemSel': _bq_btnRemSel, 'btnUp': _bq_btnUp, 'btnDown': _bq_btnDown,
        'btnClearQ': _bq_btnClearQ, 'btnSaveBless': _bq_btnSaveBless, 'btnScanBless': _bq_btnScanBless,
        'btnStopBless': _bq_btnStopBless, 'btnSaveTimers': _bq_btnSaveTimers,
        'btnWRefresh': _bq_btnWRefresh, 'btnWSave': _bq_btnWSave, 'btnHelpEN': _bq_btnHelpEN,
    }
    try:
        exec(code, namespace)
        bcfg = namespace.get('BCFG') or {}
        QtBind.setText(gui, _bq_tbBlessId, hex(int(bcfg.get('bless_id', 11766) or 11766)))
        QtBind.setChecked(gui, _bq_cbSay, bool(bcfg.get('say_in_party', True)))
        QtBind.setText(gui, _bq_tbSpam, str(float(bcfg.get('spam_interval_s', 2.5) or 2.5)))
        QtBind.setText(gui, _bq_tbSkip, str(float(bcfg.get('skip_turn_s', 15) or 15)))
        QtBind.setText(gui, _bq_tbDur, str(int(bcfg.get('duration_s', 45) or 45)))
    except Exception as ex:
        log('[%s] [Sıralı Bless] Modül yüklenemedi: %s' % (pName, str(ex)))
        return None
    _bless_queue_namespace = namespace
    return _bless_queue_namespace

def _bq_ns_call(name, *args):
    try:
        ns = _get_bless_queue_namespace()
        if ns is None or name not in ns:
            return None
        f = ns[name]
        return f(*args) if args else f()
    except Exception:
        return None

def bq_cb_enable_changed():
    _bq_ns_call('cb_enable_changed', QtBind.isChecked(gui, _bq_cbEnable))

def bq_cb_say_changed():
    _bq_ns_call('cb_say_changed', QtBind.isChecked(gui, _bq_cbSay))

def bq_btn_refresh():
    _bq_ns_call('btn_refresh')
def bq_btn_add_all():
    _bq_ns_call('btn_add_all')
def bq_btn_add_selected():
    _bq_ns_call('btn_add_selected')
def bq_btn_send_queue():
    _bq_ns_call('btn_send_queue')
def bq_btn_remove_selected():
    _bq_ns_call('btn_remove_selected')
def bq_btn_queue_up():
    _bq_ns_call('btn_queue_up')
def bq_btn_queue_down():
    _bq_ns_call('btn_queue_down')
def bq_btn_clear_q():
    _bq_ns_call('btn_clear_q')
def bq_btn_save_bless():
    _bq_ns_call('btn_save_bless')
def bq_btn_scan_bless():
    _bq_ns_call('btn_scan_bless')
def bq_btn_stop_bless():
    _bq_ns_call('btn_stop_bless')
def bq_btn_save_timers():
    _bq_ns_call('btn_save_timers')
def bq_btn_wrefresh():
    _bq_ns_call('btn_wrefresh')
def bq_btn_wsave():
    _bq_ns_call('btn_wsave')
# Script & Chat Command Maker (Tab 11) - SROManager Command Maker
_scm_x = _tab_bar_x + 15
_scm_y = _content_y + 10
_add_tab11(QtBind.createLabel(gui, 'Script - Chat Command Maker', _scm_x, _scm_y), _scm_x, _scm_y)
_add_tab11(QtBind.createLabel(gui, 'Chat:', _scm_x, _scm_y + 26), _scm_x, _scm_y + 26)
_scm_tbChat = QtBind.createLineEdit(gui, "", _scm_x + 45, _scm_y + 22, 130, 20)
_add_tab11(_scm_tbChat, _scm_x + 45, _scm_y + 22)
_add_tab11(QtBind.createLabel(gui, 'Script:', _scm_x + 195, _scm_y + 26), _scm_x + 195, _scm_y + 26)
_scm_tbScript = QtBind.createLineEdit(gui, "", _scm_x + 245, _scm_y + 22, 240, 20)
_add_tab11(_scm_tbScript, _scm_x + 245, _scm_y + 22)
_add_tab11(QtBind.createLabel(gui, 'Opcode:', _scm_x, _scm_y + 52), _scm_x, _scm_y + 52)
_scm_tbOpcode = QtBind.createLineEdit(gui, "0x", _scm_x + 55, _scm_y + 48, 130, 20)
_add_tab11(_scm_tbOpcode, _scm_x + 55, _scm_y + 48)
_add_tab11(QtBind.createLabel(gui, 'Data:', _scm_x + 195, _scm_y + 52), _scm_x + 195, _scm_y + 52)
_scm_tbData = QtBind.createLineEdit(gui, "", _scm_x + 245, _scm_y + 48, 240, 20)
_add_tab11(_scm_tbData, _scm_x + 245, _scm_y + 48)
_scm_btnSave = QtBind.createButton(gui, 'scm_ui_save', 'Kaydet', _scm_x + 500, _scm_y + 22)
_add_tab11(_scm_btnSave, _scm_x + 500, _scm_y + 22)
_scm_btnLoad = QtBind.createButton(gui, 'scm_ui_load', 'Yükle', _scm_x + 560, _scm_y + 22)
_add_tab11(_scm_btnLoad, _scm_x + 560, _scm_y + 22)
_scm_btnRemove = QtBind.createButton(gui, 'scm_ui_remove', 'Sil', _scm_x + 620, _scm_y + 22)
_add_tab11(_scm_btnRemove, _scm_x + 620, _scm_y + 22)
_scm_btnEdit = QtBind.createButton(gui, 'scm_ui_edit', 'Düzenle', _scm_x + 500, _scm_y + 48)
_add_tab11(_scm_btnEdit, _scm_x + 500, _scm_y + 48)
_add_tab11(QtBind.createLabel(gui, 'Eşlemeler:', _scm_x, _scm_y + 78), _scm_x, _scm_y + 78)
_scm_lstMap = QtBind.createList(gui, _scm_x, _scm_y + 93, 670, 72)
_add_tab11(_scm_lstMap, _scm_x, _scm_y + 93)
_scm_cbLog = QtBind.createCheckBox(gui, 'scm_ui_log', 'Tüm C2S paketlerini göster', _scm_x, _scm_y + 172)
_add_tab11(_scm_cbLog, _scm_x, _scm_y + 172)
_add_tab11(QtBind.createLabel(gui, 'Gizle opcode:', _scm_x + 205, _scm_y + 172), _scm_x + 205, _scm_y + 172)
_scm_tbHide = QtBind.createLineEdit(gui, "0x", _scm_x + 295, _scm_y + 168, 70, 20)
_add_tab11(_scm_tbHide, _scm_x + 295, _scm_y + 168)
_scm_btnHideAdd = QtBind.createButton(gui, 'scm_ui_hide_add', '+', _scm_x + 370, _scm_y + 167)
_add_tab11(_scm_btnHideAdd, _scm_x + 370, _scm_y + 167)
_scm_btnHideDel = QtBind.createButton(gui, 'scm_ui_hide_del', '-', _scm_x + 370, _scm_y + 192)
_add_tab11(_scm_btnHideDel, _scm_x + 370, _scm_y + 192)
_scm_lstHide = QtBind.createList(gui, _scm_x + 490, _scm_y + 168, 190, 52)
_add_tab11(_scm_lstHide, _scm_x + 490, _scm_y + 168)
_add_tab11(QtBind.createLabel(gui, 'Lider:', _scm_x, _scm_y + 228), _scm_x, _scm_y + 228)
_scm_tbLeader = QtBind.createLineEdit(gui, "", _scm_x + 55, _scm_y + 224, 130, 20)
_add_tab11(_scm_tbLeader, _scm_x + 55, _scm_y + 224)
_scm_lblStatus = QtBind.createLabel(gui, 'Hazır', _scm_x, _scm_y + 248)
_add_tab11(_scm_lblStatus, _scm_x, _scm_y + 248)
_scm_btnHelp = QtBind.createButton(gui, 'scm_btn_help_clicked', 'Yardım', _scm_x + 680, _scm_y)
_add_tab11(_scm_btnHelp, _scm_x + 680, _scm_y)

_script_command_maker_namespace = None

def _get_script_command_maker_namespace():
    global _script_command_maker_namespace
    if _script_command_maker_namespace is not None:
        return _script_command_maker_namespace
    code = None
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    for base in [plugin_dir, os.path.join(plugin_dir, 'sro-plugins-repo')]:
        local_path = os.path.join(base, 'feature', 'script_command_maker.py')
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                break
            except Exception as ex:
                log('[%s] [Script-Command] Yerel modül okunamadı: %s' % (pName, str(ex)))
    if not code:
        try:
            req = urllib.request.Request(
                GITHUB_SCRIPT_COMMAND_MAKER_URL,
                headers={'User-Agent': 'phBot-SROManager/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                code = r.read().decode('utf-8')
        except Exception as ex:
            log('[%s] [Script-Command] Modül indirilemedi: %s' % (pName, str(ex)))
            return None
    namespace = {
        'gui': gui, 'QtBind': QtBind, 'log': log, 'pName': pName, '_is_license_valid': _is_license_valid,
        'get_config_dir': get_config_dir, 'get_character_data': get_character_data,
        'inject_joymax': inject_joymax, 'os': os, 'json': json, 're': __import__('re'), 'time': time,
        'tbChat': _scm_tbChat, 'tbScript': _scm_tbScript, 'tbOpcode': _scm_tbOpcode, 'tbData': _scm_tbData,
        'tbLeader': _scm_tbLeader, 'tbHide': _scm_tbHide, 'lstMap': _scm_lstMap, 'lstHide': _scm_lstHide,
        'btnSave': _scm_btnSave, 'btnLoad': _scm_btnLoad, 'btnRemove': _scm_btnRemove, 'btnEdit': _scm_btnEdit,
        'btnHideAdd': _scm_btnHideAdd, 'btnHideDel': _scm_btnHideDel, 'cbLog': _scm_cbLog, 'lblStatus': _scm_lblStatus,
    }
    try:
        exec(code, namespace)
        if '_load_cfg' in namespace:
            namespace['_load_cfg']()
        namespace['_refresh_lists']()
        QtBind.setChecked(gui, _scm_cbLog, namespace.get('_cfg', {}).get('log_all_c2s', False))
        QtBind.setText(gui, _scm_tbLeader, namespace.get('_cfg', {}).get('leader', ''))
    except Exception as ex:
        log('[%s] [Script-Command] Modül yüklenemedi: %s' % (pName, str(ex)))
        return None
    _script_command_maker_namespace = namespace
    return _script_command_maker_namespace

def _scm_ns_call(name, *args):
    try:
        ns = _get_script_command_maker_namespace()
        if ns is None or name not in ns:
            return None
        f = ns[name]
        return f(*args) if args else f()
    except Exception:
        return None

def scm_btn_help_clicked():
    try:
        text = (
            "Script - Chat Command Maker (SROManager)\r\n"
            "============================================\r\n\r\n"
            "Bu modül Chat komutları ile Silkroad paketlerini eşleştirir.\r\n"
            "Oyunda bir şey yaptığınızda giden paketleri yakalayıp, "
            "belirlediğiniz Chat veya Script komutlarıyla yeniden çalıştırabilirsiniz.\r\n\r\n"
            "Alanlar:\r\n"
            "- Chat   : Oyunda parti sohbetinde yazacağınız komut (örn: bless)\r\n"
            "- Script : phBot script komutu (örn: sromanager bless)\r\n"
            "- Opcode : Paket opcode (örn: 0xB0BD)\r\n"
            "- Data   : Paket hex verisi (örn: 01 02 03)\r\n\r\n"
            "KAYDET butonu:\r\n"
            "Chat + Opcode (ve isteğe Data) girip Kaydet'e basın. "
            "Bu eşleme JSON dosyasına kaydedilir:\r\n"
            "  Config/SROManager/script_command_Server_Karakter.json\r\n"
            "Lider alanına parti liderinin adını yazın; sadece o kişi Chat komutlarını tetikleyebilir.\r\n\r\n"
            "SROManager:\r\n"
            "Script komutunda 'sromanager <anahtar>' yazarsanız, phBot script panelinden "
            "ör. sromanager bless çağrıldığında o eşleme çalışır (paket enjekte edilir).\r\n\r\n"
            "Adımlar:\r\n"
            "1) 'Tüm C2S paketlerini göster' işaretleyin\r\n"
            "2) Oyunda yapmak istediğiniz işlemi yapın (log'dan opcode/data kopyalayın)\r\n"
            "3) Chat + Script + Opcode + Data girin, Kaydet\r\n"
            "4) Lider adını yazın (Chat için) veya sromanager kullanın (Script için)"
        )
        ctypes.windll.user32.MessageBoxW(None, str(text), "%s — Script-Command Yardım" % pName, 0x40)
    except Exception as ex:
        try:
            log('[%s] Script-Command yardım penceresi açılamadı: %s' % (pName, str(ex)))
        except Exception:
            pass

def scm_ui_save():
    _scm_ns_call('ui_save')
def scm_ui_load():
    _scm_ns_call('ui_load')
def scm_ui_remove():
    _scm_ns_call('ui_remove')
def scm_ui_edit():
    _scm_ns_call('ui_edit')
def scm_ui_log(checked):
    _scm_ns_call('ui_log', checked)
def scm_ui_hide_add():
    _scm_ns_call('ui_hide_add')
def scm_ui_hide_del():
    _scm_ns_call('ui_hide_del')

def bq_btn_help_en():
    if not _is_license_valid():
        return
    try:
        import ctypes
        text = (
            "Bless Kuyruğu — Nasıl kullanılır (Oyuncu Kılavuzu)\r\n"
            "===============================================\r\n"
            "\r\n"
            "Lider / Sahip:\r\n"
            "- Parti Lideri oyun içi sohbette duyuruları okuyamaz AMA plugin ona otomatik bless atar.\r\n"
            "- 'Sırayı Gönder' tuşuna basan oyuncu otomatik olarak Lider olur.\r\n"
            "- Sadece TEK kişi basmalıdır.\r\n"
            "\r\n"
            "Kurulum (Karakter başına bir kez kaydedilir):\r\n"
            "1) YENİLE tuşuna basın\r\n"
            "   - Parti listesini ve silah listesini günceller.\r\n"
            "2) Cleric üyelerini sıraya ekleyin\r\n"
            "   - Üyeyi seçin -> 'Ekle →' (ilk boş slota eklenir)\r\n"
            "   - Veya 'Tümünü Ekle' tuşuna basın\r\n"
            "3) Sırayı düzenleyin\r\n"
            "   - Slot #1 önce bless atar, sonra #2, sonra #3...\r\n"
            "   - Sırayı değiştirmek için YUKARI / AŞAĞI kullanın\r\n"
            "4) TARA tuşuna basın\r\n"
            "   - Bless becerinizi otomatik bulur\r\n"
            "5) Silahları seçin (ÖNEMLİ)\r\n"
            "   - Cleric silahı = Bless atmak için silahı otomatik Cleric silahına geçirir\r\n"
            "   - Ana silah     = Bless attıktan sonra Ana Silaha geri geçer\r\n"
            "   - Sonra KAYDET tuşuna basın\r\n"
            "\r\n"
            "Zamanlayıcılar:\r\n"
            "- SÜRE  = Bless ne kadar süre aktif kalır\r\n"
            "- SPAM  = Parti sohbetinde hatırlatmaların ne sıklıkta tekrarlanacağı\r\n"
            "- SKIP  = Bir oyuncuyu atlamadan önce maksimum bekleme süresi (AFK/yok)\r\n"
            "\r\n"
            "Başlatma:\r\n"
            "- Lider 'Sırayı Gönder' tuşuna basar\r\n"
            "- Plugin oyuncuları sıraya göre çağırır\r\n"
            "- İsminiz çağrıldığında: hazır olun, plugin sizin için atacak\r\n"
            "\r\n"
            "Butonlar (kısa anlam):\r\n"
            "- Yenile    : parti + silahları güncelle\r\n"
            "- Ekle →   : seçili üyeyi ilk boş slota ekle\r\n"
            "- Tümünü Ekle : tüm parti üyelerini ekle\r\n"
            "- Yukarı/Aşağı : sıra düzenini değiştir\r\n"
            "- Sil      : seçili slot/üyeyi kaldır\r\n"
            "- Tümünü Sil  : sıra listesini temizle\r\n"
            "- Kaydet   : ayarları ve zamanlayıcıları kaydet\r\n"
            "- Durdur   : duyuruları/zamanlayıcıları durdur\r\n"
        )
        ctypes.windll.user32.MessageBoxW(None, str(text), "%s — Yardım" % pName, 0x40)
    except Exception as ex:
        try:
            log('[%s] Yardım penceresi açılamadı: %s' % (pName, str(ex)))
        except Exception:
            pass

# Hakkımda tab1'e alındı; diğer tablar bir kaydırıldı (tab1=Hakkımda, tab2=Banka, ... tab8=Envanter)
_swap = _tab8_widgets
_tab8_widgets = _tab7_widgets
_tab7_widgets = _tab6_widgets
_tab6_widgets = _tab5_widgets
_tab5_widgets = _tab4_widgets
_tab4_widgets = _tab3_widgets
_tab3_widgets = _tab2_widgets
_tab2_widgets = _tab1_widgets
_tab1_widgets = _swap
_new_pb = {
    1: _protected_buttons.get(8, []),
    2: _protected_buttons.get(1, []),
    3: _protected_buttons.get(2, []),
    4: _protected_buttons.get(3, []),
    5: _protected_buttons.get(4, []),
    6: _protected_buttons.get(5, []),
    7: _protected_buttons.get(6, []),
    8: _protected_buttons.get(7, []),
}
_protected_buttons.clear()
_protected_buttons.update(_new_pb)
_protected_buttons[9] = [_ts_cbxEnabled, _ts_cbxDefensive, _ts_tbxLeaders, _ts_lvwLeaders, _ts_btnAddLeader, _ts_btnRemLeader]
_protected_buttons[10] = [
    _bq_cbEnable, _bq_lstParty, _bq_lstQueue, _bq_tbBlessId, _bq_tbSpam, _bq_tbSkip, _bq_tbDur,
    _bq_cbSay, _bq_cmbClericWeapon, _bq_cmbMainWeapon, _bq_btnRefresh, _bq_btnAddAll, _bq_btnAddSel,
    _bq_btnSendQueue, _bq_btnRemSel, _bq_btnUp, _bq_btnDown, _bq_btnClearQ, _bq_btnSaveBless,
    _bq_btnScanBless, _bq_btnStopBless, _bq_btnSaveTimers, _bq_btnWRefresh, _bq_btnWSave, _bq_btnHelpEN
]
_protected_buttons[11] = [
    _scm_tbChat, _scm_tbScript, _scm_tbOpcode, _scm_tbData, _scm_tbLeader, _scm_tbHide,
    _scm_lstMap, _scm_lstHide, _scm_btnSave, _scm_btnLoad, _scm_btnRemove, _scm_btnEdit,
    _scm_btnHideAdd, _scm_btnHideDel, _scm_cbLog
]

_tab_move(_tab2_widgets, True)
_tab_move(_tab3_widgets, True)
_tab_move(_tab4_widgets, True)
_tab_move(_tab5_widgets, True)
_tab_move(_tab6_widgets, True)
_tab_move(_tab7_widgets, True)
_tab_move(_tab8_widgets, True)
_tab_move(_tab9_widgets, True)
_tab_move(_tab10_widgets, True)
_tab_move(_tab11_widgets, True)

log('[%s] v%s yüklendi.' % (pName, pVersion))

# Sunucu bilgilerini yükle ve IP'yi al
_init_server_credentials()

threading.Thread(target=_check_update_thread, name=pName + '_update_auto', daemon=True).start()
threading.Thread(target=_check_script_updates_thread, name=pName + '_script_update', daemon=True).start()

# Auto Dungeon config klasörünü oluştur (getPath uzak modülde)
_auto_dungeon_config_path = get_config_dir() + pName + "\\"
if not os.path.exists(_auto_dungeon_config_path):
    os.makedirs(_auto_dungeon_config_path)
    log('[%s] %s klasörü oluşturuldu' % (pName, pName))

# ______________________________ Events ______________________________ #

def event_loop():
    """Script Komutları: StartBot/CloseBot zamanlama kontrolü (uzaktan modül)"""
    ns = _get_script_commands_namespace()
    if ns and '_script_cmds_event_tick' in ns:
        ns['_script_cmds_event_tick']()
    scm_ns = _get_script_command_maker_namespace()
    if scm_ns and 'event_loop' in scm_ns:
        scm_ns['event_loop']()

def handle_silkroad(opcode, data):
    """Script Komutları: paket kaydı; Script-Command: C2S log"""
    if data is None:
        return True
    scm_ns = _get_script_command_maker_namespace()
    if scm_ns and 'handle_silkroad' in scm_ns:
        scm_ns['handle_silkroad'](opcode, data)
    ns = _get_script_commands_namespace()
    if ns and '_script_cmds_packet_hook' in ns:
        return ns['_script_cmds_packet_hook'](opcode, data)
    return True

def joined_game():
    loadConfigs()
    inv_cnt_loadConfigs()
    _bq_ns_call('joined_game')
    ns = _get_target_support_namespace()
    if ns and 'ts_loadConfigs' in ns:
        ns['ts_loadConfigs']()
    
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
    _bq_ns_call('handle_chat', t, player, msg)
    r = _scm_ns_call('handle_chat', t, player, msg)
    if r is False:
        return False
    ns = _get_target_support_namespace()
    if ns and 'ts_handle_chat' in ns:
        ns['ts_handle_chat'](t, player, msg)

def handle_joymax(opcode, data):
    # Sıralı Bless: 0xB0BD bless cast
    if opcode == 0xB0BD:
        _bq_ns_call('handle_joymax', opcode, data)
    # TargetSupport: 0xB070 skill action
    elif opcode == 0xB070:
        ns = _get_target_support_namespace()
        if ns and 'ts_handle_joymax' in ns:
            ns['ts_handle_joymax'](opcode, data)
    # SERVER_DIMENSIONAL_INVITATION_REQUEST
    elif opcode == 0x751A:
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
                threading.Timer(1.0, _call_remote_EnterToDimensional, [itemUsedByPlugin['name']]).start()
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
_char = get_character_data()
if _char and _char.get('name'):
    inv_cnt_loadConfigs()
    log('[%s] [Envanter Sayacı] Config yüklendi (plugin init)' % pName)
    ns = _get_target_support_namespace()
    if ns and 'ts_loadConfigs' in ns:
        ns['ts_loadConfigs']()

