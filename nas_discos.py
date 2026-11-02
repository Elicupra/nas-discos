#!/usr/bin/env python3
"""
nas_discos.py - Buscador de discos duros NAS (4-20 TB) en tiendas españolas.

Uso:
  pip install requests beautifulsoup4 playwright && playwright install chromium
  python nas_discos.py              # servidor en http://localhost:8765 (con botón de rebúsqueda)
  python nas_discos.py --once       # busca una vez y escribe nas_discos.html (estático)
  python nas_discos.py --demo       # datos de ejemplo, sin tocar internet (para probar la UI)
  python nas_discos.py --debug      # muestra qué extrae de cada página
  python nas_discos.py --headed     # navegador visible (si PcComponentes pide captcha, resuélvelo ahí)
"""
import argparse, json, random, re, statistics, sys, threading, time, webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ───────────── CONFIGURACIÓN ─────────────
# {page} se sustituye por 1, 2, 3... Ajusta las URLs si una tienda cambia su estructura.
SOURCES = [
    # mode: "browser" = Chromium real con Playwright (webs con JS o anti-bot: PcComponentes, Amazon)
    #       "http"    = petición simple con requests (tiendas de servidor renderizado: PcBox, LDLC)
    #       "vtex"    = API JSON pública de tiendas VTEX (experimental)
    # PcComponentes cambió sus URLs (2025-2026): la categoría ahora vive bajo /categorias/...
    {"name": "PcComponentes", "mode": "browser", "pages": 6,
     "url": "https://www.pccomponentes.com/categorias/discos-duros/3-5-pulgadas?page={page}"},
    # PcBox NO es VTEX: es HTML servido (nombres tipo "4000GB"). Pagina con ?page=N.
    {"name": "PcBox", "mode": "http", "pages": 3,
     "url": "https://www.pcbox.com/componentes-de-ordenador/discos-duros/discos-hdd?page={page}"},
    # Amazon España: bloquea scrapers; va con navegador real, una búsqueda por capacidad.
    # Si aparece captcha, relanza con --headed y resuélvelo en la ventana.
    {"name": "Amazon.es", "mode": "browser", "query": "disco duro interno nas {tb} tb",
     "url": "https://www.amazon.es/s?k={q}", "extract": "amazon"},
    # LDLC España: categoría de HDD 3.5". Paginación incierta -> se consulta la 1ª página.
    {"name": "LDLC", "mode": "http", "pages": 1,
     "url": "https://www.ldlc.com/es-es/informatica/piezas-de-informatica/disco-duro-interno/c4697/+fv63-1346.html"},
    # Respaldo: búsqueda del propio sitio de PcComponentes, una consulta por capacidad.
    {"name": "PcComponentes (búsqueda)", "mode": "browser", "enabled": False,
     "query": "disco duro nas {tb} tb",
     "url": "https://www.pcbox.com/s/{q}?map=ft"},
    {"name": "PcComponentes (búsqueda)", "mode": "browser", "enabled": False,
     "query": "disco duro nas {tb} tb",
     "url": "https://www.pccomponentes.com/search/?query={q}"},
]
HEADED = False            # --headed abre el navegador visible (útil si hay anti-bot)
MIN_TB, MAX_TB, TOP_N = 4, 20, 100
DELAY = (1.2, 2.5)        # pausa aleatoria entre peticiones (segundos)
COOLDOWN = 60             # espera mínima entre rebúsquedas (segundos)
PORT = 8765
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

# ───────────── EXTRACCIÓN ─────────────
BRANDS = ["Seagate", "Western Digital", "WD", "Toshiba", "HGST", "Hitachi", "Synology", "QNAP", "Samsung", "Ugreen"]
LINE_RE = re.compile(r"(IronWolf Pro|IronWolf|Red Plus|Red Pro|Red|N300|Exos\s?\w*|Ultrastar[\w ]{0,12}|Barracuda|Gold|HAT\d+)", re.I)
PART_RE = re.compile(r"\b(ST\d{4,5}[A-Z]{2}\d{3,4}|WD\d{2,3}[A-Z]{4}|HDW[A-Z]\d{3}[A-Z]{2}\d|HUH\d+[A-Z0-9]+|MG\d{2}[A-Z]{3}\d{3,4}[A-Z]?)\b")
NAS_RE = re.compile(r"\bnas\b|ironwolf|red (plus|pro)|\bred\b|n300|ultrastar|exos|hat\d{4}", re.I)
BAD_RE = re.compile(r"\bssd\b|nvme|m\.2|externo|portátil|portatil|enclosure|carcasa|caddy|adaptador|cable", re.I)
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s?€")


