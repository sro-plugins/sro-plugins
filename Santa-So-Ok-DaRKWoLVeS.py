# -*- coding: utf-8 -*-
from phBot import *
import QtBind
import threading
import time
import struct
import copy
import json
import os
import urllib.request

pName = 'Santa-So-Ok-DaRKWoLVeS'
PLUGIN_FILENAME = 'Santa-So-Ok-DaRKWoLVeS.py'
pVersion = '1.2.3'

MOVE_DELAY = 0.25

GITHUB_REPO = 'sro-plugins/sro-plugins'
GITHUB_API_LATEST = 'https://api.github.com/repos/%s/releases/latest' % GITHUB_REPO
GITHUB_RELEASES_URL = 'https://github.com/%s/releases' % GITHUB_REPO
GITHUB_RAW_MAIN = 'https://raw.githubusercontent.com/%s/main/%s' % (GITHUB_REPO, PLUGIN_FILENAME)
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

gui = QtBind.init(__name__, pName)

TAB_OFFSCREEN = -3000
_tab1_widgets = []
_tab2_widgets = []
_tab3_widgets = []
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
    _tab_move(_tab3_widgets, False)
    _current_tab = 3
    try:
        _ind_w = _tab3_btn_w - 3
        QtBind.move(gui, _tab_indicator, _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w, _tab_bar_y + _tab_bar_h - 3)
    except Exception:
        pass

def _add_tab1(w, x, y):
    _tab1_widgets.append((w, x, y))

def _add_tab2(w, x, y):
    _tab2_widgets.append((w, x, y))

def _add_tab3(w, x, y):
    _tab3_widgets.append((w, x, y))

_tab_bar_y = 8
_tab_bar_x = 10
_tab_bar_w = 700
_tab_bar_h = 26
_tab1_btn_w = 114
_tab2_btn_w = 83
_tab3_btn_w = 63
_tab_spacing = 0

QtBind.createList(gui, _tab_bar_x, _tab_bar_y, _tab_bar_w, _tab_bar_h)
QtBind.createButton(gui, '_show_tab1', 'Banka/Çanta Birleştir', _tab_bar_x + 3, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab2', 'Auto Dungeon', _tab_bar_x + 3 + _tab1_btn_w, _tab_bar_y + 2)
QtBind.createButton(gui, '_show_tab3', 'Hakkımda', _tab_bar_x + 3 + _tab1_btn_w + _tab2_btn_w, _tab_bar_y + 2)
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

_t2_y = _content_y + 40
_t2_x = _tab_bar_x + 30
_add_tab2(QtBind.createLabel(gui, 'Auto Dungeon Özelliği', _t2_x, _t2_y), _t2_x, _t2_y)
_add_tab2(QtBind.createLabel(gui, 'Yakında eklenir...', _t2_x, _t2_y + 30), _t2_x, _t2_y + 30)

_t3_container_x = _tab_bar_x + 30
_t3_container_y = _content_y + 15
_t3_container_w = _tab_bar_w - 60
_t3_container_h = 240

_t3_container = QtBind.createList(gui, _t3_container_x, _t3_container_y, _t3_container_w, _t3_container_h)
_add_tab3(_t3_container, _t3_container_x, _t3_container_y)

_t3_x = _t3_container_x + 15
_t3_y = _t3_container_y + 15

_add_tab3(QtBind.createLabel(gui, '╔═════════════════════════╗', _t3_x, _t3_y), _t3_x, _t3_y)
_add_tab3(QtBind.createLabel(gui, '║   Author:  V i S K i   DaRK_WoLVeS <3      ║', _t3_x, _t3_y + 16), _t3_x, _t3_y + 16)
_add_tab3(QtBind.createLabel(gui, '╚═════════════════════════╝', _t3_x, _t3_y + 32), _t3_x, _t3_y + 32)

_version_y = _t3_y + 58
_add_tab3(QtBind.createLabel(gui, 'Sürüm: v' + pVersion, _t3_x, _version_y), _t3_x, _version_y)

_btn_y = _version_y + 26
_add_tab3(QtBind.createButton(gui, 'check_update', 'Kontrol', _t3_x, _btn_y), _t3_x, _btn_y)
_add_tab3(QtBind.createButton(gui, 'do_auto_update', 'Güncelle', _t3_x + 70, _btn_y), _t3_x + 70, _btn_y)

_status_y = _btn_y + 30
_update_label_ref = QtBind.createLabel(gui, '', _t3_x, _status_y)
_add_tab3(_update_label_ref, _t3_x, _status_y)

_features_y = _status_y + 28
_add_tab3(QtBind.createLabel(gui, 'Plugin Özellikleri:', _t3_x, _features_y), _t3_x, _features_y)
_add_tab3(QtBind.createLabel(gui, '• So-Ok Event otomatik kullanma', _t3_x, _features_y + 22), _t3_x, _features_y + 22)
_add_tab3(QtBind.createLabel(gui, '• Çanta/Banka birleştir ve sırala', _t3_x, _features_y + 42), _t3_x, _features_y + 42)
_add_tab3(QtBind.createLabel(gui, '• Otomatik güncelleme desteği', _t3_x, _features_y + 62), _t3_x, _features_y + 62)

_tab_move(_tab2_widgets, True)
_tab_move(_tab3_widgets, True)

log('[%s] v%s yüklendi.' % (pName, pVersion))
threading.Thread(target=_check_update_thread, name=pName + '_update_auto', daemon=True).start()
