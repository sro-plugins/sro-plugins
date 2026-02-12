# -*- coding: utf-8 -*-
# Oto Kervan (Tab 5) - GitHub'dan indirilip exec ile çalıştırılır.
# Enjekte: gui, QtBind, log, pName, plugin_dir, get_config_dir, get_config_path,
# get_character_data, get_position, get_training_area, set_training_area,
# set_training_script, set_training_position, set_training_radius, start_bot, stop_bot,
# generate_script, lblKervanProfile, lstKervanScripts, lblKervanStatus,
# GITHUB_REPO, GITHUB_CARAVAN_FOLDER, GITHUB_CARAVAN_BRANCH, GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE,
# GITHUB_CARAVAN_PROFILE_FOLDER, GITHUB_CARAVAN_PROFILE_JSON_FILENAME, GITHUB_CARAVAN_PROFILE_DB3_FILENAME,
# os, json, time, threading, urllib, shutil, copy, math, _is_license_valid

_caravan_script_list = []
_caravan_running = False
_caravan_script_path = ""
_caravan_thread = None
_caravan_stop_event = threading.Event()
_caravan_lock = threading.Lock()

def _caravan_filename_to_display_name(filename):
    """Dosya adını 'Hotan --> Jangan' formatında gösterim adına çevirir."""
    name = filename.replace('.txt', '').replace('_PHBOT', '')
    parts = name.split('_')
    to_idx = -1
    for i, p in enumerate(parts):
        if p.lower() == 'to':
            to_idx = i
            break
    if to_idx <= 0 or to_idx >= len(parts) - 1:
        return filename
    start = 0
    if parts and len(parts[0]) <= 3 and parts[0][0:1].isdigit():
        start = 1
    from_name = ' '.join(parts[start:to_idx])
    to_name = ' '.join(parts[to_idx + 1:])
    return from_name + ' --> ' + to_name

def _fetch_caravan_script_list():
    """GitHub API veya yerel klasör ile caravan .txt listesini döndürür."""
    path_encoded = urllib.parse.quote(GITHUB_CARAVAN_FOLDER, safe='')
    api_url = 'https://api.github.com/repos/%s/contents/%s?ref=%s' % (
        GITHUB_REPO, path_encoded, GITHUB_CARAVAN_BRANCH
    )
    try:
        req = urllib.request.Request(
            api_url,
            headers={'User-Agent': 'phBot-SROManager/1.0', 'Accept': 'application/vnd.github.v3+json'}
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
        log('[%s] [Oto-Kervan] GitHub listesi alınamadı: %s' % (pName, str(ex)))
    folder = _get_caravan_script_folder()
    if os.path.isdir(folder):
        try:
            names = [f for f in os.listdir(folder) if f.endswith('.txt')]
            names.sort(key=lambda x: x.lower())
            if names:
                log('[%s] [Oto-Kervan] Yerel klasörden %d script listelendi.' % (pName, len(names)))
                return names
        except Exception as ex:
            log('[%s] [Oto-Kervan] Yerel liste okunamadı: %s' % (pName, str(ex)))
    return []

def _get_caravan_script_folder():
    """Oto Kervan scriptlerinin yerel klasör yolunu döndürür (plugin ile aynı dizinde)."""
    return os.path.join(plugin_dir, GITHUB_CARAVAN_FOLDER)

def _download_caravan_script(filename):
    """GitHub'dan tek bir karavan scriptini indirir; yerel yol döndürür veya False."""
    try:
        folder = _get_caravan_script_folder()
        if not os.path.exists(folder):
            os.makedirs(folder)
        script_path = os.path.join(folder, filename)
        path_encoded = urllib.parse.quote(GITHUB_CARAVAN_FOLDER, safe='')
        url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, path_encoded, filename)
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-SROManager/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read()
        if not content or len(content) < 10:
            return False
        with open(script_path, 'wb') as f:
            f.write(content)
        log('[%s] [Oto-Kervan] Script indirildi: %s' % (pName, filename))
        return script_path
    except Exception as ex:
        log('[%s] [Oto-Kervan] Script indirilemedi (%s): %s' % (pName, filename, str(ex)))
        return False

