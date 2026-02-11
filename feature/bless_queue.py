# -*- coding: utf-8 -*-
# Sıralı Bless (Tab 10) - Bless Queue. Enjekte: gui, QtBind, log, pName, get_config_dir,
# get_character_data, get_party, get_position, get_inventory, get_skills, inject_joymax,
# _is_license_valid, phBotChat (optional), ctypes
# Widget refs: cbEnable, lstParty, lstQueue, tbBlessId, tbSpam, tbSkip, tbDur, cbSay,
# cmbClericWeapon, cmbMainWeapon, btnRefresh, btnAddAll, btnAddSel, btnSendQueue, btnRemSel,
# btnUp, btnDown, btnClearQ, btnSaveBless, btnScanBless, btnStopBless, btnSaveTimers, btnWRefresh, btnWSave, btnHelpEN

import os, json, threading, time, struct, math, re

try:
    import phBotChat
    HAS_PHBOTCHAT = True
except Exception:
    HAS_PHBOTCHAT = False

def _bq_check_license():
    if not _is_license_valid():
        return False
    return True

def _base_dir():
    return (get_config_dir() or "") + pName + "\\"

def _ensure_dirs():
    try:
        os.makedirs(_base_dir(), exist_ok=True)
    except:
        pass

def _safe_fs(s):
    s = (s or "").strip()
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
    s = re.sub(r"\s+", "_", s)
    return s[:64] if len(s) > 64 else s

def _my_name():
    try:
        cd = get_character_data() or {}
        return (cd.get("name") or "").strip()
    except:
        return ""

def _my_server():
    """
    Try to get server name from character data. phBot differs across builds,
    so we check multiple possible keys.
    """
    try:
        cd = get_character_data() or {}
    except:
        cd = {}

    for k in ["server", "server_name", "serverName", "servername", "shard", "world"]:
        v = cd.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return "UnknownServer"

def _cfg_path():
    _ensure_dirs()
    name = _safe_fs(_my_name() or "UnknownChar")
    srv  = _safe_fs(_my_server())
    return os.path.join(_base_dir(), f"blessq_{srv}_{name}.json")

# Active cfg path (may change after joined_game)
BLESS_CFG = None

def _active_cfg_path():
    global BLESS_CFG
    if not BLESS_CFG:
        BLESS_CFG = _cfg_path()
    return BLESS_CFG

def _default_bless():
    return {
        "bless_id": 11766,
        "duration_s": 45,
        "spam_interval_s": 2.5,
        "skip_turn_s": 15,
        "queue": ["", "", "", "", "", "", "", ""],
        "say_in_party": True,
        "announcer_name": "",

        # dropdown selection (slot numbers)
        "cleric_weapon_slot": -1,
        "main_weapon_slot": -1,

        # tracking by NAME (requested) + FP fallback
        "cleric_name": "",
        "main_name": "",

        # tracking (fingerprints + current slots)
        "cleric_fp": "",
        "main_fp": "",
        "cleric_cur_slot": -1,
        "main_cur_slot": -1
    }

def _load_json(path, default_fn):
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_fn(), f, indent=2)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_fn()
            d = default_fn()
            d.update(data)
            q = d.get("queue")
            if not isinstance(q, list):
                q = [""] * 8
            d["queue"] = (q + [""] * 8)[:8]
            if "id_to_name" in d:
                try:
                    del d["id_to_name"]
                except:
                    pass
            return d
    except:
        return default_fn()

def _save_json(path, data):
    try:
        if isinstance(data, dict) and "id_to_name" in data:
            try:
                del data["id_to_name"]
            except:
                pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log(f"[{pName}] Failed saving {path}: {e}")
        return False

def _save_cfg():
    return _save_json(_active_cfg_path(), BCFG)

def _norm(s):
    return (s or "").strip().lower()

_ensure_dirs()
BCFG = _load_json(_active_cfg_path(), _default_bless)

def _reload_cfg_if_needed():
    """
    On joined_game, character/server become available. Switch to the correct cfg file.
    """
    global BCFG, BLESS_CFG
    newp = _cfg_path()
    if BLESS_CFG != newp:
        BLESS_CFG = newp
        BCFG = _load_json(BLESS_CFG, _default_bless)
        try:
            QtBind.setText(gui, tbBlessId, hex(int(BCFG.get("bless_id", 11766) or 11766)))
        except:
            pass
        try:
            QtBind.setChecked(gui, cbSay, bool(BCFG.get("say_in_party", True)))
        except:
            pass
        try:
            QtBind.setText(gui, tbSpam, str(float(BCFG.get("spam_interval_s", 2.5) or 2.5)))
        except:
            pass
        try:
            QtBind.setText(gui, tbSkip, str(float(BCFG.get("skip_turn_s", 15) or 15)))
        except:
            pass
        try:
            QtBind.setText(gui, tbDur, str(int(BCFG.get("duration_s", 45) or 45)))
        except:
            pass
        log(f"[{pName}] Loaded per-account cfg: {BLESS_CFG}")

_enabled = False   # this client only

def _queue_owner_name():
    try:
        return (BCFG.get("announcer_name") or "").strip()
    except:
        return ""

def _is_queue_owner():
    owner = _queue_owner_name()
    me = _my_name()
    if not owner:
        return True
    return _norm(owner) == _norm(me)

def _deny_if_not_owner(action="This action"):
    if not _is_queue_owner():
        log(f"[{pName}] {action} blocked: queue owner is '{_queue_owner_name()}'")
        return True
    return False

