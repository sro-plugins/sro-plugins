# -*- coding: utf-8 -*-
# Auto Hwt (Tab 4) - SROMaster FGW & HWT mantığı, UI sromanager'da.
# Scriptler: Gemi Enkazı 1-2/3-4 sunucudan (api/download SC), diğerleri GitHub sc/ veya yerel.
# Attack Area 1-8: Config/SROManager/FGW_<PC>/ - Her PC kendi klasörüne yazar (4 PC çakışmasız).
# Enjekte: gui, QtBind, log, pName, get_config_dir, plugin_dir, urllib,
# GITHUB_FGW_RAW_TEMPLATE, GITHUB_FGW_SCRIPT_FILENAMES, _download_from_server,
# get_position, get_monsters, set_training_script, set_training_position, start_bot, stop_bot,
# create_notification, get_training_script, time, os, _is_license_valid, cbEnabled, cbMobIgnore, cbP1..cbP8

def _get_pc_id():
    """Bilgisayar adı - 4 PC'de her biri kendi FGW klasörüne yazar."""
    try:
        return os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'PC1'))
    except Exception:
        return 'PC1'

def _get_sc_folder():
    """Script klasörü: files/sc (vps uyumlu) veya sc/ - GitHub ile senkron."""
    for sub in ['files/sc', 'sc']:
        p = os.path.join(plugin_dir, sub.replace('/', os.sep))
        if os.path.exists(p):
            return p
    return os.path.join(plugin_dir, 'files', 'sc')

def _get_fgw_folder():
    """Attack Area klasörü: Config/SROManager/FGW_<PC>/ - PC bazlı (4 PC uyumlu)."""
    cfg = get_config_dir()
    pc_id = _get_pc_id()
    if cfg:
        base = cfg.rstrip('/\\') + os.sep + pName
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return base + os.sep + 'FGW_' + pc_id + os.sep

SC_FOLDER = None
FGW_FOLDER = None

ATTACKAREA_FILENAMES = [
    "FGW Attack Area1.txt", "FGW Attack Area2.txt", "FGW Attack Area3.txt", "FGW Attack Area4.txt",
    "FGW Attack Area5.txt", "FGW Attack Area6.txt", "FGW Attack Area7.txt", "FGW Attack Area8.txt",
]
ATTACKAREA_FILENAME = ATTACKAREA_FILENAMES[0]
DYNAMIC_ATTACK_FILENAME = "FGW_DYNAMIC_ATTACKAREA.txt"

# Script dosya eşlemesi (display_name -> filename)
# Gemi Enkazı 1-2/3-4: api/download SC ile sunucudan (sunucudaki dosya adlarıyla).
FGW_SCRIPT_MAP = [
    ('Togui Köyü', 'Togui Village Forgotten World.txt', 'SCRIPT_TOGUI'),
    ('Gemi Enkazı 1-2★', 'Ship Wreck 1-2 Stars Forgotten World.txt', 'SCRIPT_SHIP12'),
    ('Gemi Enkazı 3-4★', 'Ship Wreck 3-4 Stars Forgotten World.txt', 'SCRIPT_SHIP34'),
    ('Alev Dağı', 'Flame Mountain Forgotten World.txt', 'SCRIPT_FLAME'),
    ('HWT Başlangıç', 'Holy Water Temple Beginner.txt', 'SCRIPT_HWT_BEGINNER'),
    ('HWT Orta', 'Holy Water Temple Intermediate.txt', 'SCRIPT_HWT_INTERMEDIATE'),
    ('HWT İleri', 'Holy Water Temple Advanced.txt', 'SCRIPT_HWT_ADVANCED'),
]

_my_slot = 1
_last_fgw_script_path = None
_current_state = 'fgw'
_last_check = 0.0
_pluginEnabled = False
_mobIgnoreEnabled = True  # Mob Yoksay: True ise Ghost Curse vb. yoksayılır
_attack_to_normal_wait_since = 0.0  # attack'tan normal'e geçişte 5 sn bekleme
_pre_attack_position = None  # attack'a geçmeden önceki script konumu (region, x, y, z)
_last_attack_had_unique = False  # önceki tick'te slotta Unique vardı mı
_unique_kill_wait_until = 0.0  # Unique öldü, drop bekleme bitiş zamanı
# Engel takılma: konum değişmezse geri dönüp tekrar dene
_last_attack_pos = None
_attack_pos_unchanged_since = 0.0
_last_known_moving_pos = None

def _dist2(ax, ay, bx, by):
    return (bx - ax) ** 2 + (by - ay) ** 2

