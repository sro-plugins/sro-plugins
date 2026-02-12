# -*- coding: utf-8 -*-
# Script & Chat Command Maker (Tab 11). Enjekte: gui, QtBind, log, pName, get_config_dir,
# get_character_data, inject_joymax, _is_license_valid
# Widget refs: tbChat, tbScript, tbOpcode, tbData, tbLeader, tbHide, lstMap, lstHide,
# btnSave, btnLoad, btnRemove, btnEdit, btnHideAdd, btnHideDel, cbLog, lblStatus

import os, json, re, time

def _scm_check_license():
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

def _default_cfg():
    return {
        "leader": "",
        "mappings": [],
        "log_all_c2s": False,
        "hidden_opcodes": []
    }

_cfg = _default_cfg()

def _safe_name(s):
    s = str(s or "").strip()
    s = re.sub(r"[^\w\-\.\(\)\[\] ]+", "_", s)
    s = s.replace(" ", "_")
    return s[:64] if len(s) > 64 else s

def _get_identity():
    try:
        cd = get_character_data()
        if not cd:
            return ("", "")
        server = cd.get("server", "") or cd.get("server_name", "") or ""
        name = cd.get("name", "") or cd.get("character", "") or ""
        return (str(server).strip(), str(name).strip())
    except:
        return ("", "")

_active_cfg_path = None
_active_identity = ("", "")
_last_cfg_check = 0.0

def _cfg_path_for_identity(server, char):
    _ensure_dirs()
    if not server or not char:
        return os.path.join(_base_dir(), "script_command_default.json")
    return os.path.join(_base_dir(), f"script_command_{_safe_name(server)}_{_safe_name(char)}.json")

def _ensure_cfg_path():
    global _active_cfg_path, _active_identity
    server, char = _get_identity()
    new_path = _cfg_path_for_identity(server, char)
    if new_path != _active_cfg_path:
        _active_cfg_path = new_path
        _active_identity = (server, char)
        return True
    return False

def _load_cfg():
    global _cfg
    try:
        _ensure_cfg_path()
        if os.path.exists(_active_cfg_path):
            with open(_active_cfg_path, "r", encoding="utf-8") as f:
                _cfg = json.load(f)
        else:
            _cfg = _default_cfg()
        if "leader" not in _cfg:
            _cfg["leader"] = ""
        if "mappings" not in _cfg:
            _cfg["mappings"] = []
        if "log_all_c2s" not in _cfg:
            _cfg["log_all_c2s"] = False
        if "hidden_opcodes" not in _cfg:
            _cfg["hidden_opcodes"] = []
        mandatory_hidden = ["0x2002", "0x180B", "0x750E", "0x3012", "0x34B6", "0xF04B"]
        changed = False
        for op in mandatory_hidden:
            if op not in _cfg["hidden_opcodes"]:
                _cfg["hidden_opcodes"].append(op)
                changed = True
        if changed:
            _save_cfg()
    except Exception as e:
        log(f"[{pName}] Script Command Maker config load error: {e}")
        _cfg = _default_cfg()

def _save_cfg():
    try:
        _ensure_cfg_path()
        with open(_active_cfg_path, "w", encoding="utf-8") as f:
            json.dump(_cfg, f, indent=2)
    except Exception as e:
        log(f"[{pName}] Script Command Maker save error: {e}")

_edit_mode = False
_last_live_opcode = "0x"
_last_live_data = ""
_last_sel_idx = -1
_last_sel_check = 0.0

def _norm_hex(s):
    s = str(s).strip().lower().replace("0x", "")
    s = re.sub(r"[^0-9a-f]", "", s)
    return ("0x" + s.upper()) if s else ""

def _hex_to_bytes(s):
    s = re.sub(r"[^0-9a-fA-F]", "", str(s))
    if len(s) % 2:
        s = "0" + s
    return bytes.fromhex(s) if s else b""

def _data_for_display(data_str):
    return " ".join(re.findall(r"[0-9A-Fa-f]{2}", str(data_str)))

def _selected_index():
    try:
        s = QtBind.text(gui, lstMap)
        if not s:
            return -1
        left = s.split("]")[0]
        return int(left[1:])
    except:
        return -1

def _find_mapping_by_chat(chat_command):
    cc = chat_command.strip().lower()
    for m in _cfg.get("mappings", []):
        if m.get("chat", "").strip().lower() == cc:
            return m
    return None

def _find_mapping_by_script(key):
    kk = str(key).strip().lower()
    for m in _cfg.get("mappings", []):
        if m.get("script", "").strip().lower() == kk:
            return m
    return None