UPDATE_INTERVAL_MS = 2000
MAX_MEMBERS = 8

_timer = None
_pid_to_name_live = {}
_name_to_pid_live = {}

MISSING_GRACE_SEC = 12.0
_missing_since = {}
_missing_mark = set()

def _get_my_xy():
    pos = get_position()
    if not pos:
        return None, None
    return pos.get("x", None), pos.get("y", None)

def _dist_2d(ax, ay, bx, by):
    try:
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
    except:
        return 0.0

def _refresh_live_maps():
    global _pid_to_name_live, _name_to_pid_live
    _pid_to_name_live = {}
    _name_to_pid_live = {}
    party = get_party() or {}
    for _, m in party.items():
        nm = (m.get("name", "") or "").strip()
        pid = int(m.get("player_id", 0) or 0)
        if nm:
            _name_to_pid_live[nm.lower()] = pid
        if pid:
            _pid_to_name_live[pid] = nm

    for nm_low in list(_missing_since.keys()):
        if nm_low in _name_to_pid_live:
            _missing_since.pop(nm_low, None)
            if nm_low in _missing_mark:
                _missing_mark.discard(nm_low)

def _is_in_party(name):
    if not name:
        return False
    return _name_to_pid_live.get(name.lower(), 0) != 0

def _is_missing_confirmed(name):
    n = _norm(name)
    if not n:
        return False

    if _is_in_party(name):
        _missing_since.pop(n, None)
        _missing_mark.discard(n)
        return False

    now = time.time()
    t0 = _missing_since.get(n)
    if t0 is None:
        _missing_since[n] = now
        return False

    if (now - t0) >= float(MISSING_GRACE_SEC):
        _missing_mark.add(n)
        return True

    return False

def _inv_items_list():
    try:
        inv = get_inventory()
    except Exception as e:
        log(f"[{pName}] get_inventory() failed: {e}")
        return None

    if not inv:
        return None

    if isinstance(inv, dict):
        items = inv.get("items", None)
        if isinstance(items, list):
            return items
        if isinstance(inv.get("result"), dict) and isinstance(inv["result"].get("items"), list):
            return inv["result"]["items"]
        return None

    if isinstance(inv, list):
        return inv

    return None

def _item_name_any(it):
    if it is None:
        return ""
    if isinstance(it, dict):
        return str(it.get("name") or it.get("servername") or it.get("item_name") or it.get("type") or "").strip()
    if isinstance(it, (list, tuple)):
        for v in it:
            if isinstance(v, str) and v.strip():
                return v.strip()
        return " ".join([str(x) for x in it[:4]])
    if isinstance(it, (int, float)):
        return f"ID:{int(it)}"
    if isinstance(it, str):
        return it.strip()
    return str(it)

def _weapon_options():
    """
    Dropdown options with your filters:
    - Hide slots: 00-05, 09, 0A, 0B, 0C
    - Hide keywords: pill(s), recovery, scroll, spirit, potion, global chat, coin
    """
    items = _inv_items_list()
    if not items:
        return []

    hide_slots = {0,1,2,3,4,5, 9,10,11,12}
    hide_kw = ["pill", "recovery", "scroll", "spirit", "potion", "global chat", "coin",
               "elixir", "grass", "absor", "damage", "dmg", "stone"]

    opts = []
    for sid in range(len(items)):
        if sid in hide_slots:
            continue
        it = items[sid]
        if it is None:
            continue
        name = _item_name_any(it)
        if not name:
            continue
        low = name.lower()
        bad = False
        for k in hide_kw:
            if k in low:
                bad = True
                break
        if bad:
            continue
        opts.append((sid, f"{sid}: {name}"))

    opts.sort(key=lambda x: x[0])
    return opts

def _parse_slot_from_combo_text(txt):
    try:
        s = str(txt or "").strip()
        if not s:
            return -1
        if ":" in s:
            a = s.split(":", 1)[0].strip()
            return int(a)
        return -1
    except:
        return -1

def _combo_current_text(combo_id):
    try:
        if hasattr(QtBind, "getText"):
            return QtBind.getText(gui, combo_id)
    except:
        pass
    try:
        if hasattr(QtBind, "currentText"):
            return QtBind.currentText(gui, combo_id)
    except:
        pass
    try:
        return QtBind.text(gui, combo_id)
    except:
        return ""

def _get_weapon_slots_from_cfg_or_ui():
    cleric_slot = -1
    main_slot = -1
    try:
        cleric_slot = int(BCFG.get("cleric_weapon_slot", -1) or -1)
    except:
        cleric_slot = -1
    try:
        main_slot = int(BCFG.get("main_weapon_slot", -1) or -1)
    except:
        main_slot = -1

    try:
        if "cmbClericWeapon" in globals():
            cleric_slot = _parse_slot_from_combo_text(_combo_current_text(cmbClericWeapon))
    except:
        pass
    try:
        if "cmbMainWeapon" in globals():
            main_slot = _parse_slot_from_combo_text(_combo_current_text(cmbMainWeapon))
    except:
        pass

    return cleric_slot, main_slot

def btn_refresh_weapons():
    try:
        opts = _weapon_options()

        QtBind.clear(gui, cmbClericWeapon)
        QtBind.clear(gui, cmbMainWeapon)

        QtBind.append(gui, cmbClericWeapon, "-1: (Disabled)")
        QtBind.append(gui, cmbMainWeapon,   "-1: (Disabled)")

        for _, label in opts:
            QtBind.append(gui, cmbClericWeapon, label)
            QtBind.append(gui, cmbMainWeapon,   label)

        log(f"[{pName}] Weapons dropdown refreshed: {len(opts)} items")
    except Exception as e:
        log(f"[{pName}] btn_refresh_weapons error: {e}")