def _do_stuck_recovery():
    """Engelde takılı kaldı; önceki konuma dönüp tekrar dene."""
    global _last_attack_pos, _attack_pos_unchanged_since, _last_known_moving_pos
    back_pos = _last_known_moving_pos or _pre_attack_position
    if not back_pos or len(back_pos) < 4:
        return
    pos = get_position()
    if not pos:
        return
    try:
        region = int(pos.get('region', 0))
    except (TypeError, ValueError):
        return
    stop_bot()
    log('[%s] Engel tespit edildi, önceki konuma dönülüyor...' % pName)
    create_notification('FGW: Engel tespit, geri dönülüyor')
    move_to_fn = globals().get('move_to')
    move_to_region_fn = globals().get('move_to_region')
    br, bx, by, bz = back_pos[0], back_pos[1], back_pos[2], back_pos[3]
    if region == br and move_to_fn:
        move_to_fn(bx, by, bz)
    elif move_to_region_fn:
        move_to_region_fn(br, bx, by, bz)
    _last_attack_pos = None
    _attack_pos_unchanged_since = 0.0

    def _restart_after_stuck():
        mpos = _get_nearest_monster_position()
        attack_path = _attackarea_path_for_slot(_my_slot)
        if mpos:
            region, x, y, z = mpos
            _write_attackarea_walk(attack_path, x, y, z)
            try:
                set_training_position(region, x, y, z)
            except Exception:
                pass
        start_bot()

    threading.Timer(STUCK_RECOVERY_DELAY, _restart_after_stuck).start()

CHECK_INTERVAL = 1.5
ATTACK_TO_NORMAL_DELAY = 5.0  # saniye
ATTACK_AREA_RADIUS = 100  # AttackArea script ile aynı (slot içi mob kontrolü)
UNIQUE_MOB_TYPE = 8  # phBot monster type: Unique
UNIQUE_KILL_WAIT_DELAY = 5.0  # Unique öldürünce drop almak için bekleme (saniye)
STUCK_DETECT_SEC = 6.0  # konum değişmezse bu süre sonra "takılı" sayılır
STUCK_MOVE_THRESHOLD = 2.0  # bu mesafeden az hareket = hareket yok
STUCK_RECOVERY_DELAY = 5.0  # geri dönüp tekrar denemek için bekleme
IGNORE_MONSTER_SUBSTR = (
    'ghost curse', 'telbasta', 'chief hyena', 'statue of eternal life',
    'mummy of arrogance', 'mummy of wrath', 'bast', 'sand hyena', 'heron',
    'bastet', 'keisas', 'mhont', 'lightning khepri', 'demon bug'
)

def _set_slot(n):
    global _my_slot
    _my_slot = int(n)
    for cb, i in [(cbP1, 1), (cbP2, 2), (cbP3, 3), (cbP4, 4), (cbP5, 5), (cbP6, 6), (cbP7, 7), (cbP8, 8)]:
        if cb:
            QtBind.setChecked(gui, cb, n == i)

def cbx_toggle_enabled(checked):
    global _pluginEnabled
    _pluginEnabled = bool(checked)
    log('[%s] AttackArea mantığı %s' % (pName, 'AÇIK' if _pluginEnabled else 'KAPALI'))

def cbx_toggle_mob_ignore(checked):
    global _mobIgnoreEnabled
    _mobIgnoreEnabled = bool(checked)
    log('[%s] Mob yoksay %s' % (pName, 'AÇIK' if _mobIgnoreEnabled else 'KAPALI'))

def _ensure_sc_folder():
    global SC_FOLDER
    if SC_FOLDER is None:
        SC_FOLDER = _get_sc_folder()
    try:
        os.makedirs(SC_FOLDER, exist_ok=True)
    except Exception as e:
        log('[%s] sc klasörü oluşturulamadı %s: %s' % (pName, SC_FOLDER, e))

def _ensure_fgw_folder():
    global FGW_FOLDER
    if FGW_FOLDER is None:
        FGW_FOLDER = _get_fgw_folder()
    try:
        os.makedirs(FGW_FOLDER, exist_ok=True)
    except Exception as e:
        log('[%s] FGW klasörü oluşturulamadı %s: %s' % (pName, FGW_FOLDER, e))

def _download_script_from_server(filename):
    """Sunucudan (api/download, type=SC) script indirir, sc/ klasörüne kaydeder. Başarılıysa path döner."""
    fn_dl = globals().get('_download_from_server')
    if not fn_dl:
        return None
    _ensure_sc_folder()
    dest = os.path.join(SC_FOLDER, filename)
    if fn_dl('SC', filename, dest):
        return dest
    return None

