# -*- coding: utf-8 -*-
# Auto Dungeon (Tab 2) - xAutoDungeon mantığı, UI sromanager'da.
# Enjekte: gui, QtBind, log, pName, get_config_dir, get_character_data, get_drops,
# get_monsters, get_position, start_bot, stop_bot, set_training_position,
# set_training_radius, move_to, get_inventory, get_item, get_npcs, inject_joymax,
# get_locale, sqlite3, struct, time, threading, json, os,
# WAIT_DROPS_DELAY_MAX, COUNT_MOBS_DELAY, _is_license_valid,
# set_item_used_by_plugin, get_dimensional_item_activated,
# lstMobs, tbxMobs, lstMonsterCounter, cbxIgnore*, cbxOnlyCount*, cbxAcceptForgottenWorld

character_data = None
lstMobsData = []
lstIgnore = []
lstOnlyCount = []

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
        log('[%s] Timeout for picking up drops!' % pName)
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
            log('[%s] Waiting for picking up "%s"...' % (pName, drop['name']))
            time.sleep(1.0)
            WaitPickableDrops(filterCursor, waiting + 1)

def getMobCount(position, radius):
    QtBind.clear(gui, lstMonsterCounter)
    QtBind.append(gui, lstMonsterCounter, 'Name (Type)')
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
            log('[%s] Starting to kill (%d) mobs at this area. Radius: %s' % (pName, count, str(radius) if radius != None else 'Max.'))
        threading.Timer(wait, AttackMobs, [wait, True, position, radius]).start()
    else:
        log('[%s] All mobs killed!' % pName)
        conn = GetFilterConnection()
        cursor = conn.cursor()
        WaitPickableDrops(cursor)
        conn.close()
        stop_bot()
        set_training_position(0, 0, 0, 0)
        log('[%s] Getting back to the script...' % pName)
        threading.Timer(2.5, move_to, [position['x'], position['y'], position['z']]).start()
        threading.Timer(5.0, start_bot).start()

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
                match = (itemData and itemData.get('tid1') == 3 and itemData.get('tid2') == 12 and itemData.get('tid3') == 7)
            if match:
                item['slot'] = slot
                return item
    return None

def GetDimensionalPillarUID(Name):
    npcs = get_npcs()
    if npcs:
        for uid, npc in npcs.items():
            item = get_item(npc['model'])
            if item and item.get('name') == Name:
                return uid
    return 0

def EnterToDimensional(Name):
    uid = GetDimensionalPillarUID(Name)
    if uid:
        log('[%s] Selecting dimensional hole...' % pName)
        packet = struct.pack('I', uid)
        inject_joymax(0x7045, packet, False)
        time.sleep(1.0)
        log('[%s] Entering to dimensional hole...' % pName)
        inject_joymax(0x704B, packet, False)
        packet += struct.pack('H', 3)
        inject_joymax(0x705A, packet, False)
        threading.Timer(5.0, start_bot).start()
        return
    log('[%s] "%s" cannot be found around you!' % (pName, Name))

def GoDimensionalThread(Name):
    dim_activated = get_dimensional_item_activated()
    if dim_activated:
        Name = dim_activated.get('name', '')
        log('[%s] %s still opened!' % (pName, '"' + Name + '"' if Name else 'Dimensional Hole'))
        EnterToDimensional(Name)
        return
    item = GetDimensionalHole(Name)
    if item:
        log('[%s] Using "%s"...' % (pName, item['name']))
        p = struct.pack('B', item['slot'])
        locale = get_locale()
        if locale in [56, 18, 61]:
            p += b'\x30\x0C\x0C\x07'
        else:
            p += b'\x6C\x3E'
        set_item_used_by_plugin(item)
        inject_joymax(0x704C, p, True)
    else:
        log('[%s] %s cannot be found at your inventory' % (pName, '"' + Name + '"' if Name else 'Dimensional Hole'))

def Checkbox_Checked(checked, gListName, mobType):
    gListReference = globals()[gListName]
    if checked:
        gListReference.append(mobType)
    else:
        gListReference.remove(mobType)
    saveConfigs()

def _cbx_clicked(checked, gListName, mobType):
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    Checkbox_Checked(checked, gListName, mobType)

def btnAddMob_clicked():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global lstMobsData
    text = QtBind.text(gui, tbxMobs)
    if text and not ListContains(text, lstMobsData):
        lstMobsData.append(text)
        QtBind.append(gui, lstMobs, text)
        QtBind.setText(gui, tbxMobs, "")
        saveConfigs()
        log('[%s] Monster added [%s]' % (pName, text))

def btnRemMob_clicked():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global lstMobsData
    selected = QtBind.text(gui, lstMobs)
    if selected:
        lstMobsData.remove(selected)
        QtBind.remove(gui, lstMobs, selected)
        saveConfigs()
        log('[%s] Monster removed [%s]' % (pName, selected))

def cbxIgnoreGeneral_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 0)
def cbxOnlyCountGeneral_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 0)
def cbxIgnoreChampion_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 1)
def cbxOnlyCountChampion_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 1)
def cbxIgnoreGiant_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 4)
def cbxOnlyCountGiant_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 4)
def cbxIgnoreTitan_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 5)
def cbxOnlyCountTitan_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 5)
def cbxIgnoreStrong_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 6)
def cbxOnlyCountStrong_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 6)
def cbxIgnoreElite_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 7)
def cbxOnlyCountElite_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 7)
def cbxIgnoreUnique_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 8)
def cbxOnlyCountUnique_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 8)
def cbxIgnoreParty_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 16)
def cbxOnlyCountParty_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 16)
def cbxIgnoreChampionParty_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 17)
def cbxOnlyCountChampionParty_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 17)
def cbxIgnoreGiantParty_clicked(checked):
    _cbx_clicked(checked, "lstIgnore", 20)
def cbxOnlyCountGiantParty_clicked(checked):
    _cbx_clicked(checked, "lstOnlyCount", 20)

def cbxAcceptForgottenWorld_checked(checked):
    if not _is_license_valid():
        return
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
        with open(getConfig(), "r", encoding='utf-8') as f:
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
        with open(getConfig(), "w", encoding='utf-8') as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

def AttackArea(args):
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return 0
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
        log('[%s] No mobs at this area. Radius: %s' % (pName, str(radius) if radius != None else 'Max.'))
    return 0

def GoDimensional(args):
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return 0
    stop_bot()
    name = ''
    if len(args) > 1:
        name = args[1]
    threading.Timer(0.001, GoDimensionalThread, [name]).start()
    return 0