def _inject_packet_from_mapping(mapping):
    try:
        opcode_hex = str(mapping.get("opcode", "")).strip()
        if not opcode_hex:
            return False
        if not opcode_hex.lower().startswith("0x"):
            opcode_hex = "0x" + opcode_hex
        opcode = int(opcode_hex, 16)
        data_bytes = _hex_to_bytes(mapping.get("data", ""))
        ok = inject_joymax(opcode, data_bytes, False)
        log(f"[{pName}] Injected: {opcode_hex} {re.sub(r'[^0-9A-Fa-f]','', str(mapping.get('data','')))}")
        return bool(ok)
    except Exception as e:
        log(f"[{pName}] Error injecting packet: {e}")
        return False

def _should_log_opcode(opcode_int):
    op = f"0x{int(opcode_int):04X}"
    return op not in _cfg.get("hidden_opcodes", [])

def _refresh_lists():
    QtBind.clear(gui, lstMap)
    for idx, m in enumerate(_cfg.get("mappings", [])):
        chat = m.get("chat", "")
        script = m.get("script", "")
        opcode = m.get("opcode", "")
        data = m.get("data", "")
        if data:
            packet_disp = f"{opcode} : {_data_for_display(data)}"
        else:
            packet_disp = opcode
        QtBind.append(gui, lstMap, f"[{idx}] {chat} | {script} | {packet_disp}")
    QtBind.clear(gui, lstHide)
    for o in _cfg.get("hidden_opcodes", []):
        QtBind.append(gui, lstHide, o)

def ui_log(checked):
    if not _scm_check_license():
        return
    _cfg["log_all_c2s"] = bool(checked)
    _save_cfg()
    QtBind.setText(gui, lblStatus, f"Log all C2S: {bool(checked)}")

def ui_hide_add():
    if not _scm_check_license():
        return
    op = _norm_hex(QtBind.text(gui, tbHide))
    if op and op != "0x":
        if op not in _cfg["hidden_opcodes"]:
            _cfg["hidden_opcodes"].append(op)
            _save_cfg()
            _refresh_lists()
            QtBind.setText(gui, lblStatus, f"Added {op} to hide list")
        else:
            QtBind.setText(gui, lblStatus, f"{op} already in hide list")
    else:
        QtBind.setText(gui, lblStatus, "Invalid opcode")

def ui_hide_del():
    if not _scm_check_license():
        return
    op = QtBind.text(gui, lstHide)
    if op and op in _cfg["hidden_opcodes"]:
        _cfg["hidden_opcodes"].remove(op)
        _save_cfg()
        _refresh_lists()
        QtBind.setText(gui, lblStatus, f"Removed {op} from hide list")
    else:
        QtBind.setText(gui, lblStatus, "Please select an opcode first")

def ui_edit():
    if not _scm_check_license():
        return
    global _edit_mode
    idx = _selected_index()
    if idx < 0:
        QtBind.setText(gui, lblStatus, "Önce bir eşleme seçin")
        return
    _edit_mode = True
    try:
        QtBind.setText(gui, tbLeader, _cfg.get("leader", ""))
    except:
        pass
    m = _cfg["mappings"][idx]
    QtBind.setText(gui, tbChat, m.get("chat", ""))
    QtBind.setText(gui, tbScript, m.get("script", ""))
    QtBind.setText(gui, tbOpcode, m.get("opcode", "0x"))
    QtBind.setText(gui, tbData, _data_for_display(m.get("data", "")))
    QtBind.setText(gui, lblStatus, f"Düzenleniyor [{idx}]")

def ui_save():
    if not _scm_check_license():
        return
    global _edit_mode
    try:
        leader = QtBind.text(gui, tbLeader).strip()
    except:
        leader = ""
    _cfg["leader"] = leader
    chat = QtBind.text(gui, tbChat).strip()
    script = QtBind.text(gui, tbScript).strip()
    opcode = _norm_hex(QtBind.text(gui, tbOpcode))
    data = re.sub(r"[^0-9A-Fa-f]", "", QtBind.text(gui, tbData))
    if not chat:
        QtBind.setText(gui, lblStatus, "Hata: Chat komutu gerekli")
        return
    if not opcode or opcode == "0x":
        QtBind.setText(gui, lblStatus, "Hata: Opcode gerekli")
        return
    entry = {"chat": chat, "script": script, "opcode": opcode, "data": data.upper()}
    idx = _selected_index()
    if idx >= 0:
        _cfg["mappings"][idx] = entry
    else:
        _cfg["mappings"].append(entry)
    _save_cfg()
    _refresh_lists()
    _edit_mode = False
    QtBind.setText(gui, tbChat, "")
    QtBind.setText(gui, tbScript, "")
    QtBind.setText(gui, tbOpcode, "0x")
    QtBind.setText(gui, tbData, "")
    QtBind.setText(gui, lblStatus, "Kaydedildi (hazır)")

