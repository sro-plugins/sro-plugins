# -*- coding: utf-8 -*-
from phBot import *
import phBot
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

pName = 'Santa-So-Ok-DaRKWoLVeS'
PLUGIN_FILENAME = 'Santa-So-Ok-DaRKWoLVeS.py'
pVersion = '1.4.0'

MOVE_DELAY = 0.25

# Auto Dungeon constants
DIMENSIONAL_COOLDOWN_DELAY = 7200  # saniye (2 saat)
WAIT_DROPS_DELAY_MAX = 10  # saniye
COUNT_MOBS_DELAY = 1.0  # saniye

# License System Configuration
LICENSE_SERVER_URL = 'http://76.13.141.75:8000' # Change this to your server IP
LICENSE_KEY = '' # Saved in config

GITHUB_REPO = 'sro-plugins/sro-plugins'
GITHUB_API_LATEST = 'https://api.github.com/repos/%s/releases/latest' % GITHUB_REPO
GITHUB_RELEASES_URL = 'https://github.com/%s/releases' % GITHUB_REPO
GITHUB_RAW_MAIN = 'https://raw.githubusercontent.com/%s/main/%s' % (GITHUB_REPO, PLUGIN_FILENAME)

def _get_my_ip():
    try:
        req = urllib.request.Request('https://api.ipify.org', headers={'User-Agent': 'phBot-Santa-So-Ok/1.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode('utf8')
    except:
        return '127.0.0.1'

def _api_get_file(enum_type, filename):
    try:
        my_ip = _get_my_ip()
        url = "%s/api/download?publicId=%s&ip=%s&type=%s&filename=%s" % (
            LICENSE_SERVER_URL, LICENSE_KEY, my_ip, enum_type, filename
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-Santa-So-Ok/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception as ex:
        log('[%s] API Hatası: %s' % (pName, str(ex)))
        return None

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
_caravan_profile_keys = []
_caravan_running = False
_caravan_script_path = ""
_caravan_thread = None
_caravan_stop_event = threading.Event()
_caravan_lock = threading.Lock()

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
        
        log('[%s] [Garden-Auto] API\'den script indiriliyor... (Tür: %s)' % (pName, script_type))
        
        script_content = _api_get_file('SC', script_filename)
        
        if not script_content:
            log('[%s] [Garden-Auto] Script API\'den alınamadı!' % pName)
            return False

        
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
        script_content = _api_get_file('CARAVAN', filename)
        if not script_content or len(script_content) < 10:
            return False
        with open(script_path, 'wb') as f:
            f.write(script_content)

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
    _caravan_fill_profile_combo()

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


def _caravan_get_current_profile_key():
    """phBot'ta şu an seçili olan profil anahtarını döndürür (örn. Sirion_VisKi.karavan). Config path'ten türetilir."""
    path = get_config_path()
    if not path:
        return None
    base = os.path.basename(path)
    if base.endswith('.json'):
        return base[:-5]  # .json kesilir
    return None


def _caravan_list_profile_keys():
    """Bu karakter için Config klasöründeki tüm profil dosyalarını listeler. (görünen_ad, profil_anahtarı) listesi."""
    fn = _caravan_db3_filename()
    if not fn:
        return []
    config_dir = _caravan_db3_dir()
    if not config_dir or not os.path.isdir(config_dir):
        return []
    result = []
    try:
        for name in sorted(os.listdir(config_dir)):
            if not name.endswith('.json'):
                continue
            if name == fn + '.json':
                result.append(('Varsayılan', fn))
            elif name.startswith(fn + '.'):
                # Sirion_VisKi.karavan.json -> "karavan"
                suffix = name[len(fn) + 1:-5]
                if suffix:
                    result.append((suffix, fn + '.' + suffix))
    except Exception:
        pass
    return result


def _caravan_fill_profile_combo():
    """Karavan profili combobox'ını Config'teki profillerle doldurur; karavan varsa onu seçer."""
    global _caravan_profile_keys
    try:
        QtBind.clear(gui, comboKervanProfile)
        _caravan_profile_keys = []
        items = _caravan_list_profile_keys()
        default_idx = 0
        for i, (display, key) in enumerate(items):
            QtBind.append(gui, comboKervanProfile, display)
            _caravan_profile_keys.append(key)
            if 'karavan' in key.lower():
                default_idx = i
        if _caravan_profile_keys and hasattr(QtBind, 'setCurrentIndex'):
            try:
                QtBind.setCurrentIndex(gui, comboKervanProfile, min(default_idx, len(_caravan_profile_keys) - 1))
            except Exception:
                pass
    except Exception:
        _caravan_profile_keys = []

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
    current_key = _caravan_get_current_profile_key()
    if not current_key:
        log('[%s] [Oto-Kervan] Profil bilgisi alınamadı. Botu tekrardan açıp Oyuna giriş yapıp tekrar deneyin.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Profil alınamadı')
        return
    if 'karavan' not in current_key.lower():
        log('[%s] [Oto-Kervan] Karavan profili seçili değil. Otomatik yapılandırma profil listesinden karavan profilini seçin, sonra Başlat\'a basın.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Önce Karavan profilini seçin')
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
    QtBind.setText(gui, tbxLicenseKey, "")

def btnSaveLicense_clicked():
    global LICENSE_KEY
    key = QtBind.text(gui, tbxLicenseKey).strip()
    if key:
        LICENSE_KEY = key
        saveConfigs()
        log('[%s] Lisans anahtarı kaydedildi. Sistem doğrulanıyor...' % pName)
        threading.Thread(target=_validate_license_loop, daemon=True).start()
    else:
        log('[%s] Geçersiz lisans anahtarı!' % pName)

def _validate_license_loop():
    while True:
        try:
            my_ip = _get_my_ip()
            url = "%s/api/validate?publicId=%s&ip=%s" % (LICENSE_SERVER_URL, LICENSE_KEY, my_ip)
            req = urllib.request.Request(url, headers={'User-Agent': 'phBot-Santa-So-Ok/1.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode('utf8'))
            log('[%s] Lisans Doğrulama: %s' % (pName, data.get('message', 'Tamam')))
        except Exception as ex:
            log('[%s] Lisans Hatası: %s' % (pName, str(ex)))
            # Optional: Stop features if 401
        time.sleep(300) # her 5 dakikada bir kontrol


def loadConfigs():
    loadDefaultConfig()
    if isJoined() and os.path.exists(getConfig()):
        data = {}
        with open(getConfig(), "r") as f:
            data = json.load(f)
            if "License Key" in data:
                global LICENSE_KEY
                LICENSE_KEY = data["License Key"]
                QtBind.setText(gui, tbxLicenseKey, LICENSE_KEY)
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
        data['License Key'] = LICENSE_KEY

        with open(getConfig(), "w") as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

gui = QtBind.init(__name__, pName)

TAB_OFFSCREEN = -3000
_tab1_widgets = []
_tab2_widgets = []
_tab3_widgets = []
_tab4_widgets = []
_tab5_widgets = []
_tab6_widgets = []
_tab7_widgets = []
_current_tab = 1

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
    _tab_move(_tab1_widgets, False)
    _current_tab = 1
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _show_tab2():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab2_widgets, False)
    _current_tab = 2
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _show_tab3():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab3_widgets, False)
    _current_tab = 3
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _show_tab4():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab4_widgets, False)
    _current_tab = 4
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _show_tab5():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab5_widgets, False)
    _current_tab = 5
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _show_tab7():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, True)
    _tab_move(_tab7_widgets, False)
    _current_tab = 7
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w + _tab5_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _add_tab7(w, x, y):
    _tab7_widgets.append((w, x, y))

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