def kervan_refresh_list():
    """GitHub'dan karavan script listesini çeker ve listeyi günceller (gösterim: From --> To)."""
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _caravan_script_list
    QtBind.setText(gui, lblKervanStatus, 'Durum: Liste yükleniyor...')
    names = _fetch_caravan_script_list()
    QtBind.clear(gui, lstKervanScripts)
    _caravan_script_list = []
    if not names:
        QtBind.append(gui, lstKervanScripts, '(Liste alınamadı - Yenile\'yi tekrar deneyin)')
        QtBind.setText(gui, lblKervanStatus, 'Durum: Liste alınamadı')
        log('[%s] [Oto-Kervan] Script listesi boş veya hata.' % pName)
        return
    for name in names:
        _caravan_script_list.append(name)
        display = _caravan_filename_to_display_name(name)
        QtBind.append(gui, lstKervanScripts, display)
    QtBind.setText(gui, lblKervanStatus, 'Durum: %d script listelendi' % len(names))
    log('[%s] [Oto-Kervan] %d karavan scripti listelendi.' % (pName, len(names)))
    _caravan_ensure_karavan_profile_on_init()
    _caravan_update_profile_display()

def _caravan_update_profile_display():
    """Aktif profil adını gösterir."""
    try:
        path = get_config_path()
        if not path:
            QtBind.setText(gui, lblKervanProfile, '(Bilinmiyor)')
            return
        base = os.path.basename(path)
        if base.endswith('.json'):
            profile_name = base[:-5]
            QtBind.setText(gui, lblKervanProfile, profile_name)
        else:
            QtBind.setText(gui, lblKervanProfile, '(Bilinmiyor)')
    except Exception:
        QtBind.setText(gui, lblKervanProfile, '(Hata)')

CARAVAN_JOIN_STEP = 5
CARAVAN_ON_PATH_THRESHOLD = 15

def _caravan_script_from_nearest(script_path, current_region, current_x, current_y, current_z):
    """
    En yakın script waypoint'ini bulur. Char çok uzaktaysa generate_script ile en yakın noktaya
    giden yol alınır, önce o çalıştırılır sonra script devam eder.
    """
    with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    if not lines:
        return ''
    nearest_line_idx = 0
    nearest_dist = float('inf')
    nearest_x, nearest_y, nearest_z = current_x, current_y, current_z
    for i, line in enumerate(lines):
        parts = line.split(',')
        if len(parts) < 2:
            continue
        cmd = parts[0].strip().lower()
        if cmd != 'walk':
            continue
        try:
            if len(parts) == 4:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            elif len(parts) == 5:
                reg = int(parts[1])
                if reg != current_region:
                    continue
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            else:
                continue
        except (ValueError, IndexError):
            continue
        d = math.sqrt((x - current_x) ** 2 + (y - current_y) ** 2 + (z - current_z) ** 2)
        if d < nearest_dist:
            nearest_dist = d
            nearest_line_idx = i
            nearest_x, nearest_y, nearest_z = x, y, z
    start_idx = nearest_line_idx
    if nearest_dist < CARAVAN_ON_PATH_THRESHOLD and nearest_line_idx + 1 < len(lines):
        start_idx = nearest_line_idx + 1
        log('[%s] [Oto-Kervan] Rotada çok yakınsın (%.0f); %d. satırdan devam ediyor.' % (pName, nearest_dist, start_idx + 1))
    elif nearest_line_idx > 0:
        log('[%s] [Oto-Kervan] En yakın nokta %d. satır (mesafe ~%.0f).' % (pName, nearest_line_idx + 1, nearest_dist))
    script_from_nearest = '\n'.join(lines[start_idx:])
    if nearest_dist <= CARAVAN_JOIN_STEP:
        return script_from_nearest
    join_lines = None
    try:
        path_script = generate_script(int(current_region), int(round(nearest_x)), int(round(nearest_y)), int(round(nearest_z)))
        if path_script and isinstance(path_script, list) and len(path_script) > 0:
            join_lines = [ln.strip() for ln in path_script if ln and ln.strip()]
            filtered = []
            for ln in join_lines:
                parts = [p.strip() for p in ln.split(',')]
                if len(parts) >= 4 and parts[0].lower() == 'walk':
                    try:
                        if len(parts) == 4:
                            wx, wy, wz = float(parts[1]), float(parts[2]), float(parts[3])
                        else:
                            wx, wy, wz = float(parts[2]), float(parts[3]), float(parts[4])
                        d = math.sqrt((wx - current_x)**2 + (wy - current_y)**2 + (wz - current_z)**2)
                        if d < CARAVAN_ON_PATH_THRESHOLD:
                            continue
                    except (ValueError, IndexError):
                        pass
                filtered.append(ln)
            if filtered:
                join_lines = filtered
                log('[%s] [Oto-Kervan] Bot en yakın script konumuna götürüyor (%d adım), sonra script devam edecek.' % (pName, len(join_lines)))
            else:
                join_lines = None
    except Exception as ex:
        log('[%s] [Oto-Kervan] generate_script kullanılamadı: %s' % (pName, str(ex)))
    if not join_lines:
        log('[%s] [Oto-Kervan] Pathfinding alınamadı; en yakın noktadan devam (takılma riski).' % pName)
        return script_from_nearest
    return '\n'.join(join_lines) + '\n' + script_from_nearest

