# -*- coding: utf-8 -*-
# Auto Hwt (Tab 4) - SROMaster FGW & HWT mantığı, UI sromanager'da.
# Enjekte: gui, QtBind, log, pName, get_config_dir, get_config_path, get_position, get_monsters,
# set_training_script, set_training_position, start_bot, stop_bot,
# create_notification, get_training_script, time, os, json, threading, _is_license_valid,
# cbEnabled, cbP1..cbP8

# FGW klasörü: Config/SROManager/FGW_<PC>/ - Her bilgisayar kendi klasörünü kullanır (2+ PC çakışması önlenir)
def _get_pc_id():
    """Bilgisayar adı - 2 PC'de aynı config kullanılırsa her biri kendi FGW klasörüne yazar."""
    try:
        return os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'PC1'))
    except Exception:
        return 'PC1'

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


# ______________________________ Config Sync (sc/ klasörüne kayıt, 5x5 sn retry) ______________________________ #
CONFIG_SYNC_RETRY_COUNT = 5
CONFIG_SYNC_RETRY_DELAY = 5.0

def _get_sc_sync_folder():
    """Plugin sc/ klasörü yolu (sromanager ile aynı seviye)."""
    try:
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(plugin_dir, 'sc')
    except Exception:
        return None

CONFIG_SYNC_FILENAME = 'sync_config.json'

def _get_sc_sync_file_path():
    """sc/sync_config.json dosya yolu - parti ID yok, tek dosya."""
    folder = _get_sc_sync_folder()
    if not folder:
        return None
    return os.path.join(folder, CONFIG_SYNC_FILENAME)

def config_sync_read_with_retry():
    """
    sc/ klasöründen sync config'i okur. Bulamazsa 5 sn arayla toplam 5 deneme.
    Başarılı: (cfg_dict, True), Hata: (None, False) + log
    """
    path = _get_sc_sync_file_path()
    if not path:
        log('[%s] [Config Sync] sc klasörü bulunamadı.' % pName)
        return (None, False)
    for attempt in range(1, CONFIG_SYNC_RETRY_COUNT + 1):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if attempt > 1:
                    log('[%s] [Config Sync] Config bulundu (%d. deneme): %s' % (pName, attempt, path))
                return (cfg, True)
        except Exception as e:
            log('[%s] [Config Sync] Okuma hatası (%d. deneme): %s' % (pName, attempt, e))
        if attempt < CONFIG_SYNC_RETRY_COUNT:
            log('[%s] [Config Sync] Config bulunamadı, %d sn sonra tekrar deneniyor (%d/%d)...' % (
                pName, int(CONFIG_SYNC_RETRY_DELAY), attempt, CONFIG_SYNC_RETRY_COUNT))
            time.sleep(CONFIG_SYNC_RETRY_DELAY)
    log('[%s] [Config Sync] HATA: Config %d denemeden sonra bulunamadı: %s' % (pName, CONFIG_SYNC_RETRY_COUNT, path))
    log('[%s] [Config Sync] 1. PC\'de "Yükle" yapıldığından emin olun. sc/ klasörü paylaşılıyor olmalı.' % pName)
    return (None, False)

def _remap_config_paths_for_this_pc(cfg):
    """
    Config içindeki FGW ve diğer PC'ye özel path'leri bu PC'ye uyarlar.
    Böylece 1. PC'den indirilen config 2. PC'de doğru path'lerle çalışır.
    """
    if not cfg or not isinstance(cfg, dict):
        return cfg
    current_fgw = _get_fgw_folder()
    current_pc = _get_pc_id()
    # Loop.Script altındaki Path alanları
    loop = cfg.get('Loop')
    if isinstance(loop, dict):
        script_cfg = loop.get('Script')
        if isinstance(script_cfg, dict):
            for area_name, area_data in list(script_cfg.items()):
                if not isinstance(area_data, dict):
                    continue
                path_val = area_data.get('Path')
                if path_val and isinstance(path_val, str) and 'FGW_' in path_val:
                    # Sadece FGW dosya adını al, mevcut FGW klasörüne bağla
                    fname = path_val.replace('/', os.sep).split(os.sep)[-1]
                    area_data['Path'] = current_fgw + fname
        # SkipTownScript vb. path içerebilir
        for key in ('SkipTownScript', 'SkipTown', 'NoTownScript'):
            val = loop.get(key)
            if isinstance(val, dict) and val.get('Path'):
                p = val['Path']
                if p and 'FGW_' in p:
                    fname = p.replace('/', os.sep).split(os.sep)[-1]
                    val['Path'] = current_fgw + fname
    # FGW_XXX pattern'ini her yerde değiştir (nested dict'lerde)
    def _remap_recursive(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'Path' and isinstance(v, str) and 'FGW_' in v:
                    fname = v.replace('/', os.sep).split(os.sep)[-1]
                    obj[k] = current_fgw + fname
                else:
                    _remap_recursive(v)
        elif isinstance(obj, list):
            for i, x in enumerate(obj):
                _remap_recursive(x)
    _remap_recursive(cfg)
    return cfg

def config_sync_upload():
    """
    Mevcut config'i sc/ klasörüne yükler. 1. PC'de çalıştırılır.
    Dosya: sc/sync_config.json
    """
    cfg_path = get_config_path()
    if not cfg_path or not os.path.exists(cfg_path):
        log('[%s] [Config Sync] Config dosyası bulunamadı. Oyuna giriş yapıp tekrar deneyin.' % pName)
        return False
    sc_folder = _get_sc_sync_folder()
    if not sc_folder:
        log('[%s] [Config Sync] sc klasörü bulunamadı.' % pName)
        return False
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['_sync_meta'] = {
            'source_pc': _get_pc_id(),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        if not os.path.isdir(sc_folder):
            os.makedirs(sc_folder, exist_ok=True)
            log('[%s] [Config Sync] sc klasörü oluşturuldu: %s' % (pName, sc_folder))
        out_path = _get_sc_sync_file_path()
        with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        log('[%s] [Config Sync] Config sc/ klasörüne yüklendi: %s' % (pName, out_path))
        return True
    except Exception as e:
        log('[%s] [Config Sync] Upload hatası: %s' % (pName, e))
        return False

def _config_sync_download_worker():
    """Thread'de çalışır; UI bloke olmaz."""
    cfg, ok = config_sync_read_with_retry()
    if not ok or not cfg:
        return
    cfg_path = get_config_path()
    if not cfg_path:
        log('[%s] [Config Sync] Config yolu alınamadı. Oyuna giriş yapıp tekrar deneyin.' % pName)
        return
    try:
        meta = cfg.pop('_sync_meta', {})
        log('[%s] [Config Sync] Kaynak: %s, Zaman: %s' % (pName, meta.get('source_pc', '?'), meta.get('timestamp', '?')))
        cfg = _remap_config_paths_for_this_pc(cfg)
        with open(cfg_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        log('[%s] [Config Sync] Config indirildi ve uygulandı. Path\'ler bu PC\'ye uyarlandı.' % pName)
        log('[%s] [Config Sync] Gerekirse "Scriptleri İndir" ile FGW scriptlerini oluşturun, ardından Bot Başlat.' % pName)
    except Exception as e:
        log('[%s] [Config Sync] Download hatası: %s' % (pName, e))

def config_sync_download():
    """
    sc/ klasöründen config indirir (5 sn arayla 5 deneme, thread'de). 2. PC'de çalıştırılır.
    """
    t = threading.Thread(target=_config_sync_download_worker, daemon=True)
    t.start()
    log('[%s] [Config Sync] İndirme başlatıldı (arka planda, 5 sn arayla 5 deneme).' % pName)
