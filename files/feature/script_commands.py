# -*- coding: utf-8 -*-
# Script Komutları (Tab 6 - TR_ScriptCommands) - GitHub'dan indirilip exec ile çalıştırılır.
# Enjekte: gui, QtBind, log, pName, script_cmds_path, _script_cmds_SaveName, _script_cmds_RecordBtn,
# _script_cmds_Display, _script_cmds_cbxShowPackets, get_party, inject_joymax, show_notification,
# create_notification, play_wav, set_training_script, get_client, start_bot, stop_bot, start_trace,
# get_active_skills, get_inventory, get_pets, get_config_dir, get_character_data, get_profile, set_profile,
# set_training_area, get_position, os, json, struct, threading, datetime, timedelta, subprocess, signal,
# _is_license_valid

_script_cmds_StartBotAt = ''
_script_cmds_CloseBotAt = ''
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

def _script_cmds_ResetSkip():
    global _script_cmds_SkipCommand
    _script_cmds_SkipCommand = False

def _check_license():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return False
    return True

def LeaveParty(args):
    if not _check_license():
        return 0
    if get_party():
        inject_joymax(0x7061, b'', False)
        log('[%s] Partiden çıkılıyor' % pName)
    return 0

def Notification(args):
    if not _check_license():
        return 0
    if len(args) == 3:
        title, message = args[1], args[2]
        show_notification(title, message)
        return 0
    log('[%s] Hatalı Bildirim komutu' % pName)
    return 0

def NotifyList(args):
    if not _check_license():
        return 0
    if len(args) == 2:
        create_notification(args[1])
        return 0
    log('[%s] Hatalı NotifyList komutu' % pName)
    return 0

def PlaySound(args):
    if not _check_license():
        return 0
    if len(args) < 2:
        return 0
    fname = args[1]
    if os.path.exists(script_cmds_path + fname):
        play_wav(script_cmds_path + fname)
        log('[%s] [%s] oynatılıyor' % (pName, fname))
        return 0
    log('[%s] [%s] ses dosyası mevcut değil' % (pName, fname))
    return 0

def SetScript(args):
    if not _check_license():
        return 0
    if len(args) < 2:
        return 0
    name = args[1]
    if os.path.exists(script_cmds_path + name):
        set_training_script(script_cmds_path + name)
        log('[%s] Komut [%s] olarak değiştirildi' % (pName, name))
        return 0
    log('[%s] [%s] komutu mevcut değil' % (pName, name))
    return 0

def CloseBot(args):
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
    pid = (get_client() or {}).get('pid')
    if pid:
        os.kill(pid, signal.SIGTERM)
        return 0
    log('[%s] İstemci açık değil!' % pName)
    return 0

def StartBot(args):
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
    if len(args) < 2:
        return 0
    cmdargs = args[1]
    if os.path.exists(script_cmds_path + "phBot.exe"):
        subprocess.Popen(script_cmds_path + "phBot.exe " + cmdargs)
        log('[%s] Yeni bir bot açılıyor' % pName)
        return 0
    log('[%s] Geçersiz bot yolu' % pName)
    return 0

def DismountPet(args):
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    if not _check_license():
        return 0
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
    custom_path = script_cmds_path + "CustomNPC.json"
    if not os.path.exists(custom_path):
        return
    with open(custom_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if name in data:
        _script_cmds_ExecutedPackets = data[name].get('Packets', [])

def _script_cmds_SaveNPCPackets(name, packets=None):
    if packets is None:
        packets = []
    custom_path = script_cmds_path + "CustomNPC.json"
    data = {}
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[name] = {"Packets": packets}
    with open(custom_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))
    log('[%s] Özel NPC Komutu Kaydedildi' % pName)

def CustomNPC(args):
    if not _check_license():
        return 0
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

def script_cmds_button_start():
    if not _check_license():
        return
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
    if not _check_license():
        return
    QtBind.clear(gui, _script_cmds_Display)
    custom_path = script_cmds_path + "CustomNPC.json"
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for name in data:
                QtBind.append(gui, _script_cmds_Display, name)
    else:
        log('[%s] Şu anda kaydedilmiş komut yok' % pName)

def script_cmds_button_DelCmds():
    if not _check_license():
        return
    name = QtBind.text(gui, _script_cmds_Display)
    QtBind.clear(gui, _script_cmds_Display)
    custom_path = script_cmds_path + "CustomNPC.json"
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
    if not _check_license():
        return
    name = QtBind.text(gui, _script_cmds_Display)
    QtBind.clear(gui, _script_cmds_Display)
    custom_path = script_cmds_path + "CustomNPC.json"
    if not name or not os.path.exists(custom_path):
        return
    with open(custom_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if name in data:
        for packet in data[name].get('Packets', []):
            QtBind.append(gui, _script_cmds_Display, packet)

def script_cmds_cbxAuto_clicked(checked):
    pass

def _script_cmds_event_tick():
    """StartBot/CloseBot zamanlama kontrolü - event_loop'tan çağrılır."""
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

def _script_cmds_packet_hook(opcode, data):
    """Özel NPC paket kaydı - handle_silkroad'tan çağrılır. True döner."""
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