EQUIP_WEAPON_SLOT = 0x06
TRACK_INTERVAL_S = 1.0

_weapon_track_thread = None
_weapon_track_stop = threading.Event()

def _fp_from_any_item(it):
    if it is None:
        return ""
    if isinstance(it, dict):
        name = str(it.get("name") or it.get("servername") or it.get("item_name") or "")
        rid  = str(it.get("id") or it.get("item_id") or it.get("ref_id") or it.get("model") or "")
        plus = str(it.get("plus") or it.get("opt_level") or it.get("enhance") or "")
        return (name + "|" + rid + "|" + plus).strip().lower()
    if isinstance(it, (list, tuple)):
        s = ""
        for v in it:
            if isinstance(v, str) and v.strip():
                s += "|" + v.strip()
        if s:
            return s.strip("|").lower()
        return ("|".join([str(x) for x in it[:6]])).lower()
    if isinstance(it, (int, float)):
        return f"id:{int(it)}"
    if isinstance(it, str):
        return it.strip().lower()
    return str(it).strip().lower()

def _slot_item_fp(slot):
    items = _inv_items_list()
    if not items:
        return ""
    try:
        slot = int(slot)
        if slot < 0 or slot >= len(items):
            return ""
        return _fp_from_any_item(items[slot])
    except:
        return ""

def _slot_item_name(slot):
    items = _inv_items_list()
    if not items:
        return ""
    try:
        slot = int(slot)
        if slot < 0 or slot >= len(items):
            return ""
        it = items[slot]
        if it is None:
            return ""
        return _item_name_any(it)
    except:
        return ""

def _find_slot_by_fp(fp):
    if not fp:
        return -1
    items = _inv_items_list()
    if not items:
        return -1
    try:
        for sid in range(len(items)):
            it = items[sid]
            if it is None:
                continue
            if _fp_from_any_item(it) == fp:
                return sid
    except:
        pass
    return -1

def _find_slot_by_name(wanted_name):
    """
    Find slot by exact item name (case-insensitive).
    If duplicates exist, prefer a slot that is NOT EQUIP_WEAPON_SLOT.
    """
    if not wanted_name:
        return -1

    want = wanted_name.strip().lower()
    items = _inv_items_list()
    if not items:
        return -1

    hits = []
    try:
        for sid in range(len(items)):
            it = items[sid]
            if it is None:
                continue
            nm = _item_name_any(it).strip().lower()
            if nm and nm == want:
                hits.append(sid)
    except:
        return -1

    if not hits:
        return -1

    for sid in hits:
        if int(sid) != int(EQUIP_WEAPON_SLOT):
            return int(sid)
    return int(hits[0])

def _switch_item_slot(src_slot, dst_slot):
    """
    0x7034: 00 <src> <dst> 00 00
    Example: 00 54 06 00 00  (move 0x54 -> 0x06)
    """
    try:
        src = int(src_slot) & 0xFF
        dst = int(dst_slot) & 0xFF
        payload = bytes([0x00, src, dst, 0x00, 0x00])
        return bool(inject_joymax(0x7034, payload, False))
    except Exception as e:
        log(f"[{pName}] switch packet failed: {e}")
        return False

def _update_weapon_refs_from_ui():
    cleric_slot, main_slot = _get_weapon_slots_from_cfg_or_ui()

    BCFG["cleric_weapon_slot"] = int(cleric_slot)
    BCFG["main_weapon_slot"]   = int(main_slot)

    if cleric_slot >= 0:
        BCFG["cleric_name"] = _slot_item_name(cleric_slot)
        BCFG["cleric_fp"]   = _slot_item_fp(cleric_slot)
    else:
        BCFG["cleric_name"] = ""
        BCFG["cleric_fp"]   = ""

    if main_slot >= 0:
        BCFG["main_name"] = _slot_item_name(main_slot)
        BCFG["main_fp"]   = _slot_item_fp(main_slot)
    else:
        BCFG["main_name"] = ""
        BCFG["main_fp"]   = ""

    BCFG["cleric_cur_slot"] = int(cleric_slot)
    BCFG["main_cur_slot"]   = int(main_slot)

    _save_cfg()

def btn_save_weapons():
    try:
        _update_weapon_refs_from_ui()
        log(f"[{pName}] Saved weapons: cleric_slot={BCFG.get('cleric_weapon_slot')} main_slot={BCFG.get('main_weapon_slot')}")
        cn = (BCFG.get("cleric_name") or "").strip()
        mn = (BCFG.get("main_name") or "").strip()
        if cn or mn:
            log(f"[{pName}] Saved names: cleric='{cn}' main='{mn}'")
    except Exception as e:
        log(f"[{pName}] btn_save_weapons error: {e}")

def _weapon_track_loop():
    last_cs = -999
    last_ms = -999

    while not _weapon_track_stop.is_set():
        try:
            cn = str(BCFG.get("cleric_name") or "").strip()
            mn = str(BCFG.get("main_name") or "").strip()
            cf = str(BCFG.get("cleric_fp") or "")
            mf = str(BCFG.get("main_fp") or "")

            cs = -1
            if cn:
                cs = _find_slot_by_name(cn)
            if cs < 0 and cf:
                cs = _find_slot_by_fp(cf)
            if cs >= 0:
                BCFG["cleric_cur_slot"] = int(cs)

            ms = -1
            if mn:
                ms = _find_slot_by_name(mn)
            if ms < 0 and mf:
                ms = _find_slot_by_fp(mf)
            if ms >= 0:
                BCFG["main_cur_slot"] = int(ms)

            cur_cs = int(BCFG.get("cleric_cur_slot", -1) or -1)
            cur_ms = int(BCFG.get("main_cur_slot", -1) or -1)
            if cur_cs != last_cs and last_cs != -999:
                pass
            if cur_ms != last_ms and last_ms != -999:
                pass

            last_cs = cur_cs
            last_ms = cur_ms

        except:
            pass

        time.sleep(float(TRACK_INTERVAL_S))

