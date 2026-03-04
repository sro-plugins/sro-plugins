# -*- coding: utf-8 -*-
# TargetSupport (Tab 9) - xTargetSupport mantığı, plugin içinde çalışır.
# Enjekte: gui, QtBind, log, pName, get_config_dir, get_character_data, get_party,
# inject_joymax, get_locale, struct, os, json, _is_license_valid,
# _ts_cbxEnabled, _ts_cbxDefensive, _ts_tbxLeaders, _ts_lvwLeaders

_ts_character_data = None

def _ts_check_license():
    if not _is_license_valid():
        return False
    return True

def ts_getPath():
    return get_config_dir() + pName + "\\"

def ts_getConfig():
    return ts_getPath() + _ts_character_data['server'] + "_" + _ts_character_data['name'] + ".json"

def ts_isJoined():
    global _ts_character_data
    _ts_character_data = get_character_data()
    if not (_ts_character_data and "name" in _ts_character_data and _ts_character_data["name"]):
        _ts_character_data = None
    return _ts_character_data

def ts_loadConfigs():
    if not _ts_check_license():
        return
    QtBind.setChecked(gui, _ts_cbxEnabled, False)
    QtBind.clear(gui, _ts_lvwLeaders)
    QtBind.setChecked(gui, _ts_cbxDefensive, False)
    if ts_isJoined():
        if os.path.exists(ts_getConfig()):
            try:
                with open(ts_getConfig(), "r", encoding='utf-8') as f:
                    data = json.load(f)
                if "Leaders" in data:
                    for charName in data["Leaders"]:
                        QtBind.append(gui, _ts_lvwLeaders, charName)
                if "Defensive" in data and data['Defensive']:
                    QtBind.setChecked(gui, _ts_cbxDefensive, True)
            except Exception as e:
                log('[%s] [TargetSupport] Config yüklenemedi: %s' % (pName, str(e)))

def ts_list_contains(text, lst):
    text = text.lower()
    for i in range(len(lst)):
        if lst[i].lower() == text:
            return True
    return False

def ts_getCharName(uniqueID):
    players = get_party()
    if uniqueID == _ts_character_data['player_id']:
        return _ts_character_data['name']
    if players:
        for key, player in players.items():
            if player['player_id'] == uniqueID:
                return player['name']
    return ""

def ts_inject_select_target(targetUID):
    p = struct.pack('<I', targetUID)
    inject_joymax(0x7045, p, False)

def ts_handle_joymax(opcode, data):
    if opcode != 0xB070 or not _ts_check_license():
        return True
    if not QtBind.isChecked(gui, _ts_cbxEnabled):
        return True
    if data[0] != 1:
        return True
    skillType = data[1]
    index = 7
    attackerUID = struct.unpack_from("<I", data, index)[0]
    index += 8
    locale = get_locale()
    if locale == 18 or locale == 56:
        index += 4
    targetUID = struct.unpack_from("<I", data, index)[0]
    if skillType == 2:
        charName = ts_getCharName(attackerUID)
        if charName and ts_list_contains(charName, QtBind.getItems(gui, _ts_lvwLeaders)):
            log('[%s] [TargetSupport] Liderden hedef: %s' % (pName, charName))
            ts_inject_select_target(targetUID)
        elif QtBind.isChecked(gui, _ts_cbxDefensive):
            charName = ts_getCharName(targetUID)
            if charName and ts_list_contains(charName, QtBind.getItems(gui, _ts_lvwLeaders)):
                log('[%s] [TargetSupport] Savunma hedef: %s' % (pName, charName))
                ts_inject_select_target(attackerUID)
    return True

def ts_handle_chat(t, charName, msg):
    if not charName or not _ts_check_license():
        return
    if msg.startswith("TARGET "):
        if ts_list_contains(charName, QtBind.getItems(gui, _ts_lvwLeaders)):
            msg = msg[7:]
            if msg == "ON":
                QtBind.setChecked(gui, _ts_cbxEnabled, True)
            elif msg == "OFF":
                QtBind.setChecked(gui, _ts_cbxEnabled, False)

def ts_btnAddLeader_clicked():
    if not _ts_check_license():
        return
    if not ts_isJoined():
        return
    player = QtBind.text(gui, _ts_tbxLeaders)
    if not player or ts_list_contains(player, QtBind.getItems(gui, _ts_lvwLeaders)):
        return
    data = {}
    if os.path.exists(ts_getConfig()):
        with open(ts_getConfig(), 'r', encoding='utf-8') as f:
            data = json.load(f)
    if "Leaders" not in data:
        data['Leaders'] = []
    data['Leaders'].append(player)
    with open(ts_getConfig(), "w", encoding='utf-8') as f:
        f.write(json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False))
    QtBind.append(gui, _ts_lvwLeaders, player)
    QtBind.setText(gui, _ts_tbxLeaders, "")
    log('[%s] [TargetSupport] Lider eklendi: %s' % (pName, player))

def ts_btnRemLeader_clicked():
    if not _ts_check_license():
        return
    if not ts_isJoined():
        return
    selectedItem = QtBind.text(gui, _ts_lvwLeaders)
    if not selectedItem:
        return
    if os.path.exists(ts_getConfig()):
        try:
            with open(ts_getConfig(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            data["Leaders"].remove(selectedItem)
            with open(ts_getConfig(), "w", encoding='utf-8') as f:
                f.write(json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False))
        except Exception:
            pass
    QtBind.remove(gui, _ts_lvwLeaders, selectedItem)
    log('[%s] [TargetSupport] Lider silindi: %s' % (pName, selectedItem))