_tab_bar_y = 8
_tab_bar_x = 10
_tab_bar_w = 700
_tab_bar_h = 26
_tab1_btn_w = 114
_tab2_btn_w = 83
_tab3_btn_w = 95
_tab4_btn_w = 80
_tab5_btn_w = 75
_tab6_btn_w = 63
_tab_spacing = 0

QtBind.createList(gui, _tab_bar_x, _tab_bar_y, _tab_bar_w, _tab_bar_h)
QtBind.createButton(gui, '_show_tab1', 'Banka/Çanta Birleştir', _tab_bar_x + 3, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab2', 'Auto Dungeon', _tab_bar_x + 3 + _tab1_btn_w, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab3', 'Garden Dungeon', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab4', 'Auto Hwt', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab5', 'Oto Kervan', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab7', 'Lisans', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w + _tab5_btn_w, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab6', 'Hakkımda', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w + _tab5_btn_w + _tab6_btn_w, _tab_bar_y + 2)

_tab_indicator = QtBind.createList(gui, _tab_bar_x + 3, _tab_bar_y + _tab_bar_h - 3, _tab1_btn_w - 1, 4)

_content_y = _tab_bar_y + _tab_bar_h - 1
_content_container_h = 270
QtBind.createList(gui, _tab_bar_x, _content_y, _tab_bar_w, _content_container_h)