def _start_weapon_tracker():
    global _weapon_track_thread
    try:
        _weapon_track_stop.clear()
        if not _weapon_track_thread or not _weapon_track_thread.is_alive():
            _weapon_track_thread = threading.Thread(target=_weapon_track_loop, daemon=True)
            _weapon_track_thread.start()
    except:
        pass

def _stop_weapon_tracker():
    try:
        _weapon_track_stop.set()
    except:
        pass

def _equip_cleric_now():
    src = int(BCFG.get("cleric_cur_slot", -1) or -1)
    if src < 0:
        return False
    if src == EQUIP_WEAPON_SLOT:
        return True
    return _switch_item_slot(src, EQUIP_WEAPON_SLOT)

def _equip_main_now():
    src = int(BCFG.get("main_cur_slot", -1) or -1)
    if src < 0:
        return False
    if src == EQUIP_WEAPON_SLOT:
        return True
    return _switch_item_slot(src, EQUIP_WEAPON_SLOT)

def _queue_list():
    q = BCFG.get("queue")
    if not isinstance(q, list):
        q = _default_bless()["queue"]
    q = (q + [""]*8)[:8]
    return [str(x or "").strip() for x in q]

def _save_queue(q):
    global BCFG
    q = (q + [""]*8)[:8]
    BCFG["queue"] = q
    _save_cfg()

def _queue_add(name):
    if _deny_if_not_owner("Add"):
        return False, "Not queue owner"

    name = (name or "").strip()
    if not name:
        return False, "Empty name"
    q = _queue_list()

    for nm in q:
        if _norm(nm) == _norm(name) and nm:
            return False, "Already in queue"

    for i in range(8):
        if not q[i]:
            q[i] = name
            _save_queue(q)
            return True, "Added"

    return False, "Queue full (8)"

def _queue_remove_at(index0):
    if _deny_if_not_owner("Remove"):
        return False

    q = _queue_list()
    if index0 < 0 or index0 >= 8:
        return False
    if not q[index0]:
        return False

    q[index0] = ""
    newq = [x for x in q if x]
    newq = (newq + [""]*8)[:8]
    _save_queue(newq)
    return True

def _clear_queue():
    if _deny_if_not_owner("Remove All"):
        return
    _save_queue([""]*8)

def _queue_swap(i, j):
    if _deny_if_not_owner("Reorder"):
        return False
    if i < 0 or i > 7 or j < 0 or j > 7:
        return False
    q = _queue_list()
    q[i], q[j] = q[j], q[i]
    _save_queue(q)
    return True

def _queue_find_index0_by_name(name):
    q = _queue_list()
    nn = _norm(name)
    for i, nm in enumerate(q):
        if nm and _norm(nm) == nn:
            return i
    return -1

def _bless_id():
    try:
        v = (QtBind.text(gui, tbBlessId) or "").strip()
        if v:
            if v.lower().startswith("0x"):
                return int(v, 16)
            return int(v)
    except:
        pass
    try:
        v = BCFG.get("bless_id", 11766) or 11766
        if isinstance(v, str) and v.lower().startswith("0x"):
            return int(v, 16)
        return int(v)
    except:
        return 11766

def _bless_duration():
    try:
        d = int(BCFG.get("duration_s", 45) or 45)
        return d if d > 0 else 45
    except:
        return 45

def _bless_interval():
    try:
        x = float(BCFG.get("spam_interval_s", 2.5) or 2.5)
        return x if x >= 0.5 else 0.5
    except:
        return 2.5

def _skip_turn_s():
    try:
        s = float(BCFG.get("skip_turn_s", 15) or 15)
        return 0.0 if s <= 0 else s
    except:
        return 15.0

def _say_party(text):
    if not text:
        return
    try:
        if not _enabled:
            return
    except:
        return
    try:
        ann = str(BCFG.get("announcer_name", "") or "").strip()
        if not ann or _norm(ann) != _norm(_my_name()):
            return
    except:
        return
    try:
        if not bool(BCFG.get("say_in_party", True)):
            return
    except:
        pass
    log(text)
    if HAS_PHBOTCHAT:
        try:
            phBotChat.Party(text)
        except:
            pass

def _build_party_rows():
    party = get_party() or {}
    myx, myy = _get_my_xy()
    rows = []
    for _, m in party.items():
        name  = (m.get("name", "Unknown") or "Unknown").strip()
        mx    = m.get("x", 0.0)
        my    = m.get("y", 0.0)
        dist = _dist_2d(myx, myy, mx, my) if (myx is not None and myy is not None) else 0.0
        rows.append(f"{name} D{dist:.1f}")
    rows.sort(key=lambda s: s.lower())
    return rows

def _render_party(rows):
    QtBind.clear(gui, lstParty)
    if not rows:
        QtBind.append(gui, lstParty, "No party data.")
        return
    for i, line in enumerate(rows[:MAX_MEMBERS], 1):
        QtBind.append(gui, lstParty, f"{i}. {line}")