def parse_price(v):
    if isinstance(v, (int, float)):
        return float(v)
    v = str(v).strip()
    m = PRICE_RE.search(v)
    if m:
        return float(m.group(1).replace(".", "") + "." + (m.group(2) or "0"))
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def parse_spec(title, brand_hint=""):
    """Saca marca, modelo, TB, caché y pulgadas del título. Devuelve None si no encaja."""
    if BAD_RE.search(title):
        return None
    m = re.search(r"(\d{1,2})\s?TB", title, re.I)
    if m:
        tb = int(m.group(1))
    else:  # algunas tiendas (PcBox) indican la capacidad en GB: "18000GB 3.5\""
        g = re.search(r"(\d{3,5})\s?GB", title, re.I)
        tb = round(int(g.group(1)) / 1000) if g else None
    if tb is None or not (MIN_TB <= tb <= MAX_TB):
        return None
    low = (brand_hint + " " + title).lower()
    brand = next((b for b in BRANDS if b.lower() in low), brand_hint.strip() or "—")
    brand = "Western Digital" if brand == "WD" else brand
    line = LINE_RE.search(title)
    part = PART_RE.search(title)
    model = " ".join(x for x in [line.group(1).strip() if line else "", part.group(1) if part else ""] if x)
    cache = re.search(r"(\d{2,3})\s?MB", title, re.I)
    inch = re.search(r'(3[.,]5|2[.,]5)\s?(?:"|”|pulgadas|\'\'|in\b)', title, re.I)
    return {
        "brand": brand, "model": model or title[:40], "tb": tb,
        "cache": int(cache.group(1)) if cache else None,
        "inch": inch.group(1).replace(",", ".") if inch else None,
        "nas": bool(NAS_RE.search(title)), "title": title.strip(),
    }


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)



