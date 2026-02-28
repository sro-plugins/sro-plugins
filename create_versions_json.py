# -*- coding: utf-8 -*-
"""files/jsons/versions.json oluşturur - garden + caravan scriptleri versiyonlar."""
import os
import json
import hashlib

def main():
    out = {}
    # Garden (SC)
    for f in ['garden-dungeon.txt', 'garden-dungeon-wizz-cleric.txt']:
        path = os.path.join('files', 'sc', f)
        if os.path.exists(path):
            with open(path, 'rb') as fp:
                h = hashlib.sha256(fp.read()).hexdigest()
            out[f] = {'version': '3.0', 'sha256': h}
        else:
            out[f] = {'version': '3.0', 'sha256': ''}
    # Caravan
    caravan_dir = os.path.join('files', 'caravan')
    if os.path.exists(caravan_dir):
        for f in sorted(os.listdir(caravan_dir)):
            if f.endswith('.txt'):
                path = os.path.join(caravan_dir, f)
                with open(path, 'rb') as fp:
                    h = hashlib.sha256(fp.read()).hexdigest()
                out[f] = {'version': '1.0', 'sha256': h}
    os.makedirs('files/jsons', exist_ok=True)
    with open('files/jsons/versions.json', 'w', encoding='utf-8') as w:
        json.dump(out, w, indent=2, ensure_ascii=False)
    print('files/jsons/versions.json olusturuldu (%d script)' % len(out))

if __name__ == '__main__':
    main()