def _caravan_temp_script_path():
    """Karavan için geçici script dosyası; phBot set_training_script'in kabul etmesi için Config kökünde."""
    try:
        config_dir = get_config_dir()
        if not config_dir:
            return None
        config_dir = config_dir.rstrip('/\\')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, 'caravan_current.txt')
        return os.path.abspath(path)
    except Exception:
        return None

CARAVAN_PROFILE_FILENAME = 'caravan_profile.json'
CARAVAN_BACKUP_FILENAME = 'caravan_backup.json'
CARAVAN_DB3_PROFILE_SUFFIX = 'caravan'
CARAVAN_DB3_BACKUP_SUFFIX = '_caravan_backup'

def _caravan_profile_path():
    folder = get_config_dir() + pName + "\\"
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder + CARAVAN_PROFILE_FILENAME

def _caravan_backup_path():
    folder = get_config_dir() + pName + "\\"
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder + CARAVAN_BACKUP_FILENAME

def _caravan_db3_filename():
    try:
        cd = get_character_data()
        if cd and cd.get('server') and cd.get('name'):
            return cd['server'] + '_' + cd['name']
    except Exception:
        pass
    return None

def _caravan_db3_dir():
    d = get_config_dir()
    return d.rstrip('/\\') if d else ''

def _caravan_db3_current_path():
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + '.db3')

def _caravan_db3_caravan_path():
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + '.' + CARAVAN_DB3_PROFILE_SUFFIX + '.db3')

def _caravan_db3_backup_path():
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + CARAVAN_DB3_BACKUP_SUFFIX + '.db3')

def _caravan_has_caravan_db3():
    path = _caravan_db3_caravan_path()
    return path and os.path.exists(path)

def _caravan_db3_karavan_named_path():
    fn = _caravan_db3_filename()
    if not fn:
        return None
    return os.path.join(_caravan_db3_dir(), fn + '.Karavan.db3')