def _dedupe(items):
    seen, out = set(), []
    for it in items:
        key = (re.sub(r"\s+", " ", it["name"].lower())[:80], it.get("price"))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def extract_products(html, base_url, store):
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "html.parser")
    out = []
    # 1) JSON-LD (lo más fiable cuando existe)
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        for o in _walk(data):
            if str(o.get("@type", "")).lower() != "product":
                continue
            offers = o.get("offers") or {}
            offers = offers[0] if isinstance(offers, list) and offers else offers
            price = parse_price(offers.get("price") or offers.get("lowPrice") or "") if isinstance(offers, dict) else None
            brand = o.get("brand")
            brand = brand.get("name", "") if isinstance(brand, dict) else (brand or "")
            rt = o.get("aggregateRating") or {}
            out.append(dict(name=o.get("name", ""), brand=brand, price=price,
                            url=urljoin(base_url, o.get("url") or (offers.get("url") if isinstance(offers, dict) else "") or ""),
                            rating=float(rt["ratingValue"]) if rt.get("ratingValue") else None,
                            reviews=int(float(rt.get("reviewCount") or rt.get("ratingCount") or 0)), store=store))
    out = _dedupe(out)
    if out:
        return out
    # 1b) JSON embebido de la página (Next.js __NEXT_DATA__, estado del cliente, etc.)
    #     La nueva web de PcComponentes ya no siempre publica JSON-LD, pero sí incrusta
    #     los datos de catálogo en <script> como JSON.
    for tag in soup.find_all("script"):
        if (tag.get("type") or "").lower() == "application/ld+json":
            continue
        txt = (tag.string or "").strip()
        if not txt.startswith("{"):
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        found = []
        for o in _walk(data):
            name = o.get("name") or o.get("productName")
            if not isinstance(name, str) or not re.search(r"\d{1,2}\s?TB", name, re.I):
                continue
            price = None
            for k in ("price", "finalPrice", "bestPrice", "priceValue", "Price"):
                if k in o:
                    price = parse_price(o[k])
                    if price:
                        break
            if price is None:
                offers = o.get("offers")
                if isinstance(offers, dict):
                    price = parse_price(offers.get("price") or offers.get("lowPrice") or "")
            if not price:
                continue
            url = o.get("url") or o.get("link") or o.get("slug") or ""
            if isinstance(url, str) and url and not url.startswith("http"):
                url = urljoin(base_url, url)
            brand = o.get("brand")
            brand = brand.get("name", "") if isinstance(brand, dict) else (brand or "")
            found.append(dict(name=name.strip(), brand=brand, price=price, url=url or base_url,
                              rating=None, reviews=0, store=store))
        if found:
            out = _dedupe(out + found)
    if out:
        return out
    # 2) Respaldo heurístico: enlaces con "xx TB" cuyo contenedor cercano tenga un precio en €
    seen = set()
    for a in soup.select("a[href]"):
        h = a.select_one("h2,h3,h4,[class*=title],[class*=name]")
        name = (h.get_text(" ", strip=True) if h else a.get("title") or a.get_text(" ", strip=True) or "").strip()
        if not re.search(r"\d{1,2}\s?TB|\d{3,5}\s?GB", name, re.I) or len(name) > 260:
            continue
        node, price, txt = a, None, ""
        for _ in range(6):
            txt = node.get_text(" ", strip=True)
            price = parse_price(txt) if "€" in txt else None
            if price or node.parent is None:
                break
            node = node.parent
        href = urljoin(base_url, a["href"])
        if price and href not in seen:
            seen.add(href)
            rm = re.search(r"(\d[,.]\d|\d)\s?/\s?5", txt)
            om = re.search(r"(\d+)\s+opiniones", txt)
            out.append(dict(name=name, brand="", price=price, url=href,
                            rating=float(rm.group(1).replace(",", ".")) if rm else None,
                            reviews=int(om.group(1)) if om else 0, store=store))
    return out



def extract_amazon(html, base_url, store):
    """Resultados de búsqueda de Amazon (div[data-component-type=s-search-result])."""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select('div[data-component-type="s-search-result"]'):
        h = card.select_one("h2 span") or card.select_one("h2")
        name = h.get_text(" ", strip=True) if h else ""
        if not name:
            continue
        price = None
        po = card.select_one("span.a-price span.a-offscreen") or card.select_one("span.a-price")
        if po:
            price = parse_price(po.get_text(" ", strip=True))
        link = card.select_one('a.a-link-normal[href*="/dp/"]') or card.select_one("a.a-link-normal[href]")
        url = urljoin(base_url, link["href"].split("?")[0] + "/") if link and link.get("href") else base_url
        rating = None
        ra = card.select_one("span.a-icon-alt")
        if ra:
            rm = re.search(r"(\d[\d,.]*)\s*(?:de|out of|/)\s*5", ra.get_text())
            if rm:
                rating = float(rm.group(1).replace(",", "."))
        out.append(dict(name=name, brand="", price=price, url=url, rating=rating, reviews=0, store=store))
    return out

def extract_vtex(js, store):
    out = []
    for p in js if isinstance(js, list) else []:
        try:
            off = p["items"][0]["sellers"][0]["commertialOffer"]
            if off.get("Price") and off.get("AvailableQuantity", 1):
                out.append(dict(name=p.get("productName", ""), brand=p.get("brand", ""), price=float(off["Price"]),
                                url=p.get("link", ""), rating=None, reviews=0, store=store))
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return out


# ───────────── BÚSQUEDA ─────────────
CHALLENGE = ("just a moment", "cf-chl", "attention required", "access denied")