_jewel_y = _content_y + 12
_jewel_w = 280
_jewel_h = 62
_jewel_x = _tab_bar_x + (_tab_bar_w - _jewel_w) // 2

_jewel_container = QtBind.createList(gui, _jewel_x, _jewel_y, _jewel_w, _jewel_h)
_add_tab1(_jewel_container, _jewel_x, _jewel_y)
_add_tab1(QtBind.createLabel(gui, 'So-Ok Event Kullanma', _jewel_x + 70, _jewel_y + 8), _jewel_x + 70, _jewel_y + 8)
_add_tab1(QtBind.createButton(gui, 'jewel_start', 'Başla', _jewel_x + 60, _jewel_y + 32), _jewel_x + 60, _jewel_y + 32)
_add_tab1(QtBind.createButton(gui, 'jewel_stop', 'Durdur', _jewel_x + 140, _jewel_y + 32), _jewel_x + 140, _jewel_y + 32)

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
_add_tab1(QtBind.createLabel(gui, 'Çanta İşlemleri', _inv_container_x + 12, _row2_y + 8), _inv_container_x + 12, _row2_y + 8)

_iy1 = _row2_y + 32
_frame2 = QtBind.createList(gui, _inv_container_x + 12, _iy1, _container_w - 24, 50)
_add_tab1(_frame2, _inv_container_x + 12, _iy1)
_add_tab1(QtBind.createLabel(gui, 'Çantayı Birleştir', _inv_container_x + 20, _iy1 + 5), _inv_container_x + 20, _iy1 + 5)
_add_tab1(QtBind.createButton(gui, 'merge_start', 'Başla', _inv_container_x + 20, _iy1 + 25), _inv_container_x + 20, _iy1 + 25)
_add_tab1(QtBind.createButton(gui, 'merge_stop', 'Durdur', _inv_container_x + 100, _iy1 + 25), _inv_container_x + 100, _iy1 + 25)

_iy2 = _iy1 + 58
_frame3 = QtBind.createList(gui, _inv_container_x + 12, _iy2, _container_w - 24, 50)
_add_tab1(_frame3, _inv_container_x + 12, _iy2)
_add_tab1(QtBind.createLabel(gui, 'Çantayı Sırala', _inv_container_x + 20, _iy2 + 5), _inv_container_x + 20, _iy2 + 5)
_add_tab1(QtBind.createButton(gui, 'sort_start', 'Başla', _inv_container_x + 20, _iy2 + 25), _inv_container_x + 20, _iy2 + 25)
_add_tab1(QtBind.createButton(gui, 'sort_stop', 'Durdur', _inv_container_x + 100, _iy2 + 25), _inv_container_x + 100, _iy2 + 25)

_bank_container = QtBind.createList(gui, _bank_container_x, _row2_y, _container_w, _container_h)
_add_tab1(_bank_container, _bank_container_x, _row2_y)
_add_tab1(QtBind.createLabel(gui, 'Banka İşlemleri', _bank_container_x + 12, _row2_y + 8), _bank_container_x + 12, _row2_y + 8)
_add_tab1(QtBind.createLabel(gui, 'Banka NPC yakındaysa otomatik açılır.', _bank_container_x + 12, _row2_y + 24), _bank_container_x + 12, _row2_y + 24)

_by1 = _row2_y + 46
_store_merge_frame = QtBind.createList(gui, _bank_container_x + 12, _by1, _container_w - 24, 50)
_add_tab1(_store_merge_frame, _bank_container_x + 12, _by1)
_add_tab1(QtBind.createLabel(gui, 'Bankayı Birleştir', _bank_container_x + 20, _by1 + 5), _bank_container_x + 20, _by1 + 5)
_add_tab1(QtBind.createButton(gui, 'bank_merge_start', 'Başla', _bank_container_x + 20, _by1 + 25), _bank_container_x + 20, _by1 + 25)
_add_tab1(QtBind.createButton(gui, 'bank_merge_stop', 'Durdur', _bank_container_x + 100, _by1 + 25), _bank_container_x + 100, _by1 + 25)

_by2 = _by1 + 58
_store_sort_frame = QtBind.createList(gui, _bank_container_x + 12, _by2, _container_w - 24, 50)
_add_tab1(_store_sort_frame, _bank_container_x + 12, _by2)
_add_tab1(QtBind.createLabel(gui, 'Bankayı Sırala', _bank_container_x + 20, _by2 + 5), _bank_container_x + 20, _by2 + 5)
_add_tab1(QtBind.createButton(gui, 'bank_sort_start', 'Başla', _bank_container_x + 20, _by2 + 25), _bank_container_x + 20, _by2 + 25)
_add_tab1(QtBind.createButton(gui, 'bank_sort_stop', 'Durdur', _bank_container_x + 100, _by2 + 25), _bank_container_x + 100, _by2 + 25)

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
_kervan_container_w = 450
_kervan_container_h = 260
_kervan_container_x = _tab_bar_x + (_tab_bar_w - _kervan_container_w) // 2
_kervan_container_y = _content_y + 15

