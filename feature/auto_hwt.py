# -*- coding: utf-8 -*-
# Auto Hwt (Tab 4) - SROMaster FGW & HWT mantığı, UI sromanager'da.
# Scriptler: GitHub sc/ klasöründen indirilir (İndir butonu) veya yerel sc/ kullanılır.
# Attack Area 1-8: Config/SROManager/FGW_<PC>/ - Her PC kendi klasörüne yazar (4 PC çakışmasız).
# Enjekte: gui, QtBind, log, pName, get_config_dir, plugin_dir, urllib,
# GITHUB_FGW_RAW_TEMPLATE, GITHUB_FGW_SCRIPT_FILENAMES,
# get_position, get_monsters, set_training_script, set_training_position, start_bot, stop_bot,
# create_notification, get_training_script, time, os, _is_license_valid, cbEnabled, cbP1..cbP8

def _get_pc_id():
    """Bilgisayar adı - 4 PC'de her biri kendi FGW klasörüne yazar."""
    try:
        return os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'PC1'))
    except Exception:
        return 'PC1'

def _get_sc_folder():
    """Script klasörü: plugin_dir/sc/ - GitHub ile senkron, sabit path yok."""
    return os.path.join(plugin_dir, 'sc')

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
CHECK_INTERVAL = 1.5
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
    """GitHub'dan FGW scriptlerini sc/'ye indirir; Attack Area dosyalarını FGW_<PC>/'ye oluşturur."""
    _ensure_sc_folder()
    _ensure_fgw_folder()
    count = 0

    for disp, filename, _ in FGW_SCRIPT_MAP:
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

def _ensure_script_file(display_name, filename, _fallback_var=None):
    """
    Script dosyasının mevcut olduğundan emin olur. Önce sc/'de arar, yoksa GitHub'dan indirir.
    Fallback: GitHub başarısızsa gömülü içerik kullanılabilir (opsiyonel).
    """
    path = _get_fgw_script_path(filename)
    if path:
        return path
    path = _download_script_from_github(filename)
    if path:
        return path
    log('[%s] Script bulunamadı/indirilemedi: %s' % (pName, display_name))
    return None

def _set_training_script_from_file(display_name, filename, _fallback_var=None):
    global _last_fgw_script_path, _current_state
    path = _ensure_script_file(display_name, filename, _fallback_var)
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
    return [(mid, m) for mid, m in mobs.items() if m.get('name') and not _is_ignored_monster(m.get('name', ''))]

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
    global _last_check, _current_state, _last_fgw_script_path
    if not _is_license_valid() or not _pluginEnabled:
        return
    _ensure_fgw_folder()
    now = time.time()
    if now - _last_check < CHECK_INTERVAL:
        return
    _last_check = now
    valid = _get_valid_monsters()
    has_mobs = len(valid) > 0

    if has_mobs and _current_state != 'attack':
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
        start_bot()
        return

    if not has_mobs and _current_state == 'attack':
        stop_bot()
        if _last_fgw_script_path:
            try:
                set_training_script(_last_fgw_script_path)
            except Exception:
                pass
        pos = get_position()
        if pos:
            try:
                set_training_position(int(pos.get('region', 0)), 0.0, 0.0, 0.0)
            except Exception:
                pass
        _current_state = 'fgw'
        start_bot()
