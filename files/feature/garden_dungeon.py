# -*- coding: utf-8 -*-
# Garden Dungeon (Tab 3) - Sunucudan indirilip exec ile çalıştırılır.
# Enjekte edilenler: gui, QtBind, log, pName, get_position, set_training_position,
# set_training_radius, set_training_script, start_bot, stop_bot, get_training_area,
# os, time, threading, _download_garden_script, _is_license_valid, plugin_dir,
# tbxGardenScriptPath, lblGardenScriptStatus

_garden_dungeon_running = False
_garden_dungeon_script_path = ""
_garden_dungeon_script_type = "normal"
_garden_dungeon_thread = None
_garden_dungeon_stop_event = threading.Event()
_garden_dungeon_lock = threading.Lock()

def _garden_dungeon_loop():
    global _garden_dungeon_running
    try:
        script_path = _garden_dungeon_script_path

        log('[%s] [Garden-Auto] Garden Dungeon başlatılıyor...' % pName)

        if not script_path or not os.path.exists(script_path):
            log('[%s] [Garden-Auto] Script bulunamadı: %s' % (pName, script_path))
            _garden_dungeon_running = False
            return

        pos = get_position()
        if not pos:
            log('[%s] [Garden-Auto] Pozisyon alınamadı!' % pName)
            _garden_dungeon_running = False
            return

        region = pos.get('region', 0)
        x = pos.get('x', 0)
        y = pos.get('y', 0)
        z = pos.get('z', 0)

        set_training_position(region, x, y, z)
        set_training_radius(50.0)
        log('[%s] [Garden-Auto] Training position ayarlandı: (%d, %.1f, %.1f, %.1f)' % (pName, region, x, y, z))

        result = set_training_script(script_path)
        if result:
            log('[%s] [Garden-Auto] Training script ayarlandı: %s' % (pName, script_path))
        else:
            log('[%s] [Garden-Auto] Training script ayarlanamadı!' % pName)
            _garden_dungeon_running = False
            return

        time.sleep(0.5)

        start_bot()
        _garden_dungeon_running = True
        log('[%s] [Garden-Auto] Bot başlatıldı' % pName)

        while not _garden_dungeon_stop_event.is_set():
            time.sleep(1)

        log('[%s] [Garden-Auto] Garden Dungeon durduruluyor...' % pName)
        stop_bot()
        _garden_dungeon_running = False
    except Exception as ex:
        log('[%s] [Garden-Auto] Hata: %s' % (pName, str(ex)))
        _garden_dungeon_running = False

def garden_dungeon_select_normal():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _garden_dungeon_script_type
    _garden_dungeon_script_type = "normal"
    QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Normal script seçildi')
    log('[%s] [Garden-Auto] Normal script seçildi' % pName)

def garden_dungeon_select_wizz_cleric():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _garden_dungeon_script_type
    _garden_dungeon_script_type = "wizz-cleric"
    QtBind.setText(gui, lblGardenScriptStatus, 'Durum: Wizz/Cleric script seçildi')
    log('[%s] [Garden-Auto] Wizz/Cleric script seçildi' % pName)

def garden_dungeon_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _garden_dungeon_thread, _garden_dungeon_running, _garden_dungeon_script_path, _garden_dungeon_script_type

    script_path_from_ui = QtBind.text(gui, tbxGardenScriptPath).strip()
    if script_path_from_ui:
        script_path_from_ui = script_path_from_ui.strip('"').strip("'").strip()

    if script_path_from_ui:
        _garden_dungeon_script_path = script_path_from_ui
        log('[%s] [Garden-Auto] Özel script yolu: %s' % (pName, _garden_dungeon_script_path))
    elif not _garden_dungeon_script_path:
        if _garden_dungeon_script_type == "wizz-cleric":
            _garden_dungeon_script_path = os.path.join(plugin_dir, "sc", "garden-dungeon-wizz-cleric.txt")
            log('[%s] [Garden-Auto] Wizz/Cleric script kullanılıyor: %s' % (pName, _garden_dungeon_script_path))
        else:
            _garden_dungeon_script_path = os.path.join(plugin_dir, "sc", "garden-dungeon.txt")
            log('[%s] [Garden-Auto] Normal script kullanılıyor: %s' % (pName, _garden_dungeon_script_path))

    has_training_area = False
    try:
        current_area = get_training_area()
        if current_area and current_area.get('name') == 'garden-auto':
            has_training_area = True
    except Exception:
        pass

    if not has_training_area and not os.path.exists(_garden_dungeon_script_path):
        default_normal = os.path.join(plugin_dir, "sc", "garden-dungeon.txt")
        default_wizz = os.path.join(plugin_dir, "sc", "garden-dungeon-wizz-cleric.txt")

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
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
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