_kervan_container = QtBind.createList(gui, _kervan_container_x, _kervan_container_y, _kervan_container_w, _kervan_container_h)
_add_tab5(_kervan_container, _kervan_container_x, _kervan_container_y)

_kervan_title_x = _kervan_container_x + 20
_kervan_title_y = _kervan_container_y + 10

_add_tab5(QtBind.createLabel(gui, '═══════════ Oto Kervan ═══════════', _kervan_title_x, _kervan_title_y), _kervan_title_x, _kervan_title_y)
_add_tab5(QtBind.createLabel(gui, 'GitHub\'daki karavan scriptlerinden birini seçin; Başla ile yürütün.', _kervan_title_x, _kervan_title_y + 18), _kervan_title_x, _kervan_title_y + 18)

# Karavan profili listesi (Başlat için ana pencerede karavan profilini seçin)
_kervan_profile_y = _kervan_title_y + 40
_add_tab5(QtBind.createLabel(gui, 'Karavan profili:', _kervan_title_x, _kervan_profile_y), _kervan_title_x, _kervan_profile_y)
comboKervanProfile = QtBind.createCombobox(gui, _kervan_title_x + 95, _kervan_profile_y - 2, 200, 22)
_add_tab5(comboKervanProfile, _kervan_title_x + 95, _kervan_profile_y - 2)

# Script listesi
_kervan_list_y = _kervan_title_y + 68
_add_tab5(QtBind.createLabel(gui, 'Script listesi:', _kervan_title_x, _kervan_list_y), _kervan_title_x, _kervan_list_y)
lstKervanScripts = QtBind.createList(gui, _kervan_title_x, _kervan_list_y + 18, 300, 120)
_add_tab5(lstKervanScripts, _kervan_title_x, _kervan_list_y + 18)
QtBind.append(gui, lstKervanScripts, '(Önce "Yenile" ile listeyi yükleyin)')

# Yenile / Başla / Durdur
_kervan_btn_y = _kervan_list_y + 145
_kervan_btn_x = _kervan_title_x
_add_tab5(QtBind.createButton(gui, 'kervan_refresh_list', ' Yenile ', _kervan_btn_x, _kervan_btn_y), _kervan_btn_x, _kervan_btn_y)
_add_tab5(QtBind.createButton(gui, 'kervan_start', ' Başla ', _kervan_btn_x + 75, _kervan_btn_y), _kervan_btn_x + 75, _kervan_btn_y)
_add_tab5(QtBind.createButton(gui, 'kervan_stop', ' Durdur ', _kervan_btn_x + 150, _kervan_btn_y), _kervan_btn_x + 150, _kervan_btn_y)

lblKervanStatus = QtBind.createLabel(gui, 'Durum: Hazır', _kervan_title_x, _kervan_btn_y + 28)
_add_tab5(lblKervanStatus, _kervan_title_x, _kervan_btn_y + 28)

def _caravan_init_load():
    """Init sonrası karavan profilini (yoksa) oluşturur, ardından script listesini arka planda yükler."""
    time.sleep(2)
    try:
        _caravan_ensure_karavan_profile_on_init()
        kervan_refresh_list()
    except Exception:
        pass
threading.Thread(target=_caravan_init_load, name=pName + '_caravan_init', daemon=True).start()

# Tab 6 - Hakkımda
_t3_container_x = _tab_bar_x + 30
_t3_container_y = _content_y + 15
_t3_container_w = _tab_bar_w - 60
_t3_container_h = 245

_t3_container = QtBind.createList(gui, _t3_container_x, _t3_container_y, _t3_container_w, _t3_container_h)
_add_tab6(_t3_container, _t3_container_x, _t3_container_y)

_t3_x = _t3_container_x + 15
_t3_y = _t3_container_y + 15

_add_tab6(QtBind.createLabel(gui, '╔═════════════════════════╗', _t3_x, _t3_y), _t3_x, _t3_y)
_add_tab6(QtBind.createLabel(gui, '║   Author:  V i S K i   DaRK_WoLVeS <3      ║', _t3_x, _t3_y + 16), _t3_x, _t3_y + 16)
_add_tab6(QtBind.createLabel(gui, '╚═════════════════════════╝', _t3_x, _t3_y + 32), _t3_x, _t3_y + 32)

