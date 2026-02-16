# -*- coding: utf-8 -*-
# Auto Hwt (Tab 4) - SROMaster FGW & HWT mantığı, UI sromanager'da.
# Enjekte: gui, QtBind, log, pName, get_config_dir, get_config_path, get_position, get_monsters,
# get_training_area, set_training_area, set_training_script, set_training_position, set_training_radius,
# start_bot, stop_bot, create_notification, get_training_script, time, os, json, _is_license_valid,
# cbEnabled, cbP1..cbP8, cbPC1..cbPC4

# FGW klasörü: Config/SROManager/FGW_<PC>/ - Bilgisayar No ile 2+ PC çakışması önlenir
def _get_pc_id_file():
    """PC No kayıt dosyası - yerel AppData (sync edilmez, her PC kendi değerini tutar)."""
    try:
        base = os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', ''))
        if base:
            d = os.path.join(base, 'SROManager')
            os.makedirs(d, exist_ok=True)
            return os.path.join(d, 'hwt_pc_id.txt')
    except Exception:
        pass
    return None

def _get_pc_id():
    """Önce yerel dosyadan, yoksa UI'dan, yoksa 1."""
    try:
        pf = _get_pc_id_file()
        if pf and os.path.exists(pf):
            with open(pf, 'r', encoding='utf-8') as f:
                v = f.read().strip()
            if v in ('1', '2', '3', '4'):
                return v
        for cb, n in [(cbPC1, 1), (cbPC2, 2), (cbPC3, 3), (cbPC4, 4)]:
            if cb and QtBind.isChecked(gui, cb):
                v = str(n)
                pf2 = _get_pc_id_file()
                if pf2:
                    try:
                        with open(pf2, 'w', encoding='utf-8') as f:
                            f.write(v)
                    except Exception:
                        pass
                return v
    except Exception:
        pass
    return '1'

def _set_pc_id(n):
    """Bilgisayar No checkbox değiştiğinde - tek seçim ve dosyaya kaydet."""
    global FGW_FOLDER
    n = max(1, min(4, int(n)))
    for cb, i in [(cbPC1, 1), (cbPC2, 2), (cbPC3, 3), (cbPC4, 4)]:
        if cb:
            QtBind.setChecked(gui, cb, n == i)
    pf = _get_pc_id_file()
    if pf:
        try:
            with open(pf, 'w', encoding='utf-8') as f:
                f.write(str(n))
            FGW_FOLDER = None
            log('[%s] Bilgisayar No: %d' % (pName, n))
        except Exception:
            pass

def _get_fgw_folder():
    cfg = get_config_dir()
    pc_id = _get_pc_id()
    if cfg:
        base = cfg.rstrip('/\\') + os.sep + pName
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return base + os.sep + 'FGW_' + pc_id + os.sep

FGW_FOLDER = None  # init below
ATTACKAREA_FILENAMES = [
    "FGW Attack Area1.txt", "FGW Attack Area2.txt", "FGW Attack Area3.txt", "FGW Attack Area4.txt",
    "FGW Attack Area5.txt", "FGW Attack Area6.txt", "FGW Attack Area7.txt", "FGW Attack Area8.txt",
]
ATTACKAREA_FILENAME = ATTACKAREA_FILENAMES[0]
DYNAMIC_ATTACK_FILENAME = "FGW_DYNAMIC_ATTACKAREA.txt"

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

# Script sabitleri: SROMaster/auto_hwt_scripts dosyasından metin olarak parse et
def _parse_script_file(path):
    """Dosyadan SCRIPT_X = \"\"\"...\"\"\" bloklarını parse eder."""
    out = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            s = f.read()
    except Exception:
        return out
    i = 0
    while True:
        beg = s.find('SCRIPT_', i)
        if beg < 0:
            break
        eq = s.find('=', beg)
        if eq < 0 or eq - beg > 30:
            i = beg + 1
            continue
        tq = s.find('"""', eq + 1)
        if tq < 0:
            i = beg + 1
            continue
        name = s[beg:eq].strip().rstrip('= ')
        end = s.find('"""', tq + 3)
        if end < 0:
            break
        content = s[tq + 3:end].strip()
        if name.startswith('SCRIPT_') and content and len(content) > 10:
            out[name] = content
        i = end + 3
    return out

