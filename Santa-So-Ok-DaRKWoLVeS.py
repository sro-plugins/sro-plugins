# -*- coding: utf-8 -*-
"""
Santa-So-Ok-DaRKWoLVeS – Jewel Box kırdırma, çanta/banka birleştir, çanta/banka sırala (ayrı ayrı, manuel).

Banka: Banka NPC'sini açmadan kullanmayın. Store (banka) işlemleri sağda, ayrı çerçevede.
"""
from phBot import *
import QtBind
import threading
import time
import struct
import copy

pName = 'Santa-So-Ok-DaRKWoLVeS'
pVersion = '1.1'

MOVE_DELAY = 0.25

# Banka (storage) NPC servername listesi – npc_get_id için
NPC_STORAGE_SERVERNAMES = [
    'NPC_CH_WAREHOUSE_M', 'NPC_CH_WAREHOUSE_W', 'NPC_EU_WAREHOUSE',
    'NPC_WC_WAREHOUSE_M', 'NPC_WC_WAREHOUSE_W', 'NPC_CA_WAREHOUSE',
    'NPC_KT_WAREHOUSE', 'NPC_AR_WAREHOUSE', 'NPC_SD_M_AREA_WAREHOUSE',
    'NPC_SD_T_AREA_WAREHOUSE2'
]

# -------- Jewel Box kırdırma --------
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

# -------- Çantayı birleştir / sırala (ortak yardımcılar) --------
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

# -------- Çantayı birleştir --------
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

# -------- Çantayı sıralı --------
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

# -------- Banka (storage): birleştir / sırala --------
def _npc_get_id_storage():
    """Banka NPC ID (2 byte). Karakter banka NPC'sine yakın olmalı."""
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
    """Banka NPC'sini seçip depoyu açar. Karakter banka NPC'sine yakın olmalı."""
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
    """Banka içinde taşıma. Banka NPC açık olmalı."""
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

# -------- GUI --------
gui = QtBind.init(__name__, pName)

# Her blok: önce çerçeve (stroke) olarak liste kutusu, sonra label ve butonlar
# 1) Jewel Box Kırdır
_y1 = 10
_frame1 = QtBind.createList(gui, 10, _y1 - 2, 180, 52)
QtBind.createLabel(gui, 'Jewel Box Kırdır', 15, _y1)
QtBind.createButton(gui, 'jewel_start', 'Başla', 15, _y1 + 22)
QtBind.createButton(gui, 'jewel_stop', 'Durdur', 95, _y1 + 22)

# 2) Çantayı Birleştir
_y2 = _y1 + 58
_frame2 = QtBind.createList(gui, 10, _y2 - 2, 180, 52)
QtBind.createLabel(gui, 'Çantayı Birleştir', 15, _y2)
QtBind.createButton(gui, 'merge_start', 'Başla', 15, _y2 + 22)
QtBind.createButton(gui, 'merge_stop', 'Durdur', 95, _y2 + 22)

# 3) Çantayı Sıralı
_y3 = _y2 + 58
_frame3 = QtBind.createList(gui, 10, _y3 - 2, 180, 52)
QtBind.createLabel(gui, 'Çantayı Sırala', 15, _y3)
QtBind.createButton(gui, 'sort_start', 'Başla', 15, _y3 + 22)
QtBind.createButton(gui, 'sort_stop', 'Durdur', 95, _y3 + 22)

# Sağ taraf: Store (Banka) bölümü – stroke'tan içeri padding
_store_x = 200
_store_y = 10
_store_w = 200
STORE_PAD = 12
# Dış stroke yüksekliği: not + iki blok, altında az boşluk
_store_h = 22 + 20 + 58 + 52 + 4
_store_inner_x = _store_x + STORE_PAD
_store_inner_y = _store_y + STORE_PAD
_store_inner_w = _store_w - 2 * STORE_PAD

_store_frame = QtBind.createList(gui, _store_x - 2, _store_y - 2, _store_w + 4, _store_h + 4)
QtBind.createLabel(gui, 'Banka NPC yakındaysa otomatik açılır.', _store_inner_x, _store_inner_y)
# Bankayı Birleştir (stroke içinde)
_by1 = _store_inner_y + 22
_store_merge_frame = QtBind.createList(gui, _store_inner_x, _by1 - 2, _store_inner_w, 52)
QtBind.createLabel(gui, 'Bankayı Birleştir', _store_inner_x + 8, _by1)
QtBind.createButton(gui, 'bank_merge_start', 'Başla', _store_inner_x + 8, _by1 + 22)
QtBind.createButton(gui, 'bank_merge_stop', 'Durdur', _store_inner_x + 88, _by1 + 22)
# Bankayı Sırala (stroke içinde)
_by2 = _by1 + 58
_store_sort_frame = QtBind.createList(gui, _store_inner_x, _by2 - 2, _store_inner_w, 52)
QtBind.createLabel(gui, 'Bankayı Sırala', _store_inner_x + 8, _by2)
QtBind.createButton(gui, 'bank_sort_start', 'Başla', _store_inner_x + 8, _by2 + 22)
QtBind.createButton(gui, 'bank_sort_stop', 'Durdur', _store_inner_x + 88, _by2 + 22)

# En altta: Viski template (Author)
_author_x = 10
_author_y = _y3 + 58
QtBind.createLabel(gui, '╔═════════════════════════╗', _author_x, _author_y)
QtBind.createLabel(gui, '║   Author:  V i S K i   DaRK_WoLVeS <3      ║', _author_x, _author_y + 16)
QtBind.createLabel(gui, '╚═════════════════════════╝', _author_x, _author_y + 32)

log('[%s] v%s yüklendi.' % (pName, pVersion))
