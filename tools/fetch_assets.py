# Downloads public-domain museum imagery from Wikimedia Commons
# into source/assets/img/ for the MUSA frontend demo.
import json, urllib.request, urllib.parse, os, sys, time

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "assets", "img")
os.makedirs(OUT, exist_ok=True)

UA = {"User-Agent": "MusaFrontendDemo/1.0 (educational demo; contact: local)"}

# (filename, search query, desired width)
WANTS = [
    ("hero-museum-hall.jpg",  "Louvre museum gallery interior ceiling", 1920),
    ("art-pearl-earring.jpg", "Girl with a Pearl Earring Vermeer", 1200),
    ("art-vangogh-self.jpg",  "Vincent van Gogh Self-Portrait 1889", 1200),
    ("art-milkmaid.jpg",      "Vermeer The Milkmaid", 1200),
    ("art-night-watch.jpg",   "Rembrandt The Night Watch", 1600),
    ("art-water-lilies.jpg",  "Monet Water Lilies", 1200),
    ("art-nefertiti.jpg",     "Bust of Nefertiti", 1200),
    ("art-winged-victory.jpg","Winged Victory of Samothrace", 1200),
    ("art-greek-amphora.jpg", "ancient Greek amphora black figure museum", 1200),
    ("art-egyptian-statue.jpg","ancient Egyptian statue museum", 1200),
    ("film-metropolis.jpg",   "Metropolis 1927 film poster", 900),
    ("film-nosferatu.jpg",    "Nosferatu 1922 film poster", 900),
    ("film-modern-times.jpg", "Modern Times 1936 film poster", 900),
    ("twin-wall.jpg",         "museum gallery wall paintings interior", 1600),
]

def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def pick_title(query):
    data = api({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f'filetype:bitmap {query}', "gsrnamespace": 6, "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600,
    })
    pages = (data.get("query") or {}).get("pages", {})
    best, best_score = None, -1
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        w, h = ii.get("width", 0), ii.get("height", 0)
        if w < 800 or h < 500:
            continue
        score = min(w, 4000) + min(h, 3000)
        em = ii.get("extmetadata", {})
        lic = (em.get("LicenseShortName", {}) or {}).get("value", "")
        if any(k in lic for k in ("Public domain", "CC0", "CC BY", "CC-BY", "CC0 1.0")):
            score += 100000
        if score > best_score:
            best, best_score = ii.get("thumburl") or ii.get("url"), score
    return best

def download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())

failed = []
for fname, query, w in WANTS:
    dest = os.path.join(OUT, fname)
    if os.path.exists(dest) and os.path.getsize(dest) > 20000:
        print("skip", fname); continue
    try:
        url = pick_title(query)
        if not url:
            raise RuntimeError("no result")
        download(url, dest)
        print("ok  ", fname, os.path.getsize(dest) // 1024, "KB")
        time.sleep(0.4)
    except Exception as e:
        failed.append((fname, query, str(e)))
        print("FAIL", fname, e)

print("\nFAILED:", len(failed))
for f in failed: print("  ", f)