def _render_queue():
    QtBind.clear(gui, lstQueue)
    q = _queue_list()
    QtBind.append(gui, lstQueue, "IDX | NAME")
    QtBind.append(gui, lstQueue, "----------")

    _refresh_live_maps()

    for i, nm in enumerate(q, 1):
        show = nm or "-"
        if nm:
            if _is_missing_confirmed(nm):
                show = f"{nm} (MISSING)"
        QtBind.append(gui, lstQueue, f"{i:>2} | {show}")

_BLESS_OP = 0xB0BD

_BLESS_TOKEN_LOCK = threading.Lock()
_bless_token = 0

_bless_spam_target = ""
_bless_spam_on = False
_bless_last_spam_ts = 0.0
_bless_last_cast_ts = 0.0

_expected_caster = ""
_turn_skip_timer = None

def _bless_inc_token():
    global _bless_token
    with _BLESS_TOKEN_LOCK:
        _bless_token += 1
        return _bless_token

def _bless_get_token():
    with _BLESS_TOKEN_LOCK:
        return _bless_token

def _bless_set_spam(name, enabled):
    global _bless_spam_target, _bless_spam_on, _bless_last_spam_ts
    _bless_spam_target = (name or "").strip()
    _bless_spam_on = bool(enabled) and bool(_bless_spam_target)
    _bless_last_spam_ts = 0.0

def _cancel_skip_timer():
    global _turn_skip_timer
    try:
        if _turn_skip_timer:
            _turn_skip_timer.cancel()
    except:
        pass
    _turn_skip_timer = None

def _bless_stop_all():
    global _bless_last_cast_ts, _expected_caster
    _bless_last_cast_ts = 0.0
    _expected_caster = ""
    _cancel_skip_timer()
    _bless_inc_token()
    _bless_set_spam("", False)

def _queue_next_after(name_or_none):
    q = _queue_list()
    if not any(q):
        return ""
    if not name_or_none:
        for nm in q:
            if nm:
                return nm
        return ""
    cur = _norm(name_or_none)
    start = -1
    for i, nm in enumerate(q):
        if _norm(nm) == cur and nm:
            start = i
            break
    if start < 0:
        for nm in q:
            if nm:
                return nm
        return ""
    for step in range(1, 9):
        nm = q[(start + step) % 8]
        if nm:
            return nm
    return ""

def _start_turn(name, reason_text=""):
    global _expected_caster, _turn_skip_timer

    _cancel_skip_timer()
    _bless_set_spam("", False)

    if not name:
        _expected_caster = ""
        return

    _refresh_live_maps()

    if _is_missing_confirmed(name):
        _say_party(f"({name}) missing → skipped (not removed)")
        _start_turn(_queue_next_after(name), reason_text="")
        return

    _expected_caster = name
    if reason_text:
        _say_party(reason_text)

    _say_party(f"({_expected_caster}) Bless Spell Please")
    _bless_set_spam(_expected_caster, True)

    sk = _skip_turn_s()
    if sk > 0:
        tok = _bless_get_token()

        def _on_skip():
            try:
                if _bless_get_token() != tok:
                    return
                if not _expected_caster or _norm(_expected_caster) != _norm(name):
                    return
            except:
                return

            _refresh_live_maps()

            if _is_missing_confirmed(name):
                _say_party(f"({name}) skipped (timeout {int(sk)}s) + missing → not removed")
            else:
                _say_party(f"({name}) skipped (timeout {int(sk)}s)")

            _bless_inc_token()
            _bless_set_spam("", False)
            _cancel_skip_timer()

            nxt = _queue_next_after(name)
            if nxt:
                _start_turn(nxt, reason_text="")
            else:
                _say_party(f"({name}) skipped → no next")

        _turn_skip_timer = threading.Timer(float(sk), _on_skip)
        _turn_skip_timer.daemon = True
        _turn_skip_timer.start()

def _bless_spam_loop():
    global _bless_last_spam_ts
    while True:
        try:
            if _bless_spam_on and _bless_spam_target:
                now = time.time()
                if _bless_last_spam_ts <= 0 or (now - _bless_last_spam_ts) >= _bless_interval():
                    _bless_last_spam_ts = now
                    _say_party(f"({_bless_spam_target}) bless spell please")
        except:
            pass
        time.sleep(0.25)

threading.Thread(target=_bless_spam_loop, daemon=True).start()

def _schedule_bless_warnings(caster_name):
    dur = _bless_duration()

    in_queue = (_queue_find_index0_by_name(caster_name) >= 0)
    next_name = _queue_next_after(caster_name) if in_queue else ""

    token = _bless_inc_token()
    _bless_set_spam("", False)
    _cancel_skip_timer()

    def _say_if(tok, text):
        if _bless_get_token() == tok:
            _say_party(text)

    def _tcall(delay_s, fn):
        try:
            threading.Timer(max(0.0, float(delay_s)), fn).start()
        except:
            pass

    _say_party(f"{caster_name} casted bless spell  , next player is ({next_name})")

    if next_name:
        for sec in range(10, -1, -1):
            _tcall(dur - sec, lambda s=sec: _say_if(token, f"Bless Spell Ends in {s}s , Next ({next_name})"))

        def _on_finish():
            if _bless_get_token() != token:
                return
            _start_turn(next_name, reason_text="")

        _tcall(dur, _on_finish)
    else:
        _tcall(dur, lambda: _say_if(token, "Bless Spell Finished"))

