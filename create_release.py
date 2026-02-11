import urllib.request
import json
import os
import sys

# GitHub repo bilgileri
GITHUB_REPO = 'sro-plugins/sro-plugins'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

if not GITHUB_TOKEN:
    print("GITHUB_TOKEN environment variable bulunamadi!")
    print("GitHub Personal Access Token olusturun ve GITHUB_TOKEN olarak ayarlayin.")
    print("Veya manuel olarak release olusturun:")
    print("https://github.com/sro-plugins/sro-plugins/releases/new")
    sys.exit(1)

# Release notlarını oku
with open('release-notes.md', 'r', encoding='utf-8') as f:
    release_notes = f.read()

# Release oluştur
release_data = {
    'tag_name': 'v1.6.0',
    'name': 'v1.6.0 - Script-Command tab, TargetSupport, Sıralı Bless',
    'body': release_notes,
    'draft': False,
    'prerelease': False
}

url = f'https://api.github.com/repos/{GITHUB_REPO}/releases'
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'phBot-Santa-So-Ok-Plugin/1.0'
}

req = urllib.request.Request(
    url,
    data=json.dumps(release_data).encode('utf-8'),
    headers=headers,
    method='POST'
)

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(f"Release başarıyla oluşturuldu!")
        print(f"URL: {result['html_url']}")
        
        # Asset yükleme URL'i
        upload_url = result['upload_url'].replace('{?name,label}', '')
        print(f"\nŞimdi Santa-So-Ok-DaRKWoLVeS.py dosyasını asset olarak yüklüyoruz...")
        
        # Dosyayı yükle
        with open('Santa-So-Ok-DaRKWoLVeS.py', 'rb') as f:
            file_data = f.read()
        
        upload_headers = headers.copy()
        upload_headers['Content-Type'] = 'application/octet-stream'
        
        upload_req = urllib.request.Request(
            upload_url + '?name=Santa-So-Ok-DaRKWoLVeS.py',
            data=file_data,
            headers=upload_headers,
            method='POST'
        )
        
        with urllib.request.urlopen(upload_req) as upload_response:
            print("Asset başarıyla yüklendi!")
            
except urllib.error.HTTPError as e:
    print(f"Hata: {e.code}")
    print(e.read().decode('utf-8'))
    sys.exit(1)
