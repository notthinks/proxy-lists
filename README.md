# Proxy Lists — Auto-Updated Hourly

📡 **Free proxy list**, dipindai otomatis **setiap jam** via GitHub Actions.

## Isi Repo

| File | Isi |
|---|---|
| `alive.txt` | 🔥 **Proxy AKTIF** (HTTP/SOCKS5 verified, IP:PORT) — utama |
| `tokenharbor.txt` | Proxy yang bisa membuka tokenharbor.ai (bonus) |
| `history/` | Arsip hasil per jam (format YYYYMMDD_HHMMSS) |
| `scanner.py` | Script scanner (26+ sumber) |

## Sumber Provider (26+)

- **GeoNode** API (proxylist.geonode.com) — http & socks5
- **Proxyscrape** API — http, socks4, socks5
- **GitHub lists**: TheSpeedX, monosans, mmpx12, clarketm, proxifly, jetkai, shiftytr, roosterkid, HookzAG
- **Proxy-List.Download** API — http, https, socks4, socks5
- **OpenProxy.Space**

## Cara Pakai

```bash
# download proxy aktif terbaru
curl -O https://raw.githubusercontent.com/notthinks/proxy-lists/main/alive.txt

# jalankan scanner manual
pip install requests
python scanner.py --target tokenharbor
```

## Update

Workflow `.github/workflows/scan.yml` jalan tiap jam (UTC). `alive.txt` selalu list proxy terverifikasi hidup di jam itu.