def _caravan_download_profile_db3(save_path):
    if not save_path:
        return False
    for folder in ('sc', GITHUB_CARAVAN_FOLDER):
        try:
            path_encoded = urllib.parse.quote(folder, safe='')
            url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, path_encoded, GITHUB_CARAVAN_PROFILE_DB3_FILENAME)
            req = urllib.request.Request(url, headers={'User-Agent': 'phBot-SROManager/1.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            if data:
                with open(save_path, 'wb') as f:
                    f.write(data)
                log('[%s] [Oto-Kervan] Karavan profili (db3) indirildi: %s' % (pName, folder + '/' + GITHUB_CARAVAN_PROFILE_DB3_FILENAME))
                return True
        except Exception:
            continue
    return False

def _caravan_switch_to_caravan_db3():
    current = _caravan_db3_current_path()
    caravan = _caravan_db3_caravan_path()
    backup = _caravan_db3_backup_path()
    if not current or not caravan or not backup:
        return None
    if not os.path.exists(current):
        return None
    try:
        source_db3 = None
        karavan_named = _caravan_db3_karavan_named_path()
        if karavan_named and os.path.exists(karavan_named):
            source_db3 = karavan_named
            log('[%s] [Oto-Kervan] Botta mevcut "Karavan" profili kullanılıyor.' % pName)
        if not source_db3 and os.path.exists(caravan):
            source_db3 = caravan
        if not source_db3:
            if _caravan_download_profile_db3(caravan):
                source_db3 = caravan
            else:
                shutil.copy2(current, caravan)
                source_db3 = caravan
                log('[%s] [Oto-Kervan] Karavan db3 profili oluşturuldu (mevcut ayarlardan); repoda %s yoksa ekleyebilirsiniz.' % (pName, GITHUB_CARAVAN_PROFILE_DB3_FILENAME))
        shutil.copy2(current, backup)
        shutil.copy2(source_db3, current)
        if source_db3 != karavan_named:
            log('[%s] [Oto-Kervan] Karavan db3 profili uygulandı (pick filter, town vb.).' % pName)
        return backup
    except Exception as ex:
        log('[%s] [Oto-Kervan] db3 karavan profili uygulanamadı: %s' % (pName, str(ex)))
        return None

def _caravan_restore_db3(backup_path):
    if not backup_path or not os.path.exists(backup_path):
        return
    current = _caravan_db3_current_path()
    if not current:
        return
    try:
        shutil.copy2(backup_path, current)
        log('[%s] [Oto-Kervan] db3 yedekten geri yüklendi.' % pName)
    except Exception as ex:
        log('[%s] [Oto-Kervan] db3 geri yüklenemedi: %s' % (pName, str(ex)))

def _caravan_apply_tweaks_to_dict(data):
    if not isinstance(data, dict):
        return data
    out = copy.deepcopy(data)
    attack_keys = ('Attack', 'attack', 'Combat', 'combat')
    skip_keys = ('SkipTownScript', 'SkipTown', 'SkipTownLoop', 'NoTownScript', 'SkipTownScriptLoop')

    def apply(obj):
        if not isinstance(obj, dict):
            return
        for k, v in list(obj.items()):
            if isinstance(v, dict):
                apply(v)
            elif isinstance(v, bool):
                if k in attack_keys and v:
                    obj[k] = False
                elif k in skip_keys and not v:
                    obj[k] = True
                else:
                    k_lower = k.lower()
                    if k_lower in ('attack', 'combat') and v:
                        obj[k] = False
                    elif 'skiptown' in k_lower or 'notown' in k_lower:
                        obj[k] = True
    apply(out)
    return out

def _caravan_karavan_json_path():
    fn = _caravan_db3_filename()
    if not fn:
        return None
    config_dir = _caravan_db3_dir()
    if not config_dir:
        path = get_config_path()
        config_dir = os.path.dirname(path) if path else ''
    if not config_dir:
        return None
    return os.path.join(config_dir, fn + '.karavan.json')

def _caravan_phbot_karavan_json_path():
    for suffix in ('.karavan.json', '.Karavan.json'):
        p = os.path.join(_caravan_db3_dir(), _caravan_db3_filename() + suffix) if _caravan_db3_filename() and _caravan_db3_dir() else None
        if p and os.path.exists(p):
            return p
    return None

def _caravan_char_has_any_config():
    fn = _caravan_db3_filename()
    if not fn:
        return False
    config_dir = _caravan_db3_dir()
    if not config_dir or not os.path.isdir(config_dir):
        return False
    try:
        for name in os.listdir(config_dir):
            if name.startswith(fn + '.') or name == fn + '.json':
                return True
    except Exception:
        pass
    return False

def _caravan_download_profile_json(save_path):
    if not save_path:
        return False
    config_dir = os.path.dirname(save_path)
    if config_dir and not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception:
            pass
    try:
        folder_enc = urllib.parse.quote(GITHUB_CARAVAN_PROFILE_FOLDER, safe='')
        url = GITHUB_RAW_CARAVAN_SCRIPT_TEMPLATE % (GITHUB_REPO, GITHUB_CARAVAN_BRANCH, folder_enc, GITHUB_CARAVAN_PROFILE_JSON_FILENAME)
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-SROManager/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if data:
            with open(save_path, 'wb') as f:
                f.write(data)
            basename = os.path.basename(save_path)
            log('[%s] [Oto-Kervan] Karavan profili indirildi; Config içine %s olarak kaydedildi.' % (pName, basename))
            return True
    except Exception:
        pass
    return False

def _caravan_ensure_karavan_profile_on_init():
    """Init'te karavan profili (Server_CharName.karavan.json) yoksa oluşturur (repodan veya mevcut config'ten)."""
    if _caravan_phbot_karavan_json_path():
        return
    save_path = _caravan_karavan_json_path()
    if not save_path:
        return
    if _caravan_download_profile_json(save_path):
        return
    path = get_config_path()
    if not path or not os.path.exists(path):
        return
    try:
        config_dir = os.path.dirname(save_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data = _caravan_apply_tweaks_to_dict(data)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log('[%s] [Oto-Kervan] Init: Karavan profili oluşturuldu (mevcut ayarlardan). Otomatik yapılandırma: "karavan" profilini seçip Başlat\'a basabilirsiniz.' % pName)
    except Exception as ex:
        log('[%s] [Oto-Kervan] Init: Karavan profili oluşturulamadı: %s' % (pName, str(ex)))

def _caravan_ensure_profile_file(current_config_path):
    profile_path = _caravan_profile_path()
    if os.path.exists(profile_path):
        return profile_path
    if not current_config_path or not os.path.exists(current_config_path):
        return None
    try:
        with open(current_config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data = _caravan_apply_tweaks_to_dict(data)
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log('[%s] [Oto-Kervan] Karavan profili oluşturuldu (yedek): %s' % (pName, profile_path))
        return profile_path
    except Exception as ex:
        log('[%s] [Oto-Kervan] Karavan profili oluşturulamadı: %s' % (pName, str(ex)))
        return None

def _caravan_switch_to_profile():
    path = get_config_path()
    if not path or not os.path.exists(path):
        return None
    backup_path = _caravan_backup_path()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            backup_data = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(backup_data)
        profile_path = _caravan_phbot_karavan_json_path()
        if not profile_path:
            save_path = _caravan_karavan_json_path()
            if save_path:
                if not _caravan_char_has_any_config():
                    log('[%s] [Oto-Kervan] Bu char için Config\'te henüz dosya yok; repodan profil indiriliyor.' % pName)
                if _caravan_download_profile_json(save_path):
                    profile_path = save_path
        if not profile_path or not os.path.exists(profile_path):
            profile_path = _caravan_ensure_profile_file(path)
        if not profile_path or not os.path.exists(profile_path):
            return None
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_data = f.read()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(profile_data)
        if _caravan_phbot_karavan_json_path() and profile_path == _caravan_phbot_karavan_json_path():
            log('[%s] [Oto-Kervan] phBot karavan profili uygulandı (config yedeklendi).' % pName)
        else:
            log('[%s] [Oto-Kervan] Karavan profili uygulandı (config yedeklendi).' % pName)
        return backup_path
    except Exception as ex:
        log('[%s] [Oto-Kervan] Profil uygulanamadı: %s' % (pName, str(ex)))
        return None

def _caravan_restore_from_backup(backup_path):
    if not backup_path or not os.path.exists(backup_path):
        return
    path = get_config_path()
    if not path:
        return
    try:
        with open(backup_path, 'r', encoding='utf-8') as f:
            data = f.read()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        log('[%s] [Oto-Kervan] Config yedekten geri yüklendi.' % pName)
    except Exception as ex:
        log('[%s] [Oto-Kervan] Config geri yüklenemedi: %s' % (pName, str(ex)))

def _caravan_loop():
    global _caravan_running
    temp_path = None
    backup_path = None
    try:
        current_area = get_training_area()
        if not current_area:
            cfg_path_now = get_config_path()
            if cfg_path_now and os.path.exists(cfg_path_now):
                try:
                    with open(cfg_path_now, 'r', encoding='utf-8') as f:
                        cfg_now = json.load(f)
                    script_cfg = (cfg_now.get('Loop') or {}).get('Script') or {}
                    if isinstance(script_cfg, dict):
                        for area_name in list(script_cfg.keys()):
                            if area_name and set_training_area(area_name):
                                log('[%s] [Oto-Kervan] Kasılma alanı aktif edildi: %s' % (pName, area_name))
                                break
                except Exception:
                    pass

        backup_path = _caravan_switch_to_profile()
        if not backup_path:
            log('[%s] [Oto-Kervan] Config profil uygulanamadı; mevcut ayarlarla devam ediliyor.' % pName)

        script_path = _caravan_script_path
        log('[%s] [Oto-Kervan] Karavan yürüyüşü başlatılıyor: %s' % (pName, script_path))
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
        cx = float(pos.get('x', 0))
        cy = float(pos.get('y', 0))
        cz = float(pos.get('z', 0))
        script_content = _caravan_script_from_nearest(script_path, region, cx, cy, cz)
        if not script_content:
            log('[%s] [Oto-Kervan] Script dosyası boş veya uygun nokta yok!' % pName)
            _caravan_running = False
            return
        temp_path = _caravan_temp_script_path()
        if not temp_path:
            log('[%s] [Oto-Kervan] Geçici dosya yolu alınamadı.' % pName)
            _caravan_running = False
            return
        with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script_content)
        current_area = get_training_area()
        if not current_area and backup_path and os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                script_cfg = (cfg.get('Loop') or {}).get('Script') or {}
                if isinstance(script_cfg, dict):
                    for area_name in list(script_cfg.keys()):
                        if area_name and set_training_area(area_name):
                            log('[%s] [Oto-Kervan] Aktif training area seçildi: %s' % (pName, area_name))
                            break
            except Exception:
                pass
        set_training_position(region, cx, cy, cz)
        set_training_radius(600.0)
        script_path_for_bot = os.path.abspath(temp_path)
        script_set_ok = set_training_script(script_path_for_bot)
        if not script_set_ok:
            cfg_path = get_config_path()
            if cfg_path and os.path.exists(cfg_path):
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                    loop = cfg.get('Loop')
                    if not isinstance(loop, dict):
                        loop = {}
                        cfg['Loop'] = loop
                    script_cfg = loop.get('Script')
                    if not isinstance(script_cfg, dict):
                        script_cfg = {}
                        loop['Script'] = script_cfg
                    caravan_area = {
                        'Data': [],
                        'Enabled': True,
                        'Path': script_path_for_bot.replace('/', '\\'),
                        'Pick Radius': 50,
                        'Polygon': [],
                        'Radius': 600.0,
                        'Region': region,
                        'Type': 0,
                        'X': float(cx),
                        'Y': float(cy),
                        'Z': float(cz),
                    }
                    for name in list(script_cfg.keys()):
                        if isinstance(script_cfg.get(name), dict):
                            script_cfg[name]['Enabled'] = False
                    script_cfg['Caravan'] = caravan_area
                    with open(cfg_path, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, indent=4, ensure_ascii=False)
                    script_set_ok = True
                    log('[%s] [Oto-Kervan] Kasılma alanı yoktu; config\'e "Caravan" alanı eklendi, script atandı, bot başlatılıyor.' % pName)
                except Exception as ex:
                    log('[%s] [Oto-Kervan] Config güncellenemedi: %s' % (pName, str(ex)))
            if not script_set_ok:
                log('[%s] [Oto-Kervan] Seçilen script atanamadı. Yol: %s' % (pName, script_path_for_bot))
                _caravan_running = False
                return
        time.sleep(0.3)
        if not get_training_area():
            log('[%s] [Oto-Kervan] Kasılma: Kasılma alanınızı aktif etmediniz. Bot başlatılamıyor.' % pName)
            _caravan_running = False
            QtBind.setText(gui, lblKervanStatus, 'Durum: Durduruldu ■')
            return
        start_bot()
        _caravan_running = True
        log('[%s] [Oto-Kervan] Karavan scripti dosyadan çalışıyor (training script).' % pName)
        while not _caravan_stop_event.is_set():
            time.sleep(1)
        log('[%s] [Oto-Kervan] Karavan durduruluyor...' % pName)
        stop_bot()
        _caravan_running = False
    except Exception as ex:
        log('[%s] [Oto-Kervan] Hata: %s' % (pName, str(ex)))
        _caravan_running = False
        try:
            stop_bot()
        except Exception:
            pass
    finally:
        if backup_path:
            _caravan_restore_from_backup(backup_path)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def kervan_start():
    if not _is_license_valid():
        log('[%s] Bu özelliği kullanmak için geçerli bir lisans anahtarı gereklidir!' % pName)
        return
    global _caravan_script_path, _caravan_thread
    try:
        path = get_config_path()
        if not path:
            log('[%s] [Oto-Kervan] Profil bilgisi alınamadı. Botu tekrar açıp oyuna giriş yapın.' % pName)
            QtBind.setText(gui, lblKervanStatus, 'Durum: Profil alınamadı')
            return
        profile_name = os.path.basename(path)
        if profile_name.endswith('.json'):
            profile_name = profile_name[:-5]
        if 'karavan' not in profile_name.lower():
            log('[%s] [Oto-Kervan] Karavan profili seçili değil! Ana pencereden karavan profilini seçin, sonra Başlat\'a basın.' % pName)
            QtBind.setText(gui, lblKervanStatus, 'Durum: Karavan profili seçili değil!')
            return
    except Exception:
        log('[%s] [Oto-Kervan] Profil kontrolü yapılamadı.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Profil kontrolü hatası')
        return

    selected_display = QtBind.text(gui, lstKervanScripts).strip()
    if not selected_display or selected_display.startswith('('):
        log('[%s] [Oto-Kervan] Lütfen listeden bir script seçin.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Önce script seçin')
        return
    selected = None
    for fname in _caravan_script_list:
        if _caravan_filename_to_display_name(fname) == selected_display:
            selected = fname
            break
    if not selected:
        log('[%s] [Oto-Kervan] Seçim eşleşmedi; listeyi Yenile ile tekrar yükleyin.' % pName)
        QtBind.setText(gui, lblKervanStatus, 'Durum: Listeyi yenileyin')
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
    if not _is_license_valid():
        return
    global _caravan_thread, _caravan_running
    try:
        stop_bot()
    except Exception:
        pass
    with _caravan_lock:
        _caravan_stop_event.set()
        if _caravan_thread and _caravan_thread.is_alive():
            _caravan_thread.join(timeout=3)
        _caravan_thread = None
        _caravan_running = False
    QtBind.setText(gui, lblKervanStatus, 'Durum: Durduruldu ■')
    log('[%s] [Oto-Kervan] Durduruldu.' % pName)