def _load_scripts():
    base = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(base)
    paths = [
        os.path.join(base, 'auto_hwt_scripts.py'),
        os.path.join(parent, 'feature', 'auto_hwt_scripts.py'),
        r'C:\Users\Burakcan\Downloads\SROCAVE OTO FGW HWT 2026 (1)\SROMaster FGW & HWT.py',
    ]
    for p in paths:
        if os.path.exists(p):
            r = _parse_script_file(p)
            if r:
                return r
    return {}

SCRIPT_TOGUI = "walk,0,0,0\n"
SCRIPT_SHIP12 = "walk,0,0,0\n"
SCRIPT_SHIP34 = "walk,0,0,0\n"
SCRIPT_FLAME = "walk,0,0,0\n"
SCRIPT_HWT_BEGINNER = "walk,0,0,0\nteleport,Pharaoh tomb (beginner),Kings Valley\ninject,0x7061,00\n"
SCRIPT_HWT_INTERMEDIATE = "walk,0,0,0\nteleport,Pharaoh tomb (intermediate),Kings Valley\ninject,0x7061,00\n"
SCRIPT_HWT_ADVANCED = "walk,0,0,0\nteleport,Pharaoh tomb (advance),Kings Valley\ninject,0x7061,00\n"
for k, v in _load_scripts().items():
    if v and len(v) > 20:
        globals()[k] = v

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

def _ensure_fgw_folder():
    global FGW_FOLDER
    if FGW_FOLDER is None:
        FGW_FOLDER = _get_fgw_folder()
    try:
        os.makedirs(FGW_FOLDER, exist_ok=True)
    except Exception as e:
        log('[%s] Klasör oluşturulamadı %s: %s' % (pName, FGW_FOLDER, e))

def _save_script_to_file(display_name, filename, content):
    if not content or not content.strip():
        log('[%s] Script boş: %s' % (pName, display_name))
        return None
    _ensure_fgw_folder()
    path = os.path.join(FGW_FOLDER, filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content.strip() + '\n')
        log('[%s] Kaydedildi: %s' % (pName, path))
        return path
    except Exception as e:
        log('[%s] Yazma hatası %s: %s' % (pName, path, e))
        return None

def _write_empty_file(full_path):
    try:
        _ensure_fgw_folder()
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('')
        return True
    except Exception as e:
        log('[%s] Boş dosya yazılamadı %s: %s' % (pName, full_path, e))
        return False

def _ensure_attackarea_files():
    _ensure_fgw_folder()
    for fn in ATTACKAREA_FILENAMES:
        p = os.path.join(FGW_FOLDER, fn)
        if not os.path.exists(p):
            _write_empty_file(p)

def _download_all_scripts():
    _ensure_fgw_folder()
    count = 0
    maps = [
        ('Togui Köyü', 'Togui Village Forgotten World.txt', 'SCRIPT_TOGUI'),
        ('Gemi Enkazı 1-2★', 'Ship Wreck 1-2 Stars Forgotten World.txt', 'SCRIPT_SHIP12'),
        ('Gemi Enkazı 3-4★', 'Ship Wreck 3-4 Stars Forgotten World.txt', 'SCRIPT_SHIP34'),
        ('Alev Dağı', 'Flame Mountain Forgotten World.txt', 'SCRIPT_FLAME'),
        ('HWT Başlangıç', 'Holy Water Temple Beginner.txt', 'SCRIPT_HWT_BEGINNER'),
        ('HWT Orta', 'Holy Water Temple Intermediate.txt', 'SCRIPT_HWT_INTERMEDIATE'),
        ('HWT İleri', 'Holy Water Temple Advanced.txt', 'SCRIPT_HWT_ADVANCED'),
    ]
    for disp, fname, var in maps:
        c = globals().get(var, '')
        if c and _save_script_to_file(disp, fname, c):
            count += 1
    _ensure_attackarea_files()
    for fn in ATTACKAREA_FILENAMES:
        if _write_empty_file(os.path.join(FGW_FOLDER, fn)):
            count += 1
    log('[%s] %d script indirildi: %s' % (pName, count, FGW_FOLDER))

def _ensure_script_file(display_name, filename, script_var_name):
    _ensure_fgw_folder()
    path = os.path.join(FGW_FOLDER, filename)
    if os.path.exists(path):
        return path
    content = globals().get(script_var_name, '')
    if not content or not content.strip():
        log('[%s] Gömülü script yok: %s' % (pName, script_var_name))
        return None
    return _save_script_to_file(display_name, filename, content)