def run_search(progress=lambda *_: None, debug=False):
    import requests
    http = requests.Session()
    http.headers.update(HEADERS)
    pw = browser = ctx = None

    def browser_get(url):
        nonlocal pw, browser, ctx
        if ctx is None:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=not HEADED)
            ctx = browser.new_context(locale="es-ES", user_agent=HEADERS["User-Agent"], viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        try:
            r = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            for _ in range(6):  # scroll para cargar imágenes/productos perezosos
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(400)
            html = page.content()
            waited = 0
            while HEADED and any(c in html[:3000].lower() for c in CHALLENGE) and waited < 40:
                page.wait_for_timeout(2000); waited += 2; html = page.content()  # tiempo para resolver el captcha a mano
            return (r.status if r else 0), html
        finally:
            page.close()

    raw, pages_ok, per_source, seen = [], 0, [], set()
    srcs = [x for x in SOURCES if x.get("enabled", True)]
    from urllib.parse import quote
    steps = sum(len(range(MIN_TB, MAX_TB + 1, 2)) if (x["mode"] == "vtex" or "query" in x) else x["pages"] for x in srcs) or 1
    done = 0
    try:
        for src in srcs:
            ok = items = 0
            note = ""
            try:
                if src["mode"] == "vtex":
                    reqs = [src["url"].format(tb=tb) for tb in range(MIN_TB, MAX_TB + 1, 2)]
                elif "query" in src:
                    reqs = [src["url"].format(q=quote(src["query"].format(tb=tb))) for tb in range(MIN_TB, MAX_TB + 1, 2)]
                else:
                    reqs = [src["url"].format(page=p) for p in range(1, src["pages"] + 1)]
                for i, url in enumerate(reqs, 1):
                    progress(done / steps, f"{src['name']} · {i}/{len(reqs)}")
                    done += 1
                    if src["mode"] == "browser":
                        status, html = browser_get(url)
                    else:
                        r = http.get(url, timeout=20)
                        status, html = r.status_code, r.text
                    blocked = any(c in html[:3000].lower() for c in CHALLENGE) and status in (200, 403, 503)
                    found = []
                    if status == 200 and not blocked:
                        if src["mode"] == "vtex":
                            try:
                                found = extract_vtex(json.loads(html), src["name"])
                            except Exception:
                                found = []
                        elif src.get("extract") == "amazon":
                            found = extract_amazon(html, url, src["name"])
                        else:
                            found = extract_products(html, url, src["name"])
                    new = [f for f in found if f["url"] not in seen]
                    if debug:
                        print(f"[{status}{' anti-bot' if blocked else ''}] {url} -> {len(found)} productos ({len(new)} nuevos)", file=sys.stderr)
                    if not new:
                        if ok == 0:
                            note = "bloqueada por anti-bot (prueba --headed)" if blocked or status in (403, 429) else \
                                   f"HTTP {status}" if status != 200 else "sin productos reconocibles"
                        elif found:
                            note = "paginación ignorada (la página ?page=N devuelve lo mismo); prueba la fuente de búsqueda"
                        if src["mode"] != "vtex":
                            break
                        continue
                    seen.update(f["url"] for f in new)
                    ok += 1; items += len(new); raw += new
                    time.sleep(random.uniform(*DELAY))
            except ImportError:
                note = "falta Playwright: pip install playwright && playwright install chromium"
            except Exception as e:
                note = f"error: {str(e)[:100]}"
            pages_ok += ok
            per_source.append({"name": src["name"], "pages": ok, "items": items, "note": note})
    finally:
        if ctx:
            ctx.close(); browser.close(); pw.stop()
    return build_dataset(raw, pages_ok, per_source)


def build_dataset(raw, pages_ok, per_source):
    best = {}
    for r in raw:
        spec = parse_spec(r["name"], r.get("brand", ""))
        if not spec or not spec["nas"] or not r.get("price"):
            continue
        d = {**spec, "price": round(r["price"], 2), "url": r["url"], "store": r["store"],
             "rating": r.get("rating"), "reviews": r.get("reviews", 0)}
        key = (d["brand"].lower(), re.sub(r"\W", "", d["model"].lower()), d["tb"], d["cache"])
        cur = best.get(key)
        if cur is None or d["price"] < cur["price"]:
            if cur and cur.get("rating") and not d["rating"]:
                d["rating"], d["reviews"] = cur["rating"], cur["reviews"]
            d["offers"] = (cur["offers"] if cur else 0) + 1
            best[key] = d
        else:
            cur["offers"] += 1
            if d["rating"] and (not cur["rating"] or d["reviews"] > cur["reviews"]):
                cur["rating"], cur["reviews"] = d["rating"], d["reviews"]
    items = list(best.values())
    for d in items:
        d["ppt"] = round(d["price"] / d["tb"], 2)
    items.sort(key=lambda d: d["ppt"])
    unique = len(items)
    items = items[:TOP_N]
    hl = highlights(items)
    return {"meta": {"time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "pages": pages_ok,
                     "raw": len(raw), "unique": unique, "shown": len(items), "sources": per_source},
            "items": items, "highlights": hl}


def highlights(items):
    if not items:
        return {}
    cheapest = min(items, key=lambda d: d["price"])
    rated = [d for d in items if d.get("rating")]
    most_rated = max(rated, key=lambda d: (d["rating"] * (1 - 1 / (1 + d["reviews"] / 10)), d["reviews"])) if rated else None
    ppts = [d["ppt"] for d in items]
    lo, hi = min(ppts), max(ppts)

    def score(d):  # mejor = 50% €/TB, 25% valoración, 15% gama NAS, 10% caché
        cheap = 1 - (d["ppt"] - lo) / (hi - lo) if hi > lo else 1
        rate = (d["rating"] or 0) / 5
        cache = min((d["cache"] or 0) / 512, 1)
        return .5 * cheap + .25 * rate + .15 * (1 if d["nas"] else 0) + .1 * cache
    best = max(items, key=score)
    return {"cheapest": cheapest, "rated": most_rated, "best": best}


def demo_dataset():
    rnd = random.Random(7)
    lines = [("Seagate", "IronWolf", "ST{n}VN006", 256, 22), ("Seagate", "IronWolf Pro", "ST{n}NT001", 256, 29),
             ("Western Digital", "Red Plus", "WD{n}EFPX", 256, 24), ("Western Digital", "Red Pro", "WD{n}KFGX", 512, 31),
             ("Toshiba", "N300", "HDWG{n}UZSVA", 256, 25), ("Seagate", "Exos", "ST{n}NM000", 256, 27)]
    raw = []
    for tb in (4, 6, 8, 10, 12, 14, 16, 18, 20):
        for st in ("PcComponentes", "Coolmod", "PcBox"):
            for brand, line, part, cache, base in lines:
                if rnd.random() < .35:
                    continue
                price = round(tb * base * rnd.uniform(.85, 1.2) + 12, 2)
                name = f'Disco Duro {brand} {line} {tb}TB 3.5" {cache}MB NAS {part.format(n=tb*1000)}'
                raw.append(dict(name=name, brand=brand, price=price, url="https://example.com/" + str(rnd.random())[2:8],
                                rating=round(rnd.uniform(4.0, 4.9), 1) if rnd.random() < .8 else None,
                                reviews=rnd.randint(3, 900), store=st))
    return build_dataset(raw, 9, [{"name": s["name"], "pages": 3, "items": 50} for s in SOURCES])


# ───────────── INTERFAZ ─────────────
PAGE = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discos NAS · comparador</title>
<style>
:root{--bg:#eef1f4;--panel:#fff;--ink:#14202b;--mute:#5b6b7a;--line:#d6dde4;--acc:#2447f5;--acc-ink:#fff;
--cheap:#0e8a5f;--rate:#b86e00;--best:#2447f5;--bar:#c9d3ff;--r:14px}
@media(prefers-color-scheme:dark){:root{--bg:#10161d;--panel:#18212b;--ink:#e8eef4;--mute:#93a3b3;--line:#27333f;--acc:#7b94ff;
--acc-ink:#10161d;--cheap:#3fd19a;--rate:#f0b24a;--best:#7b94ff;--bar:#2a3a7a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "IBM Plex Sans","Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header{display:flex;flex-wrap:wrap;gap:20px;justify-content:space-between;align-items:flex-end;margin-bottom:26px}
h1{font-size:clamp(28px,4.5vw,46px);line-height:1.05;margin:0 0 6px;letter-spacing:-.02em;font-weight:700}
.sub{color:var(--mute);margin:0;max-width:52ch}
button{font:inherit;cursor:pointer;border:0;border-radius:10px;padding:12px 20px;background:var(--acc);color:var(--acc-ink);font-weight:600;min-width:210px;position:relative;overflow:hidden}
button:disabled{cursor:not-allowed;opacity:.8}button:focus-visible,input:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
button .fill{position:absolute;inset:0 auto 0 0;width:0;background:rgba(255,255,255,.28);transition:width .4s}
button span{position:relative}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:22px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:14px 16px}
.stat b{display:block;font-size:26px;letter-spacing:-.01em}.stat small{color:var(--mute)}
.srcs{display:flex;flex-wrap:wrap;gap:8px;margin:-8px 0 20px}.srcs span{font-size:13px;padding:5px 11px;border-radius:99px;border:1px solid var(--line);background:var(--panel)}.srcs .bad{border-color:#c0392b;color:#c0392b}
.hl{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:28px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:18px;border-top:5px solid var(--c);display:flex;flex-direction:column;gap:6px}
.card h3{margin:0;font-size:14px;color:var(--c);font-weight:700}
.card .m{font-size:20px;font-weight:700;line-height:1.2}.card .p{font-size:30px;font-weight:700;letter-spacing:-.02em}
.card .meta{color:var(--mute);font-size:13px}.card a{margin-top:auto;color:var(--c);font-weight:600}
.tools{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;align-items:center}
input,select{font:inherit;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--ink)}
input{flex:1;min-width:200px}
.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{padding:7px 12px;border-radius:99px;border:1px solid var(--line);background:var(--panel);color:var(--ink);min-width:0;font-weight:500}
.chip[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.tablewrap{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:860px}
th,td{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-size:13px;color:var(--mute);font-weight:600;position:sticky;top:0;background:var(--panel)}
tr:last-child td{border-bottom:0}tr:hover td{background:color-mix(in srgb,var(--acc) 6%,transparent)}
.cap{display:flex;align-items:center;gap:8px;min-width:130px}.cap i{display:block;height:8px;border-radius:4px;background:var(--bar);width:100px;overflow:hidden}
.cap i u{display:block;height:100%;background:var(--acc)}.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{font-size:12px;padding:2px 8px;border-radius:99px;margin-left:6px;color:#fff;background:var(--c)}
td a{color:var(--acc);font-weight:600;text-decoration:none}td a:hover{text-decoration:underline}
.empty{padding:40px;text-align:center;color:var(--mute)}.foot{margin-top:18px;color:var(--mute);font-size:13px}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><div class="wrap">
<header><div><h1>Discos duros para NAS</h1>
<p class="sub">De 4 a 20 TB, el 100 más barato por terabyte entre varias tiendas. Un disco por modelo, con su mejor precio.</p></div>
<div><button id="re" type="button"><i class="fill" id="fill"></i><span id="relabel">Buscar de nuevo</span></button>
<div class="foot" id="rehint" style="margin:6px 0 0;text-align:right"></div></div></header>
<section class="stats" aria-label="Resumen de la búsqueda" id="stats"></section>
<section class="srcs" id="srcs" aria-label="Estado de las tiendas"></section>
<section class="hl" id="hl" aria-label="Destacados"></section>
<div class="tools"><input id="q" type="search" placeholder="Filtrar por marca, modelo o tienda" aria-label="Filtrar">
<select id="sort" aria-label="Ordenar"><option value="ppt">€/TB (menor primero)</option><option value="price">Precio</option>
<option value="tb">Capacidad (mayor primero)</option><option value="rating">Valoración</option></select></div>
<div class="chips" id="chips" style="margin-bottom:12px"></div>
<div class="tablewrap"><table><thead><tr><th>Marca</th><th>Modelo</th><th>Tamaño</th><th class="num">Caché</th><th>Formato</th>
<th class="num">Precio</th><th class="num">€/TB</th><th>Tienda</th><th>Enlace</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="foot" id="foot"></p></div>
<script>
const LIVE=/*LIVE*/false;let D=/*DATA*/null;let brand='';
const $=s=>document.querySelector(s),eur=n=>n.toLocaleString('es-ES',{style:'currency',currency:'EUR'});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function card(t,c,d,why){if(!d)return`<div class="card" style="--c:${c}"><h3>${t}</h3><div class="meta">Sin datos suficientes (${why}).</div></div>`;
return`<div class="card" style="--c:${c}"><h3>${t}</h3><div class="m">${esc(d.brand)} ${esc(d.model)}</div>
<div class="p">${eur(d.price)}</div><div class="meta">${d.tb} TB · ${d.cache?d.cache+' MB':'caché n/d'} · ${eur(d.ppt)}/TB${d.rating?` · ★ ${d.rating} (${d.reviews})`:''} · ${esc(d.store)}</div>
<a href="${esc(d.url)}" target="_blank" rel="noopener">Ver producto</a></div>`}
function render(){if(!D)return;const m=D.meta,h=D.highlights||{};
$('#stats').innerHTML=[['Hora de búsqueda',m.time],['Páginas encontradas',m.pages],['Discos distintos',m.unique],['Mostrados',m.shown]]
.map(([a,b])=>`<div class="stat"><small>${a}</small><b>${b}</b></div>`).join('');
$('#srcs').innerHTML=m.sources.map(x=>`<span class="${x.note?'bad':''}">${esc(x.name)}: ${x.items} productos${x.note?' — '+esc(x.note):''}</span>`).join('');
$('#hl').innerHTML=card('El más barato','var(--cheap)',h.cheapest,'')+card('El más valorado','var(--rate)',h.rated,'las tiendas no publican valoraciones')+card('El mejor','var(--best)',h.best,'');
const brands=[...new Set(D.items.map(i=>i.brand))].sort();
$('#chips').innerHTML=['',...brands].map(b=>`<button type="button" class="chip" aria-pressed="${b===brand}" data-b="${esc(b)}">${b||'Todas'}</button>`).join('');
rows()}
function rows(){const q=$('#q').value.toLowerCase(),s=$('#sort').value,h=D.highlights||{};
let L=D.items.filter(i=>(!brand||i.brand===brand)&&(`${i.brand} ${i.model} ${i.store}`.toLowerCase().includes(q)));
L.sort((a,b)=>s==='tb'?b.tb-a.tb||a.ppt-b.ppt:s==='rating'?(b.rating||0)-(a.rating||0):a[s]-b[s]);
$('#rows').innerHTML=L.length?L.map(i=>{const t=[h.cheapest===i||(h.cheapest&&h.cheapest.url===i.url)?['Barato','var(--cheap)']:0,
h.rated&&h.rated.url===i.url?['Valorado','var(--rate)']:0,h.best&&h.best.url===i.url?['Mejor','var(--best)']:0].filter(Boolean)
.map(([n,c])=>`<span class="tag" style="--c:${c}">${n}</span>`).join('');
return`<tr><td>${esc(i.brand)}</td><td>${esc(i.model)}${t}</td><td><div class="cap"><b>${i.tb} TB</b><i><u style="width:${(i.tb-4)/16*100}%"></u></i></div></td>
<td class="num">${i.cache?i.cache+' MB':'—'}</td><td>${i.inch?i.inch+'"':'—'}</td><td class="num"><b>${eur(i.price)}</b></td><td class="num">${eur(i.ppt)}</td>
<td>${esc(i.store)}</td><td><a href="${esc(i.url)}" target="_blank" rel="noopener">Abrir</a></td></tr>`}).join('')
:'<tr><td colspan="9" class="empty">Sin resultados. Prueba con otro filtro o pulsa «Buscar de nuevo».</td></tr>';
$('#foot').textContent=`${L.length} discos en pantalla. «Mejor» pondera €/TB (50%), valoración (25%), gama NAS (15%) y caché (10%). Caché y pulgadas aparecen solo si la tienda las indica.`}
$('#chips').onclick=e=>{const b=e.target.closest('.chip');if(b){brand=b.dataset.b;render()}};$('#q').oninput=rows;$('#sort').onchange=rows;
const btn=$('#re');let cdT;
function setBtn(txt,dis,pct){btn.disabled=dis;$('#relabel').textContent=txt;$('#fill').style.width=(pct||0)+'%'}
function cooldown(sec){clearInterval(cdT);if(sec<=0){setBtn('Buscar de nuevo',false,0);return}
cdT=setInterval(()=>{sec--;if(sec<=0){clearInterval(cdT);setBtn('Buscar de nuevo',false,0)}else setBtn(`Disponible en ${sec} s`,true,0)},1000);setBtn(`Disponible en ${sec} s`,true,0)}
async function poll(){const s=await(await fetch('/api/status')).json();
if(s.running){setBtn(`Buscando… ${s.label||''}`,true,Math.round(s.progress*100));setTimeout(poll,1000)}
else{D=await(await fetch('/api/data')).json();render();cooldown(s.cooldown);$('#rehint').textContent=s.error?'Error: '+s.error:''}}
btn.onclick=async()=>{setBtn('Iniciando…',true,2);const r=await fetch('/api/refresh',{method:'POST'});if(r.status===429){const j=await r.json();cooldown(j.cooldown);return}poll()};
if(!LIVE){setBtn('Búsqueda en vivo: ejecuta python nas_discos.py',true,0)}
render();if(LIVE){fetch('/api/status').then(r=>r.json()).then(s=>{if(s.running)poll();else if(!D)poll();else cooldown(s.cooldown)})}
</script></body></html>'''


def render_html(data, live):
    return PAGE.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
               .replace("/*LIVE*/false", "true" if live else "false")


# ───────────── SERVIDOR ─────────────
STATE = {"running": False, "progress": 0.0, "label": "", "data": None, "error": "", "last": 0.0}
LOCK = threading.Lock()


def worker(demo, debug):
    try:
        def prog(p, label):
            STATE.update(progress=p, label=label)
        data = demo_dataset() if demo else run_search(prog, debug)
        if demo:
            time.sleep(3)
        STATE.update(data=data, error="" if data["items"] else "No se extrajo ningún disco. Ejecuta con --debug y revisa SOURCES.")
    except Exception as e:
        STATE["error"] = str(e)
    finally:
        STATE.update(running=False, progress=1.0, last=time.time())


def start(demo, debug):
    with LOCK:
        wait = COOLDOWN - (time.time() - STATE["last"])
        if STATE["running"] or wait > 0:
            return False, max(0, int(wait))
        STATE.update(running=True, progress=0.0, label="", error="")
    threading.Thread(target=worker, args=(demo, debug), daemon=True).start()
    return True, 0


def make_handler(demo, debug):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def _status(self):
            cd = max(0, int(COOLDOWN - (time.time() - STATE["last"]))) if STATE["last"] else 0
            return {k: STATE[k] for k in ("running", "progress", "label", "error")} | {"cooldown": cd}

        def do_GET(self):
            if self.path == "/api/status":
                self._send(200, json.dumps(self._status()))
            elif self.path == "/api/data":
                self._send(200, json.dumps(STATE["data"] or {"meta": {"time": "—", "pages": 0, "raw": 0, "unique": 0, "shown": 0}, "items": [], "highlights": {}}))
            elif self.path in ("/", "/index.html"):
                self._send(200, render_html(STATE["data"], True), "text/html; charset=utf-8")
            else:
                self._send(404, "{}")

        def do_POST(self):
            if self.path == "/api/refresh":
                ok, wait = start(demo, debug)
                self._send(200 if ok else 429, json.dumps({"started": ok, "cooldown": wait}))
            else:
                self._send(404, "{}")

        def log_message(self, *a):
            pass
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="genera nas_discos.html y sale")
    ap.add_argument("--demo", action="store_true", help="datos de ejemplo")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--headed", action="store_true", help="navegador visible (anti-bot)")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    global HEADED
    HEADED = a.headed
    if a.once:
        data = demo_dataset() if a.demo else run_search(lambda p, l: print(f"{p:4.0%} {l}", file=sys.stderr), a.debug)
        open("nas_discos.html", "w", encoding="utf-8").write(render_html(data, False))
        print(f"OK: nas_discos.html ({data['meta']['unique']} discos distintos)")
        return
    start(a.demo, a.debug)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(a.demo, a.debug))
    print(f"Abre http://localhost:{PORT}  (Ctrl+C para salir)")
    if not a.no_open:
        webbrowser.open(f"http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