def _download_script_from_github(filename):
    """GitHub'dan tek script indirir, sc/ klasörüne kaydeder. Başarılıysa path döner."""
    _ensure_sc_folder()
    from urllib.parse import quote
    encoded = quote(filename, safe='')
    url = GITHUB_FGW_RAW_TEMPLATE % encoded
    dest = os.path.join(SC_FOLDER, filename)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'phBot-SROManager/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read()
        if not content or len(content) < 50:
            return None
        with open(dest, 'wb') as f:
            f.write(content)
        log('[%s] İndirildi: %s' % (pName, filename))
        return dest
    except Exception as e:
        log('[%s] İndirme hatası (%s): %s' % (pName, filename, str(e)))
        return None

def _write_empty_file(full_path):
    try:
        dirp = os.path.dirname(full_path)
        if dirp and not os.path.exists(dirp):
            os.makedirs(dirp, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('')
        return True
    except Exception as e:
        log('[%s] Boş dosya yazılamadı %s: %s' % (pName, full_path, e))
        return False

def _download_all_scripts():
    """FGW scriptlerini indirir: Gemi Enkazı 1-2/3-4 sunucudan (api/download SC), diğerleri GitHub'dan."""
    _ensure_sc_folder()
    _ensure_fgw_folder()
    count = 0

    for disp, filename, _ in FGW_SCRIPT_MAP:
        if disp in ('Gemi Enkazı 1-2★', 'Gemi Enkazı 3-4★'):
            if _download_script_from_server(filename):
                count += 1
            # if _download_script_from_github(filename): count += 1  # eski: GitHub
        else:
            if _download_script_from_github(filename):
                count += 1

    for fn in ATTACKAREA_FILENAMES:
        p = os.path.join(FGW_FOLDER, fn)
        if not os.path.exists(p):
            if _write_empty_file(p):
                count += 1

    log('[%s] %d script hazır. sc: %s | FGW: %s' % (pName, count, SC_FOLDER, FGW_FOLDER))
    create_notification('FGW: Scriptler hazır')

def _get_fgw_script_path(filename):
    """sc/ klasöründe script var mı kontrol eder. Varsa path, yoksa None."""
    _ensure_sc_folder()
    path = os.path.join(SC_FOLDER, filename)
    return path if os.path.exists(path) and os.path.getsize(path) > 50 else None

def _ensure_script_file(display_name, filename, _fallback_var=None, from_server=False):
    """
    Script dosyasının mevcut olduğundan emin olur.
    from_server=True (Gemi Enkazı): sc/'de varsa kullan, yoksa api/download SC ile sunucudan indir (GitHub yok).
    from_server=False: sc/'de arar, yoksa GitHub'dan indirir.
    """
    path = _get_fgw_script_path(filename)
    if path:
        return path
    if from_server:
        path = _download_script_from_server(filename)
        if path:
            return path
        # path = _download_script_from_github(filename)  # eski: GitHub fallback
        # if path: return path
        log('[%s] Script bulunamadı/indirilemedi (sunucu): %s' % (pName, display_name))
        return None
    path = _download_script_from_github(filename)
    if path:
        return path
    log('[%s] Script bulunamadı/indirilemedi: %s' % (pName, display_name))
    return None

def _set_training_script_from_file(display_name, filename, _fallback_var=None, from_server=False):
    """Script ayarlar. from_server=True ise Gemi Enkazı 1-2/3-4 için sunucudan indirir."""
    global _last_fgw_script_path, _current_state
    path = _ensure_script_file(display_name, filename, _fallback_var, from_server)
    if not path:
        return
    try:
        set_training_script(path)
        _last_fgw_script_path = path
        _current_state = 'fgw'
        log('[%s] Eğitim scripti ayarlandı: %s' % (pName, display_name))
        create_notification('FGW: %s' % display_name)
    except Exception as e:
        log('[%s] Script ayarlama hatası: %s' % (pName, e))

def _write_attackarea_walk(path, x, y, z):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write('walk,%d,%d,%d\n' % (int(x), int(y), int(z)))
        return True
    except Exception as e:
        log('[%s] AttackArea yazma hatası: %s' % (pName, e))
        return False

def _write_dynamic_attackarea_script():
    pos = get_position()
    if not pos:
        return None
    try:
        x, y = float(pos.get('x', 0)), float(pos.get('y', 0))
    except (TypeError, ValueError):
        x, y = 0.0, 0.0
    _ensure_fgw_folder()
    path = os.path.join(FGW_FOLDER, DYNAMIC_ATTACK_FILENAME)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write('walk,{:.0f},{:.0f}\n'.format(x, y))
            f.write('AttackArea,100\n')
        return path
    except Exception as e:
        log('[%s] Dynamic script yazılamadı: %s' % (pName, e))
        return None

def _attackarea_path_for_slot(slot):
    _ensure_fgw_folder()
    try:
        slot = max(1, min(8, int(slot)))
    except (TypeError, ValueError):
        slot = 1
    return os.path.join(FGW_FOLDER, ATTACKAREA_FILENAMES[slot - 1])

def _ensure_attackarea_files():
    _ensure_fgw_folder()
    for fn in ATTACKAREA_FILENAMES:
        p = os.path.join(FGW_FOLDER, fn)
        if not os.path.exists(p):
            _write_empty_file(p)

def _is_ignored_monster(name):
    if not name:
        return False
    ln = name.lower()
    return any(s in ln for s in IGNORE_MONSTER_SUBSTR)

def _get_valid_monsters():
    mobs = get_monsters()
    if not mobs:
        return []
    mob_ignore = QtBind.isChecked(gui, cbMobIgnore) if cbMobIgnore else _mobIgnoreEnabled
    base = [(mid, m) for mid, m in mobs.items() if m.get('name')]
    if not mob_ignore:
        return base
    return [(mid, m) for mid, m in base if not _is_ignored_monster(m.get('name', ''))]

def _get_valid_monsters_in_attack_radius():
    """Attack modunda: sadece slot/alan (ATTACK_AREA_RADIUS) içindeki mob'ları döner."""
    valid = _get_valid_monsters()
    if not valid:
        return []
    pos = get_position()
    if not pos:
        return valid
    try:
        px, py = float(pos.get('x', 0)), float(pos.get('y', 0))
        r2 = ATTACK_AREA_RADIUS * ATTACK_AREA_RADIUS
        return [(mid, m) for mid, m in valid if (float(m.get('x', 0)) - px) ** 2 + (float(m.get('y', 0)) - py) ** 2 <= r2]
    except (TypeError, ValueError):
        return valid

def _get_nearest_monster_position():
    pos = get_position()
    if not pos:
        return None
    try:
        region = int(pos.get('region', 0))
        px, py = float(pos.get('x', 0)), float(pos.get('y', 0))
    except (TypeError, ValueError):
        return None
    best, best_d2 = None, None
    for _, m in _get_valid_monsters():
        try:
            mx, my = float(m.get('x', 0)), float(m.get('y', 0))
            d2 = (mx - px) ** 2 + (my - py) ** 2
            if best_d2 is None or d2 < best_d2:
                best_d2, best = d2, (region, mx, my, 0.0)
        except (TypeError, ValueError):
            continue
    return best

def event_loop():
    global _last_check, _current_state, _last_fgw_script_path, _attack_to_normal_wait_since, _pre_attack_position
    global _last_attack_had_unique, _unique_kill_wait_until
    global _last_attack_pos, _attack_pos_unchanged_since, _last_known_moving_pos
    if not _is_license_valid() or not _pluginEnabled:
        return
    _ensure_fgw_folder()
    now = time.time()
    if _unique_kill_wait_until > 0:
        if now < _unique_kill_wait_until:
            return  # Unique öldü, drop almak için bekleniyor
        _unique_kill_wait_until = 0.0
        # Bekleme bitti, mob yoksa hemen normal scripte geç (zaten 5 sn bekledik)
        _attack_to_normal_wait_since = now - ATTACK_TO_NORMAL_DELAY
    if now - _last_check < CHECK_INTERVAL:
        return
    _last_check = now
    # Attack modunda: sadece slot içindeki (100 birim) mob'lar sayılır; normal modda tüm harita
    valid = _get_valid_monsters_in_attack_radius() if _current_state == 'attack' else _get_valid_monsters()
    has_mobs = len(valid) > 0
    had_unique = any(m.get('type') == UNIQUE_MOB_TYPE for _, m in valid)

    # Engel takılma: attack modunda mob var, konum değişmiyor VE en yakın mob uzaktaysa (saldırmıyor) -> geri dön
    if _current_state == 'attack' and has_mobs and _unique_kill_wait_until <= 0:
        pos = get_position()
        if pos:
            try:
                px, py = float(pos.get('x', 0)), float(pos.get('y', 0))
                mpos = _get_nearest_monster_position()
                nearest_d2 = 999999
                if mpos:
                    mx, my = mpos[1], mpos[2]
                    nearest_d2 = _dist2(px, py, mx, my)
                # Sadece mob uzaktaysa (saldırmıyorsa) takılı say - yakınsa melee attack olabilir
                if nearest_d2 > 30 * 30:  # 30 birimden uzak
                    if _last_attack_pos:
                        d2 = _dist2(_last_attack_pos[0], _last_attack_pos[1], px, py)
                        if d2 < STUCK_MOVE_THRESHOLD * STUCK_MOVE_THRESHOLD:
                            if _attack_pos_unchanged_since == 0:
                                _attack_pos_unchanged_since = now
                            elif now - _attack_pos_unchanged_since >= STUCK_DETECT_SEC:
                                _do_stuck_recovery()
                                return
                        else:
                            _attack_pos_unchanged_since = 0
                            _last_known_moving_pos = (int(pos.get('region', 0)), px, py, float(pos.get('z', 0)))
                    _last_attack_pos = (px, py)
            except (TypeError, ValueError):
                pass

    # Unique öldü: önceki tick'te vardı, şimdi yok -> 5 sn dur, drop al
    if _current_state == 'attack' and _last_attack_had_unique and not had_unique:
        stop_bot()
        _unique_kill_wait_until = now + UNIQUE_KILL_WAIT_DELAY
        _last_attack_had_unique = False
        log('[%s] Unique öldürüldü, %d sn drop bekleniyor...' % (pName, int(UNIQUE_KILL_WAIT_DELAY)))
        return
    _last_attack_had_unique = had_unique

    if has_mobs:
        _attack_to_normal_wait_since = 0.0  # mob varsa bekleme iptal
    if has_mobs and _current_state != 'attack':
        pos = get_position()
        if pos:
            try:
                _pre_attack_position = (
                    int(pos.get('region', 0)),
                    float(pos.get('x', 0)), float(pos.get('y', 0)), float(pos.get('z', 0))
                )
            except (TypeError, ValueError):
                _pre_attack_position = None
        stop_bot()
        attack_path = _attackarea_path_for_slot(_my_slot)
        _ensure_attackarea_files()
        try:
            set_training_script(attack_path)
        except Exception:
            pass
        mpos = _get_nearest_monster_position()
        if mpos:
            region, x, y, z = mpos
            _write_attackarea_walk(attack_path, x, y, z)
            try:
                set_training_position(region, x, y, z)
            except Exception:
                pass
        _current_state = 'attack'
        _last_attack_pos = None
        _attack_pos_unchanged_since = 0.0
        pos = get_position()
        if pos:
            try:
                _last_known_moving_pos = (int(pos.get('region', 0)), float(pos.get('x', 0)), float(pos.get('y', 0)), float(pos.get('z', 0)))
            except (TypeError, ValueError):
                _last_known_moving_pos = _pre_attack_position
        else:
            _last_known_moving_pos = _pre_attack_position
        start_bot()
        return

    if not has_mobs and _current_state == 'attack':
        if _attack_to_normal_wait_since == 0:
            _attack_to_normal_wait_since = now
        if now - _attack_to_normal_wait_since < ATTACK_TO_NORMAL_DELAY:
            return  # 5 sn bekle, sonra normal scripte geç
        _attack_to_normal_wait_since = 0.0
        stop_bot()
        if _last_fgw_script_path:
            try:
                set_training_script(_last_fgw_script_path)
            except Exception:
                pass
        if _pre_attack_position:
            try:
                region, x, y, z = _pre_attack_position
                set_training_position(region, x, y, z)
                move_to_fn = globals().get('move_to')
                move_to_region_fn = globals().get('move_to_region')
                pos = get_position()
                if pos and (move_to_fn or move_to_region_fn):
                    cur_r = int(pos.get('region', 0))
                    if cur_r == region and move_to_fn:
                        move_to_fn(x, y, z)
                    elif move_to_region_fn:
                        move_to_region_fn(region, x, y, z)
                _pre_attack_position = None
            except Exception:
                pass
        elif get_position():
            pos = get_position()
            try:
                set_training_position(int(pos.get('region', 0)), 0.0, 0.0, 0.0)
            except Exception:
                pass
        _current_state = 'fgw'
        _last_attack_had_unique = False
        _last_attack_pos = None
        _attack_pos_unchanged_since = 0.0
        start_bot()
        return

    # Unique beklemeden çıktık, hâlâ attack modunda ve mob var -> botu tekrar başlat
    if _current_state == 'attack' and has_mobs:
        start_bot()