def _parse_b0bd_owner_and_id(data):
    try:
        if not data or len(data) < 8:
            return None
        owner = struct.unpack_from("<I", data, 0)[0]
        sid   = struct.unpack_from("<I", data, 4)[0]
        return owner, sid
    except:
        return None

_last_autocast_ts = 0.0
_last_autocast_ok = False

_my_turn_until = 0.0
_retry_timer = None

def _cancel_retry():
    global _retry_timer
    try:
        if _retry_timer:
            _retry_timer.cancel()
    except:
        pass
    _retry_timer = None

def _begin_my_turn_window(seconds):
    global _my_turn_until
    _my_turn_until = max(_my_turn_until, time.time() + float(seconds))

def _my_turn_active():
    return time.time() < float(_my_turn_until or 0.0)

def _try_cast_bless_now(reason="", force_inject=True):
    global _last_autocast_ts, _last_autocast_ok

    now = time.time()
    if _last_autocast_ts > 0 and (now - _last_autocast_ts) < 0.65:
        return False

    bid = int(_bless_id())
    ok = False

    if force_inject:
        try:
            payload = bytearray()
            payload += b"\x01\x04"
            payload += struct.pack("<H", bid & 0xFFFF)
            payload += b"\x00\x00\x00"
            r = inject_joymax(0x7074, payload, False)
            if r:
                ok = True
        except Exception as e:
            log(f"[{pName}] Inject cast failed: {e}")
            ok = False

    if not ok:
        try:
            if "use_skill" in globals() and callable(globals().get("use_skill")):
                use_skill(bid)
                ok = True
        except:
            ok = False

    if not ok:
        try:
            if "cast_skill" in globals() and callable(globals().get("cast_skill")):
                cast_skill(bid)
                ok = True
        except:
            ok = False

    try:
        time.sleep(0.15)
        _equip_main_now()
    except:
        pass

    _last_autocast_ts = now
    _last_autocast_ok = ok

    if ok:
        log(f"[{pName}] ✅ Auto-cast Bless on '{_my_name()}' ({reason})")
    else:
        log(f"[{pName}] ❌ Auto-cast failed on '{_my_name()}' ({reason})")
    return ok

def _retry_loop(tag=""):
    global _retry_timer
    try:
        if not _my_turn_active():
            _cancel_retry()
            return

        ok = _try_cast_bless_now(reason=f"Retry {tag}", force_inject=True)
        if ok:
            _cancel_retry()
            return

        _retry_timer = threading.Timer(1.0, lambda: _retry_loop(tag))
        _retry_timer.daemon = True
        _retry_timer.start()
    except:
        _cancel_retry()

def _start_retrying(tag=""):
    if _retry_timer:
        return
    _retry_loop(tag)

def handle_chat(t, player, msg):
    if not _bq_check_license():
        return True
    try:
        text = str(msg or "")
        me = _my_name()
        if not me:
            return True

        if re.search(r"\(\s*"+re.escape(me)+r"\s*\)\s*bless\s*spell\s*please", text, re.IGNORECASE):
            _begin_my_turn_window(max(6.0, float(_skip_turn_s() or 15.0)))
            _try_cast_bless_now(reason="Called Bless Please", force_inject=True)
            _start_retrying(tag="Called")
            return True

        m = re.search(r"Ends\s+in\s+(\d+)\s*s\s*,\s*Next\s*\(\s*([^)]+?)\s*\)", text, re.IGNORECASE)
        if not m:
            return True

        sec = int(m.group(1))
        nxt = (m.group(2) or "").strip()

        if _norm(nxt) != _norm(me):
            return True

        if sec == 5:
            _equip_cleric_now()
            return True

        if sec == 3:
            _begin_my_turn_window(6.0)
            _try_cast_bless_now(reason="Next EndsIn3s", force_inject=True)
            if not _last_autocast_ok:
                _start_retrying(tag="Next3")
            return True

        if 0 <= sec <= 2:
            _begin_my_turn_window(4.0)
            _try_cast_bless_now(reason=f"Next EndsIn{sec}s", force_inject=True)
            if not _last_autocast_ok:
                _start_retrying(tag=f"Next{sec}")
            return True

        return True

    except Exception as e:
        log(f"[{pName}] handle_chat error: {e}")
    return True

def _handle_bless_cast(owner_id):
    global _bless_last_cast_ts, _expected_caster, _my_turn_until

    _refresh_live_maps()

    try:
        owner_id = int(owner_id)
    except:
        return

    mapped = _pid_to_name_live.get(owner_id)
    if not mapped:
        return

    now = time.time()
    if _bless_last_cast_ts > 0 and (now - _bless_last_cast_ts) < 1.0:
        return
    _bless_last_cast_ts = now

    if _norm(mapped) == _norm(_my_name()):
        _my_turn_until = 0.0
        _cancel_retry()

    if _expected_caster and _norm(_expected_caster) == _norm(mapped):
        _expected_caster = ""
        _bless_set_spam("", False)
        _cancel_skip_timer()

    if _bless_spam_on and _bless_spam_target and _norm(_bless_spam_target) == _norm(mapped):
        _bless_set_spam("", False)

    _missing_mark.discard(_norm(mapped))
    _missing_since.pop(_norm(mapped), None)

    _schedule_bless_warnings(mapped)

def handle_joymax(opcode, data):
    if not _bq_check_license():
        return True
    try:
        if opcode != _BLESS_OP:
            return True
        parsed = _parse_b0bd_owner_and_id(data)
        if not parsed:
            return True
        owner_id, sid = parsed
        if sid == _bless_id():
            _handle_bless_cast(owner_id)
    except Exception as e:
        log(f"[{pName}] handle_joymax bless error: {e}")
    return True

