# -*- coding: utf-8 -*-
# Envanter Sayacı (Tab 7 - TR_InventoryCounter) - GitHub'dan indirilip exec ile çalıştırılır.
# Enjekte: gui, QtBind, log, pName, _inv_cnt_name, get_config_dir, get_character_data, os, json,
# phBotChat, get_party, get_guild, get_inventory, get_storage, get_pets, get_guild_storage, get_job_pouch,
# _inv_cnt_lstLeaders, _inv_cnt_lstInfo, _inv_cnt_tbxLeaders, _inv_cnt_tbxTargetPrivate,
# _inv_cnt_cbxAllChat, _inv_cnt_cbxPartyChat, _inv_cnt_cbxGuildChat, _inv_cnt_cbxUnionChat,
# _inv_cnt_cbxPrivateChatSender, _inv_cnt_cbxPrivateChatTarget, _is_license_valid

_inv_cnt_inGame = None
_inv_cnt_selected_chat_channel = "PrivateSender"
_inv_cnt_target_private_name = ""

def _check_license():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return False
    return True

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
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    if not _check_license():
        return
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- COIN : Envanterdeki Gold/Silver/Iron/Copper/Arena Coin miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- COMBATI : Coin of Combativeness (Party) ve Coin of Combativeness (Individual)')
    QtBind.append(gui, _inv_cnt_lstInfo, 'Miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- TOKEN1 : Monk\'s Token miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- TOKEN2 : Soldier\'s Token miktarını bildirir.')
    QtBind.append(gui, _inv_cnt_lstInfo, '- TOKEN3 : General\'s Token miktarını bildirir.')

def inv_cnt_btnstone_clicked():
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    if not _check_license():
        return
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.append(gui, _inv_cnt_lstInfo, '- SETA : Egpty A Grade Eşya Miktarını Bildirir.(Giyilmişler Haric)')
    QtBind.append(gui, _inv_cnt_lstInfo, ' Sadece Drop Sayısını bildirir.(Silah - Kıyafet - Kalkan - Yüzük)')
    QtBind.append(gui, _inv_cnt_lstInfo, '- SETB : Egpty B Grade Eşya Miktarını Bildirir.(Giyilmişler Haric)')
    QtBind.append(gui, _inv_cnt_lstInfo, ' Sadece Drop Sayısını bildirir.(Silah - Kıyafet - Kalkan - Yüzük)')

def inv_cnt_btnstall_clicked():
    if not _check_license():
        return
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
    if not _check_license():
        return
    QtBind.clear(gui, _inv_cnt_lstInfo)
    QtBind.clear(gui, _inv_cnt_lstLeaders)
    QtBind.append(gui, _inv_cnt_lstInfo, "   TR_InventoryCounter - Lider ekleyip sohbetten komut gönderin (ENV, DEPO, GOLD, EXP, SOX vb.).")
    QtBind.append(gui, _inv_cnt_lstInfo, "   Komut listesi için üstteki butonlara tıklayın.")
    
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
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    if not _check_license():
        return
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
    
    if all_items:
        for item in all_items:
            if item is not None and 'name' in item:
                q = item.get('quantity', 1)
                name = item['name']
                sname = item.get('servername', '')
                
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
                
                if "Flower" in name and "Evil" in name: flowerevil += q
                if "Flower" in name and "Illusion" in name: flowerillusion += q
                if "Flower" in name and "Life" in name: flowerlife += q
                if "Flower" in name and "Energy" in name: flowerenergy += q
                if "Flower" in name and "Whirling" in name: flowerwhirling += q
                
                if "ITEM_ETC_ARENA_COIN" in sname: arena += q
                if "ITEM_ETC_SD_TOKEN_04" in sname: qgold += q
                if "ITEM_ETC_SD_TOKEN_03" in sname: silver += q
                if "ITEM_ETC_SD_TOKEN_02" in sname: iron += q
                if "ITEM_ETC_SD_TOKEN_01" in sname: copper += q
                if "ITEM_ETC_SURVIVAL_ARENA_PARTY_COIN" in sname: combativeness1 += q
                if "ITEM_ETC_SURVIVAL_ARENA_SOLO_COIN" in sname: combativeness2 += q
                
                if "Alchemy catalyst" in name: catalyst += q
                if "Berserker Regeneration Potion" in name: berserker += q
                
                if "ITEM_ETC_E060517_MON_GENERATION_BOX" in sname or "ITEM_EVENT_GENERATION_BOX" in sname or "ITEM_EVENT_RENT_E100222_MON_GENERATION_BOX" in sname:
                    pandora += q
                if "ITEM_ETC_E060517_SUMMON_PARTY_SCROLL" in sname or "ITEM_ETC_E060526_SUMMON_PARTY_SCROLL_A" in sname or "ITEM_EVENT_RENT_E100222_SUMMON_SCROLL" in sname:
                    ms += q
                if "ITEM_ETC_E090121_LUCKYBOX" in sname or "ITEM_ETC_E120118_LUCKYBOX" in sname:
                    luckybox += q
                
                if "ITEM_ETC_E070523_LEFT_HEART" in sname: pledge1 += q
                if "ITEM_ETC_E070523_RIGHT_HEART" in sname: pledge2 += q
                
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
                
                if "ITEM_ETC_E090722_" in sname and "ICECREAM" in sname: cream += q
                if "Genie's Lamp" in name: lamp += q
                if "Dirty Lamp" in name: dLamp += q
                
                if 'SET_A_RARE' in sname: aGrade += 1
                if 'SET_B_RARE' in sname: bGrade += 1
                
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
                
                if "Magic stone of Astral" in name and "(Lvl.08)" in name: astral8 += q
                if "Magic stone of Astral" in name and "(Lvl.09)" in name: astral9 += q
                if "Magic stone of Astral" in name and "(Lvl.10)" in name: astral10 += q
                if "Magic stone of Astral" in name and "(Lvl.11)" in name: astral11 += q
                if "Magic stone of immortal" in name and "(Lvl.08)" in name: immortal8 += q
                if "Magic stone of immortal" in name and "(Lvl.09)" in name: immortal9 += q
                if "Magic stone of immortal" in name and "(Lvl.10)" in name: immortal10 += q
                if "Magic stone of immortal" in name and "(Lvl.11)" in name: immortal11 += q
                
                if "ITEM_ETC_LEVEL_TOKEN_01" in sname: token1 += q
                if "ITEM_ETC_LEVEL_TOKEN_02" in sname: token2 += q
                if "ITEM_ETC_LEVEL_TOKEN_03" in sname: token3 += q
                
                if "Increase Strength" in name or "Gücü Arttır" in name: petstr += q
                if "Increase Intelligence" in name or "Zekayı Arttır" in name: petint += q
                
                if "ITEM_ETC_SKILLPOINT_STONE" in sname: faded += q
    
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
    if not _check_license():
        return
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