_version_y = _t3_y + 58
_add_tab6(QtBind.createLabel(gui, 'Sürüm: v' + pVersion, _t3_x, _version_y), _t3_x, _version_y)

_btn_y = _version_y + 26
_add_tab6(QtBind.createButton(gui, 'check_update', 'Kontrol', _t3_x, _btn_y), _t3_x, _btn_y)
_add_tab6(QtBind.createButton(gui, 'do_auto_update', 'Güncelle', _t3_x + 70, _btn_y), _t3_x + 70, _btn_y)

_status_y = _btn_y + 30
_update_label_ref = QtBind.createLabel(gui, '', _t3_x, _status_y)
_add_tab6(_update_label_ref, _t3_x, _status_y)

_features_y = _status_y + 35
_add_tab6(QtBind.createLabel(gui, 'Plugin Özellikleri:', _t3_x, _features_y), _t3_x, _features_y)
_add_tab6(QtBind.createLabel(gui, '• So-Ok Event otomatik kullanma', _t3_x, _features_y + 22), _t3_x, _features_y + 22)
_add_tab6(QtBind.createLabel(gui, '• Çanta/Banka birleştir ve sırala', _t3_x, _features_y + 42), _t3_x, _features_y + 42)
_add_tab6(QtBind.createLabel(gui, '• Auto Dungeon sistemi', _t3_x, _features_y + 62), _t3_x, _features_y + 62)
_add_tab6(QtBind.createLabel(gui, '• Garden Dungeon otomatik oynatma', _t3_x, _features_y + 82), _t3_x, _features_y + 82)
_add_tab6(QtBind.createLabel(gui, '• Auto Hwt sistemi', _t3_x, _features_y + 102), _t3_x, _features_y + 102)
_add_tab6(QtBind.createLabel(gui, '• Oto Kervan sistemi', _t3_x, _features_y + 122), _t3_x, _features_y + 122)
_add_tab6(QtBind.createLabel(gui, '• Otomatik güncelleme desteği', _t3_x, _features_y + 142), _t3_x, _features_y + 142)

# Tab 7 - Lisans
_t7_container_x = _tab_bar_x + 100
_t7_container_y = _content_y + 40
_t7_container_w = 500
_t7_container_h = 180

_t7_container = QtBind.createList(gui, _t7_container_x, _t7_container_y, _t7_container_w, _t7_container_h)
_add_tab7(_t7_container, _t7_container_x, _t7_container_y)

_t7_x = _t7_container_x + 20
_t7_y = _t7_container_y + 20

_add_tab7(QtBind.createLabel(gui, '═════════════ Lisans Sistemi ═════════════', _t7_x, _t7_y), _t7_x, _t7_y)
_add_tab7(QtBind.createLabel(gui, 'Botu kullanmak için size verilen Public ID (Lisans Anahtarı)\'nı girin.', _t7_x, _t7_y + 25), _t7_x, _t7_y + 25)

_t7_input_y = _t7_y + 55
_add_tab7(QtBind.createLabel(gui, 'Lisans Anahtarı:', _t7_x, _t7_input_y), _t7_x, _t7_input_y)
tbxLicenseKey = QtBind.createLineEdit(gui, "", _t7_x + 100, _t7_input_y - 2, 350, 22)
_add_tab7(tbxLicenseKey, _t7_x + 100, _t7_input_y - 2)

_t7_btn_y = _t7_input_y + 40
_add_tab7(QtBind.createButton(gui, 'btnSaveLicense_clicked', ' Lisansı Kaydet ve Doğrula ', _t7_x + 150, _t7_btn_y), _t7_x + 150, _t7_btn_y)

_tab_move(_tab2_widgets, True)
_tab_move(_tab3_widgets, True)
_tab_move(_tab4_widgets, True)
_tab_move(_tab5_widgets, True)
_tab_move(_tab6_widgets, True)
_tab_move(_tab7_widgets, True)


log('[%s] v%s yüklendi.' % (pName, pVersion))
threading.Thread(target=_check_update_thread, name=pName + '_update_auto', daemon=True).start()
threading.Thread(target=_check_script_updates_thread, name=pName + '_script_update', daemon=True).start()

# Auto Dungeon klasörünü oluştur
if not os.path.exists(getPath()):
    os.makedirs(getPath())
    log('[%s] %s klasörü oluşturuldu' % (pName, pName))

# ______________________________ Events ______________________________ #

def joined_game():
    loadConfigs()

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
