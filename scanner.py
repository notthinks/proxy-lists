#!/usr/bin/env python3
"""Proxy Scanner — scrape fresh lists -> alive -> (optional) target screening.

Usage:
  python3 proxy_scanner.py [--target tokenharbor|blackbox|outlook] [--min-hits N]

Output (timestamped) in output/:
  proxies_alive_<TS>.txt              — proxy hidup (semua protokol)
  proxies_<target>_<TS>.txt           — proxy yang bisa buka target (kalau --target)
  latest.txt / latest_<target>.txt    — symlink-style pointer untuk cron pickup
"""
import argparse, concurrent.futures, glob, os, time
import requests
import re

TARGETS = {
    "tokenharbor": {"url": "https://tokenharbor.ai", "marks": ["token harbor", "harbor", "one api"]},
    "blackbox":    {"url": "https://app.blackbox.ai", "marks": ["blackbox", "sign in", "start building"]},
    "outlook":     {"url": "https://signup.live.com", "marks": ["signup", "create account", "microsoft account"]},
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
HDRS = {"User-Agent": UA}

SOURCES = [
    # Proxyscrape API
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=8000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=8000&country=all&ssl=all&anonymity=all",
    # GitHub raw lists
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
    "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/HookzAG/socks-proxy-list/main/socks5.txt",
    # API lain
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://www.proxy-list.download/api/v1/get?type=socks4",
    "https://www.proxy-list.download/api/v1/get?type=socks5",
    "https://openproxy.space/list/http",
    "https://openproxy.space/list/socks5",
]

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def fetch_sources():
    raw = []
    for url in SOURCES:
        try:
            r = requests.get(url, timeout=20, headers=HDRS)
            if r.status_code == 200:
                raw.append(r.text)
        except Exception:
            pass
    return "\n".join(raw)


def fetch_geonode():
    """GeoNode free proxy list API (update tiap menit, tanpa API key)."""
    lines = []
    for proto in ("http", "socks5"):
        for page in (1, 2, 3):
            try:
                r = requests.get(
                    f"https://proxylist.geonode.com/api/proxy-list?limit=500&page={page}"
                    f"&sort_by=lastChecked&sort_type=desc&protocols={proto}",
                    timeout=20, headers=HDRS)
                for p in r.json().get("data", []):
                    ip, port = p.get("ip"), p.get("port")
                    if ip and port:
                        lines.append(f"{proto}://{ip}:{port}")
            except Exception:
                pass
    return "\n".join(lines)


def parse(raw):
    seen, out = set(), []
    for line in raw.splitlines():
        p = line.strip().replace("\r", "")
        if not p or ":" not in p:
            continue
        if "://" in p:
            proto, hp = p.split("://", 1)
        else:
            proto, hp = "http", p
        hp = hp.strip()
        if not re.match(r"^[\w.\-]+:\d{2,5}$", hp):
            continue
        if hp in seen:
            continue
        seen.add(hp)
        out.append((hp, proto))
    return out


def alive(hp, proto):
    px = f"{proto}://{hp}"
    try:
        r = requests.get("https://ipinfo.io/json", proxies={"https": px, "http": px}, timeout=6, headers=HDRS)
        if r.status_code == 200:
            return px
    except Exception:
        pass
    return None


def target_ok(px, target):
    cfg = TARGETS[target]
    try:
        r = requests.get(cfg["url"], proxies={"https": px, "http": px}, timeout=10,
                         headers=HDRS, allow_redirects=True)
        if r.status_code == 200:
            low = r.text.lower()
            if any(m in low for m in cfg["marks"]):
                return px
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=list(TARGETS) + ["none"], default="none")
    ap.add_argument("--alive-workers", type=int, default=60)
    ap.add_argument("--target-workers", type=int, default=25)
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    TS = time.strftime("%Y%m%d_%H%M%S")
    t0 = time.time()

    print(f"[*] Scrape fresh proxies...", flush=True)
    raw = fetch_sources()
    raw += "\n" + fetch_geonode()
    pool = parse(raw)
    print(f"[*] {len(pool)} proxy unik ({time.time()-t0:.0f}s)", flush=True)

    alive_list = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.alive_workers) as ex:
        futs = {ex.submit(alive, h, p): (h, p) for h, p in pool}
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            r = f.result()
            if r:
                alive_list.append(r)
            if i % 2000 == 0:
                print(f"    [alive] {i}/{len(pool)}, hidup={len(alive_list)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"[*] HIDUP: {len(alive_list)}", flush=True)

    alive_path = os.path.join(OUTDIR, f"proxies_alive_{TS}.txt")
    with open(alive_path, "w") as f:
        f.write("\n".join(alive_list) + "\n")
    with open(os.path.join(OUTDIR, "latest.txt"), "w") as f:
        f.write("\n".join(alive_list) + "\n")

    target_path = None
    if args.target != "none":
        tl = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.target_workers) as ex:
            futs = {ex.submit(target_ok, px, args.target): px for px in alive_list}
            for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
                r = f.result()
                if r:
                    tl.append(r)
                    print("    LOLOS:", r, flush=True)
        print(f"[*] TARGET {args.target}: {len(tl)}", flush=True)
        target_path = os.path.join(OUTDIR, f"proxies_{args.target}_{TS}.txt")
        with open(target_path, "w") as f:
            f.write("\n".join(tl) + "\n")
        with open(os.path.join(OUTDIR, f"latest_{args.target}.txt"), "w") as f:
            f.write("\n".join(tl) + "\n")

    print(f"=== SELESAI {time.time()-t0:.0f}s ===", flush=True)
    print(f"ALIVE_FILE={alive_path} total={len(alive_list)}", flush=True)
    if target_path:
        print(f"TARGET_FILE={target_path} total={len(target_path and tl)}", flush=True)


if __name__ == "__main__":
    main()