# GUI ve widget'lar ana plugin tarafından oluşturulup enjekte edilir

def _selected_party_name():
    try:
        idx = QtBind.currentIndex(gui, lstParty)
        if idx is None or idx < 0:
            return ""
        items = QtBind.getItems(gui, lstParty) or []
        if idx >= len(items):
            return ""
        line = str(items[idx])
        if ". " in line:
            line = line.split(". ", 1)[1]
        name = (line.split(" ", 1)[0]).strip()
        return name
    except:
        return ""

def _selected_queue_index0():
    try:
        idx = QtBind.currentIndex(gui, lstQueue)
        if idx is None or idx < 2:
            return -1
        row = idx - 2
        if row < 0 or row > 7:
            return -1
        q = _queue_list()
        if not q[row]:
            return -1
        return row
    except:
        return -1

def btn_add_all():
    if not _bq_check_license():
        return
    if _deny_if_not_owner("Add All"):
        return
    party = get_party() or {}
    added = 0
    for _, m in party.items():
        name = (m.get("name") or "").strip()
        if not name:
            continue
        ok, _ = _queue_add(name)
        if ok:
            added += 1
    _one_refresh(manual=True)
    log(f"[{pName}] Add All: added {added} party members")

def btn_queue_up():
    if not _bq_check_license():
        return
    row = _selected_queue_index0()
    if row < 0:
        log(f"[{pName}] Select a queued name first.")
        return
    if row == 0:
        return
    if _queue_swap(row, row-1):
        _one_refresh(manual=True)

def btn_queue_down():
    if not _bq_check_license():
        return
    row = _selected_queue_index0()
    if row < 0:
        log(f"[{pName}] Select a queued name first.")
        return
    if row == 7:
        return
    if _queue_swap(row, row+1):
        _one_refresh(manual=True)

def btn_send_queue():
    if not _bq_check_license():
        return
    if not _enabled:
        log(f"[{pName}] Send Queue blocked: plugin is disabled on this client.")
        return

    me = _my_name()
    if me:
        BCFG["announcer_name"] = me
        _save_cfg()

    q = _queue_list()
    lines = []
    idx = 1
    for name in q:
        if name:
            lines.append(f"{idx}- {name}")
            idx += 1

    if not lines:
        log(f"[{pName}] Queue is empty, nothing to send.")
        return

    _say_party("Bless Queue:")
    for line in lines:
        _say_party(line)
        time.sleep(0.2)
