# -*- coding: utf-8 -*-
from phBot import *
import phBot
import QtBind
import threading
import time
import copy
import json
import os
import urllib.request
import sqlite3

pName = 'Santa-So-Ok-DaRKWoLVeS'
PLUGIN_FILENAME = 'Santa-So-Ok-DaRKWoLVeS.py'
pVersion = '1.3.0'

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
GITHUB_CARAVAN_FOLDER = 'PHBOT Caravan SC'
GITHUB_API_CARAVAN_CONTENTS = 'https://api.github.com/repos/%s/contents/%s' % (GITHUB_REPO, 'PHBOT%20Caravan%20SC')
GITHUB_RAW_CARAVAN_SCRIPT = ('https://raw.githubusercontent.com/%s/main/PHBOT%%20Caravan%%20SC/%%s' % GITHUB_REPO)
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
_caravan_script_list = []  # GitHub'dan gelen .txt dosya adları
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

def _fetch_caravan_script_list():
    """GitHub API ile PHBOT Caravan SC klasöründeki .txt dosyalarının listesini döndürür."""
    try:
        req = urllib.request.Request(
            GITHUB_API_CARAVAN_CONTENTS,
            headers={'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'}
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
        log('[%s] [Oto-Kervan] Script listesi alınamadı: %s' % (pName, str(ex)))
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
        url = GITHUB_RAW_CARAVAN_SCRIPT % (filename,)
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
        log('[%s] [Script-Update] Script güncellemeleri kontrol ediliyor...' % pName)
        
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
    """GitHub'dan karavan script listesini çeker ve listeyi günceller."""
    QtBind.setText(gui, lblKervanStatus, 'Durum: Liste yükleniyor...')
    names = _fetch_caravan_script_list()
    QtBind.clear(gui, lstKervanScripts)
    if not names:
        QtBind.append(gui, lstKervanScripts, '(Liste alınamadı - Yenile\'yi tekrar deneyin)')
        QtBind.setText(gui, lblKervanStatus, 'Durum: Liste alınamadı')
        log('[%s] [Oto-Kervan] Script listesi boş veya hata.' % pName)
        return
    for name in names:
        QtBind.append(gui, lstKervanScripts, name)
    QtBind.setText(gui, lblKervanStatus, 'Durum: %d script listelendi' % len(names))
    log('[%s] [Oto-Kervan] %d karavan scripti listelendi.' % (pName, len(names)))

def _caravan_loop():
    global _caravan_running
    try:
        script_path = _caravan_script_path
        log('[%s] [Oto-Kervan] Karavan başlatılıyor: %s' % (pName, script_path))
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
        x, y, z = pos.get('x', 0), pos.get('y', 0), pos.get('z', 0)
        set_training_position(region, x, y, z)
        set_training_radius(50.0)
        result = set_training_script(script_path)
        if not result:
            log('[%s] [Oto-Kervan] Training script ayarlanamadı!' % pName)
            _caravan_running = False
            return
        time.sleep(0.5)
        start_bot()
        _caravan_running = True
        log('[%s] [Oto-Kervan] Bot başlatıldı' % pName)
        while not _caravan_stop_event.is_set():
            time.sleep(1)
        log('[%s] [Oto-Kervan] Karavan durduruluyor...' % pName)
        stop_bot()
        _caravan_running = False
    except Exception as ex:
        log('[%s] [Oto-Kervan] Hata: %s' % (pName, str(ex)))
        _caravan_running = False

def kervan_start():
    global _caravan_script_path, _caravan_thread
    selected = QtBind.text(gui, lstKervanScripts).strip()
    if not selected or selected.startswith('('):
        log('[%s] [Oto-Kervan] Lütfen listeden bir script seçin.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Önce script seçin')
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
    with _caravan_lock:
        _caravan_stop_event.set()
        if _caravan_thread and _caravan_thread.is_alive():
            _caravan_thread.join(timeout=3)
        _caravan_thread = None
        _caravan_running = False
    stop_bot()
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

gui = QtBind.init(__name__, pName)

TAB_OFFSCREEN = -3000
_tab1_widgets = []
_tab2_widgets = []
_tab3_widgets = []
_tab4_widgets = []
_tab5_widgets = []
_tab6_widgets = []
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

def _show_tab6():
    global _current_tab
    _tab_move(_tab1_widgets, True)
    _tab_move(_tab2_widgets, True)
    _tab_move(_tab3_widgets, True)
    _tab_move(_tab4_widgets, True)
    _tab_move(_tab5_widgets, True)
    _tab_move(_tab6_widgets, False)
    _current_tab = 6
    try:
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w + _tab5_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

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
QtBind.createButton(gui, '_show_tab6', 'Hakkımda', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w + _tab3_btn_w + _tab4_btn_w + _tab5_btn_w, _tab_bar_y + 2)
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

# Script listesi
_kervan_list_y = _kervan_title_y + 42
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
    """Init sonrası GitHub'dan karavan listesini arka planda yükler."""
    time.sleep(2)
    try:
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

_tab_move(_tab2_widgets, True)
_tab_move(_tab3_widgets, True)
_tab_move(_tab4_widgets, True)
_tab_move(_tab5_widgets, True)
_tab_move(_tab6_widgets, True)

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