def ui_load():
    if not _scm_check_license():
        return
    idx = _selected_index()
    if idx < 0:
        QtBind.setText(gui, lblStatus, "Önce bir eşleme seçin")
        return
    try:
        QtBind.setText(gui, tbLeader, _cfg.get("leader", ""))
    except:
        pass
    m = _cfg["mappings"][idx]
    QtBind.setText(gui, tbChat, m.get("chat", ""))
    QtBind.setText(gui, tbScript, m.get("script", ""))
    QtBind.setText(gui, tbOpcode, m.get("opcode", "0x"))
    QtBind.setText(gui, tbData, _data_for_display(m.get("data", "")))
    QtBind.setText(gui, lblStatus, f"Yüklendi [{idx}]")

def ui_remove():
    if not _scm_check_license():
        return
    global _edit_mode
    idx = _selected_index()
    if idx >= 0:
        removed = _cfg["mappings"].pop(idx)
        _save_cfg()
        _refresh_lists()
        _edit_mode = False
        QtBind.setText(gui, lblStatus, f"Silindi [{idx}] {removed.get('chat','')}")
        QtBind.setText(gui, tbChat, "")
        QtBind.setText(gui, tbScript, "")
        QtBind.setText(gui, tbOpcode, "0x")
        QtBind.setText(gui, tbData, "")
    else:
        QtBind.setText(gui, lblStatus, "Önce bir eşleme seçin")

def handle_chat(t, sender, message):
    if not _scm_check_license():
        return True
    leader = (_cfg.get("leader", "") or "").strip()
    if not leader:
        return True
    if (sender or "").strip().lower() != leader.lower():
        return True
    msg = (message or "").strip().lower()
    mapping = _find_mapping_by_chat(msg)
    if mapping:
        _inject_packet_from_mapping(mapping)
        return False
    return True

def sromanager(args):
    if not _scm_check_license():
        return 500
    try:
        if not args:
            return 500
        a0 = str(args[0]).strip().lower()
        if a0 == "sromanager":
            key = " ".join(str(x) for x in args[1:])
        else:
            key = " ".join(str(x) for x in args)
        key = key.replace(",", " ")
        key = " ".join(key.split()).strip().lower()
        mapping = _find_mapping_by_script(key)
        if mapping:
            _inject_packet_from_mapping(mapping)
            log(f"[{pName}] sromanager executed: {key}")
        else:
            log(f"[{pName}] sromanager key not found: {key}")
        return 500
    except Exception as e:
        log(f"[{pName}] sromanager() error: {e}")
        return 500

def handle_silkroad(opcode, data):
    global _last_live_opcode, _last_live_data, _edit_mode
    if not _cfg.get("log_all_c2s", False):
        return True
    if not _should_log_opcode(opcode):
        return True
    op = f"0x{int(opcode):04X}"
    hexdata = " ".join(f"{x:02X}" for x in data)
    log(f"[C2S] {op} : {hexdata}")
    _last_live_opcode = op
    _last_live_data = hexdata
    if not _edit_mode:
        try:
            QtBind.setText(gui, tbOpcode, op)
            QtBind.setText(gui, tbData, hexdata)
        except:
            pass
    return True

def event_loop():
    global _last_sel_idx, _last_sel_check, _edit_mode, _last_cfg_check
    now = time.time()
    if now - _last_cfg_check > 1.0:
        _last_cfg_check = now
        if _ensure_cfg_path():
            _load_cfg()
            try:
                QtBind.setChecked(gui, cbLog, _cfg.get("log_all_c2s", False))
            except:
                pass
            try:
                QtBind.setText(gui, tbLeader, _cfg.get("leader", ""))
            except:
                pass
            _refresh_lists()
    if now - _last_sel_check < 0.2:
        return
    _last_sel_check = now
    if _edit_mode:
        return
    idx = _selected_index()
    if idx < 0 or idx == _last_sel_idx:
        return
    _last_sel_idx = idx
    try:
        QtBind.setText(gui, lblStatus, f"Seçildi [{idx}] (Düzenle ile yükle)")
    except:
        pass