def _show_text_dialog(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(None, str(text), str(title), 0x40)
        return
    except Exception as e:
        try:
            log(f"[{pName}] Help popup failed: {e}")
        except:
            pass

def btn_help_en():
    if not _bq_check_license():
        return
    text = (
        "Bless Queue — How to use it (Player Guide)\r\n"
        "====================================\r\n"
        "\r\n"
        "Leader / Owner:\r\n"
        "- Party Leader Will not be able to read Announcements in game chat BUT plugin will auto cast bless for him.\r\n"
        "- The player who presses 'Send Queue' becomes the Leader automatically.\r\n"
        "- Only ONE person should press it.\r\n"
        "\r\n"
        "Setup (Saved once per character):\r\n"
        "1) Press REFRESH\r\n"
        "   - Updates party list + weapons list.\r\n"
        "2) Add Cleric members to the turn list\r\n"
        "   - Select member -> 'Add →' (fills first empty slot)\r\n"
        "   - Or press 'Add All'\r\n"
        "3) Arrange the order\r\n"
        "   - Slot #1 casts first, then #2, then #3...\r\n"
        "   - Use UP / DOWN to reorder\r\n"
        "4) Press SCAN\r\n"
        "   - Finds your Bless skill automatically\r\n"
        "5) Select weapons (IMPORTANT)\r\n"
        "   - Cleric weapon = For Auto Switch your weapon to Cleric to cast bless\r\n"
        "   - Main weapon   = For Switching back to your Main Weapon after casting Bless Spell\r\n"
        "   - Then press SAVE\r\n"
        "\r\n"
        "Timers:\r\n"
        "- DUR  = how long Bless lasts\r\n"
        "- SPAM = how often reminders repeat in party chat\r\n"
        "- SKIP = maximum waiting time before skipping a player (AFK/missing)\r\n"
        "\r\n"
        "Start:\r\n"
        "- Leader presses 'Send Queue'\r\n"
        "- Plugin will call players by order\r\n"
        "- When your name is called: stay ready, plugin will cast for you\r\n"
        "\r\n"
        "Buttons quick meaning:\r\n"
        "- Refresh   : update party + weapons\r\n"
        "- Add →     : add selected member to first empty slot\r\n"
        "- Add All   : add all party members\r\n"
        "- Up/Down   : change turn order\r\n"
        "- Remove    : remove selected slot/member\r\n"
        "- RemoveAll : clear the turn list\r\n"
        "- Save/SaveT: save settings and timers\r\n"
        "- Stop Bless: stop announcements/timers\r\n"
    )
    _show_text_dialog(f"{pName} — Help (EN)", text)

def cb_enable_changed(v):
    if not _bq_check_license():
        return
    global _enabled
    _enabled = bool(v)
    if _enabled:
        _start_timer()
        log(f"[{pName}] Enabled (this client: {_my_name() or 'unknown'})")
    else:
        _stop_timer()
        log(f"[{pName}] Disabled (this client)")
        _bless_stop_all()

def btn_refresh():
    if not _bq_check_license():
        return
    _one_refresh(manual=True)
    try:
        btn_refresh_weapons()
    except:
        pass

def btn_add_selected():
    if not _bq_check_license():
        return
    name = _selected_party_name()
    if not name:
        log(f"[{pName}] Select a party member on the left first.")
        return
    ok, msg = _queue_add(name)
    _one_refresh(manual=True)
    log(f"[{pName}] Add '{name}': {msg}")

def btn_remove_selected():
    if not _bq_check_license():
        return
    row = _selected_queue_index0()
    if row < 0:
        log(f"[{pName}] Select a queued name on the right first.")
        return
    if _queue_remove_at(row):
        _one_refresh(manual=True)
        log(f"[{pName}] Removed queue item #{row+1}")
    else:
        log(f"[{pName}] Remove failed.")

def btn_clear_q():
    if not _bq_check_license():
        return
    _clear_queue()
    _bless_stop_all()
    _one_refresh(manual=True)
    log(f"[{pName}] Queue cleared + bless stopped")

def btn_save_bless():
    if not _bq_check_license():
        return
    global BCFG
    try:
        v = (QtBind.text(gui, tbBlessId) or "").strip()
        bid = int(v, 16) if v.lower().startswith("0x") else int(v)
        BCFG["bless_id"] = bid
        _save_cfg()
        log(f"[{pName}] Saved Bless ID={bid}")
    except Exception as e:
        log(f"[{pName}] Save Bless failed: {e}")

def btn_save_timers():
    if not _bq_check_license():
        return
    global BCFG
    try:
        BCFG["duration_s"] = int((QtBind.text(gui, tbDur) or "45").strip())
    except:
        BCFG["duration_s"] = 45
    try:
        BCFG["spam_interval_s"] = float((QtBind.text(gui, tbSpam) or "2.5").strip())
    except:
        BCFG["spam_interval_s"] = 2.5
    try:
        BCFG["skip_turn_s"] = float((QtBind.text(gui, tbSkip) or "15").strip())
    except:
        BCFG["skip_turn_s"] = 15
    _save_cfg()
    log(f"[{pName}] Saved timers: duration={BCFG['duration_s']} spam={BCFG['spam_interval_s']} skip={BCFG['skip_turn_s']}")

def cb_say_changed(v):
    if not _bq_check_license():
        return
    global BCFG
    BCFG["say_in_party"] = bool(v)
    _save_cfg()

def btn_stop_bless():
    if not _bq_check_license():
        return
    _bless_stop_all()
    log(f"[{pName}] Bless timers/spam stopped")

def btn_scan_bless():
    if not _bq_check_license():
        return
    global BCFG
    try:
        skills = get_skills() or {}
    except Exception as e:
        log(f"[{pName}] Bless scan: get_skills() failed: {e}")
        return

    target_id = None
    target_name = None

    for sid, sdata in (skills.items() if isinstance(skills, dict) else []):
        try:
            _sid = int(sid)
        except:
            continue
        try:
            name = str(sdata.get('name') or sdata.get('skill_name') or "") if isinstance(sdata, dict) else str(sdata)
            n = _norm(name)
        except:
            continue

        if n == "bless spell":
            target_id, target_name = _sid, name
            break
        if ("bless spell" in n) and target_id is None:
            target_id, target_name = _sid, name

    if not target_id:
        log(f"[{pName}] ❌ Bless not found")
        return

    QtBind.setText(gui, tbBlessId, hex(int(target_id)))
    BCFG["bless_id"] = int(target_id)
    _save_cfg()
    log(f"[{pName}] ✅ Bless found: '{target_name}' → ID={int(target_id)}")

def btn_wrefresh():
    if not _bq_check_license():
        return
    btn_refresh_weapons()

def btn_wsave():
    if not _bq_check_license():
        return
    btn_save_weapons()

# ---------------- refresh loop ----------------
def _one_refresh(manual=False):
    _refresh_live_maps()
    party_rows = _build_party_rows()
    _render_party(party_rows)
    _render_queue()

def _tick():
    global _timer
    if not _enabled:
        return
    try:
        _one_refresh(manual=False)
    except Exception as e:
        log(f"[{pName}] tick error: {e}")
    _timer = threading.Timer(UPDATE_INTERVAL_MS / 1000.0, _tick)
    _timer.daemon = True
    _timer.start()

def _start_timer():
    global _timer
    _stop_timer()
    _timer = threading.Timer(0.2, _tick)
    _timer.daemon = True
    _timer.start()

def _stop_timer():
    global _timer
    try:
        if _timer:
            _timer.cancel()
    except:
        pass
    _timer = None

# ---------------- phBot events ----------------
def joined_game():
    _reload_cfg_if_needed()
    _one_refresh(manual=True)
    try:
        btn_refresh_weapons()
    except:
        pass
    _start_weapon_tracker()

def teleported():
    _reload_cfg_if_needed()
    _one_refresh(manual=True)
    try:
        btn_refresh_weapons()
    except:
        pass
    _start_weapon_tracker()

def unload():
    _stop_timer()
    _cancel_retry()
    _stop_weapon_tracker()
    _bless_stop_all()
    _save_cfg()
    log(f"[{pName}] Unloaded")

_one_refresh(manual=True)
try:
    btn_refresh_weapons()
except:
    pass

_start_weapon_tracker()

log(f"[{pName}] [Sıralı Bless] v1.4 yüklendi. Cfg: {_active_cfg_path()} | Client: {_my_name() or 'unknown'}")