def _set_training_script_from_file(display_name, filename, script_var_name):
    global _last_fgw_script_path, _current_state
    path = _ensure_script_file(display_name, filename, script_var_name)
    if not path:
        return
    try:
        pos = get_position()
        if pos:
            try:
                region = int(pos.get('region', 0))
                x = float(pos.get('x', 0))
                y = float(pos.get('y', 0))
                z = float(pos.get('z', 0))
                _ensure_training_area(region, x, y, z, path)
                set_training_script(path)
                set_training_position(region, x, y, z)
                set_training_radius(100.0)
            except Exception:
                pass
        else:
            set_training_script(path)
        _last_fgw_script_path = path
        _current_state = 'fgw'
        log('[%s] Eğitim scripti ayarlandı: %s' % (pName, display_name))
        create_notification('FGW: %s' % display_name)
    except Exception as e:
        log('[%s] Script ayarlama hatası: %s' % (pName, e))

def _write_attackarea_walk(path, x, y, z):
    """walk + AttackArea - karakter konumunda saldırı."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write('walk,%d,%d,%d\n' % (int(x), int(y), int(z)))
            f.write('AttackArea,100\n')
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

def _ensure_training_area(region, x, y, z, script_path):
    """Aktif kasılma alanı yoksa config'den seç veya FGW ekle. phBot sadece aktif alana script atar."""
    if get_training_area():
        return True
    cfg_path = get_config_path()
    if cfg_path and os.path.exists(cfg_path):
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            script_cfg = (cfg.get('Loop') or {}).get('Script') or {}
            if isinstance(script_cfg, dict):
                for name in list(script_cfg.keys()):
                    if name and set_training_area(name):
                        log('[%s] Kasılma alanı seçildi: %s' % (pName, name))
                        return True
        except Exception:
            pass
    if not cfg_path or not os.path.exists(cfg_path):
        return False
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
        abspath = os.path.abspath(script_path).replace('/', '\\')
        fgw_area = {
            'Data': [], 'Enabled': True, 'Path': abspath,
            'Pick Radius': 50, 'Polygon': [], 'Radius': 100.0,
            'Region': int(region), 'Type': 0,
            'X': float(x), 'Y': float(y), 'Z': float(z),
        }
        for name in list(script_cfg.keys()):
            if isinstance(script_cfg.get(name), dict):
                script_cfg[name]['Enabled'] = False
        script_cfg['FGW'] = fgw_area
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        if set_training_area('FGW'):
            log('[%s] Config\'e FGW kasılma alanı eklendi.' % pName)
            return True
    except Exception as ex:
        log('[%s] FGW kasılma alanı eklenemedi: %s' % (pName, str(ex)))
    return False

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
        pos = get_position()
        if pos:
            try:
                region = int(pos.get('region', 0))
                x = float(pos.get('x', 0))
                y = float(pos.get('y', 0))
                z = float(pos.get('z', 0))
                _write_attackarea_walk(attack_path, x, y, z)
                _ensure_training_area(region, x, y, z, attack_path)
                set_training_script(attack_path)
                set_training_position(region, x, y, z)
                set_training_radius(100.0)
            except Exception:
                pass
        else:
            try:
                set_training_script(attack_path)
            except Exception:
                pass
        _current_state = 'attack'
        time.sleep(0.2)
        start_bot()
        return
    if not has_mobs and _current_state == 'attack':
        stop_bot()
        pos = get_position()
        if pos and _last_fgw_script_path:
            try:
                region = int(pos.get('region', 0))
                x = float(pos.get('x', 0))
                y = float(pos.get('y', 0))
                z = float(pos.get('z', 0))
                _ensure_training_area(region, x, y, z, _last_fgw_script_path)
                set_training_script(_last_fgw_script_path)
                set_training_position(region, x, y, z)
                set_training_radius(100.0)
            except Exception:
                pass
        elif _last_fgw_script_path:
            try:
                set_training_script(_last_fgw_script_path)
            except Exception:
                pass
        _current_state = 'fgw'
        time.sleep(0.2)
        start_bot()

# Init: kayıtlı Bilgisayar No'yu checkbox'lara uygula
try:
    pf = _get_pc_id_file()
    if pf and os.path.exists(pf):
        with open(pf, 'r', encoding='utf-8') as f:
            v = f.read().strip()
        if v in ('1', '2', '3', '4'):
            n = int(v)
            for cb, i in [(cbPC1, 1), (cbPC2, 2), (cbPC3, 3), (cbPC4, 4)]:
                if cb:
                    QtBind.setChecked(gui, cb, n == i)
except Exception:
    pass
