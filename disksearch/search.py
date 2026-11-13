"""Búsqueda en tiendas, extracción y agregación de resultados."""
from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime
from urllib.parse import quote

from . import config
from .extractors import (
    extract_alternate,
    extract_amazon,
    extract_coolmod,
    extract_geeknetic,
    extract_products,
    extract_vtex,
    normalize_url,
)
from .parsing import parse_spec, product_key

CHALLENGE = ("just a moment", "cf-chl", "attention required", "access denied")


def source_blocks(source):
    """Devuelve listas de URLs agrupadas por bloque de paginación."""
    blocks = source.get("urls") or [source]
    result = []
    for block in blocks:
        pages = int(block.get("pages", source.get("pages", 1)) or 1)
        query = block.get("query", source.get("query"))
        template = block.get("url") or source.get("url")
        urls = []
        for page in range(1, pages + 1):
            if query is not None:
                urls.append(template.format(q=quote(query), page=page))
            else:
                urls.append(template.format(page=page))
        result.append(urls)
    return result


def source_requests(source):
    """Genera las URLs de una fuente sin bucles de capacidad."""
    for urls in source_blocks(source):
        yield from urls


def _search_steps(sources):
    return sum(1 for source in sources for _ in source_requests(source)) or 1


def run_search(progress=lambda *_: None, debug=False, sources=None):
    import requests

    sources = [s for s in (sources or config.SOURCES) if s.get("enabled", True)]
    http = requests.Session()
    http.headers.update(config.HEADERS)
    playwright = browser = context = None

    def browser_get(url):
        nonlocal playwright, browser, context
        if context is None:
            from playwright.sync_api import sync_playwright
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=not config.HEADED)
            context = browser.new_context(
                locale="es-ES",
                user_agent=config.HEADERS["User-Agent"],
                viewport={"width": 1366, "height": 900},
            )
        page = context.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            for _ in range(6):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(400)
            html = page.content()
            waited = 0
            while (config.HEADED
                   and any(c in html[:3000].lower() for c in CHALLENGE)
                   and waited < 40):
                page.wait_for_timeout(2000)
                waited += 2
                html = page.content()
            return (response.status if response else 0), html
        finally:
            page.close()

    raw, pages_ok, per_source, seen = [], 0, [], set()
    steps = _search_steps(sources)
    done = 0
    try:
        for source in sources:
            ok_pages = items = 0
            note = ""
            blocked_any = failed_any = pagination_ignored = False
            progress(done / steps, f"{source['name']} · empezando", source["name"],
                     {"state": "buscando", "results": None})
            try:
                blocks = source_blocks(source)
                for block_index, urls in enumerate(blocks, 1):
                    for page_index, url in enumerate(urls, 1):
                        progress(
                            done / steps,
                            f"{source['name']} · {block_index}/{len(blocks)} · {page_index}/{len(urls)}",
                            source["name"],
                        )
                        done += 1
                        if source["mode"] == "browser":
                            status, html = browser_get(url)
                        else:
                            response = http.get(url, timeout=25)
                            status, html = response.status_code, response.text

                        blocked = (
                            any(c in html[:3000].lower() for c in CHALLENGE)
                            and status in (200, 403, 503)
                        )
                        blocked_any = blocked_any or blocked
                        failed_any = failed_any or status != 200
                        found = []
                        if status == 200 and not blocked:
                            mode = source.get("extract", "generic")
                            if source["mode"] == "vtex":
                                try:
                                    found = extract_vtex(json.loads(html), source["name"])
                                except Exception:
                                    found = []
                            elif mode == "amazon":
                                found = extract_amazon(html, url, source["name"])
                            elif mode == "coolmod":
                                found = extract_coolmod(html, url, source["name"])
                            elif mode == "alternate":
                                found = extract_alternate(html, url, source["name"])
                            elif mode == "geeknetic":
                                found = extract_geeknetic(html, url, source["name"])
                            else:
                                found = extract_products(html, url, source["name"])
                            ok_pages += 1

                        new = []
                        for item in found:
                            item["url"] = normalize_url(item.get("url", ""), url)
                            if item["url"] not in seen:
                                seen.add(item["url"])
                                new.append(item)

                        if debug:
                            print(
                                f"[{status}{' anti-bot' if blocked else ''}] {url} -> "
                                f"{len(found)} productos ({len(new)} nuevos)",
                                file=sys.stderr,
                            )

                        if not new:
                            if blocked or status in (403, 429):
                                note = "bloqueo anti-bot en una página (prueba --headed)"
                            elif status != 200:
                                note = f"HTTP {status} en una página"
                            elif ok_pages == 0:
                                note = "sin productos reconocibles"
                            elif found:
                                note = "paginación ignorada (la página devuelve lo mismo)"
                                pagination_ignored = True
                            # Se corta este bloque, pero se prueban los demás
                            # (p. ej. PcComponentes 3,5" falla y aún queda 2,5").
                            if page_index > 1 or not found:
                                break
                            continue

                        items += len(new)
                        raw += new
                        time.sleep(random.uniform(*config.DELAY))
            except ImportError:
                note = "falta Playwright: pip install playwright && playwright install chromium"
            except Exception as exc:  # una tienda no debe tumbar la búsqueda
                note = f"error: {str(exc)[:100]}"

            pages_ok += ok_pages
            per_source.append({
                "name": source["name"],
                "pages": ok_pages,
                "items": items,
                "note": note,
                # Solo se usa para detectar ausencias si la tienda respondió
                # completa y correctamente. Un bloqueo, un HTTP raro, una
                # paginación ignorada o una fuente agregadora no deben marcar
                # productos como ausentes.
                "ok": bool(
                    ok_pages and items
                    and not blocked_any and not failed_any and not pagination_ignored
                    and not source.get("aggregator")
                ),
            })
            final = per_source[-1]
            if final["ok"]:
                state = "ok"
            elif blocked_any:
                state = "bloqueada"
            elif failed_any or not ok_pages:
                state = "fallida"
            else:
                state = "sin resultados"
            progress(
                done / steps, f"{source['name']} · {state}",
                source["name"], {"state": state, "results": items},
            )
    finally:
        if context:
            context.close()
            browser.close()
            playwright.stop()
    return build_dataset(raw, pages_ok, per_source)


def build_dataset(raw, pages_ok, per_source):
    """Agrupa ofertas por producto canónico y conserva todas las tiendas."""
    parsed = []
    forms = {}
    for observation in raw:
        spec = parse_spec(
            observation["name"], observation.get("brand", ""),
            observation.get("hints"),
        )
        price = observation.get("price")
        if not spec or not price:
            continue
        parsed.append((spec, observation, price))
        if spec.get("form_factor"):
            identity = (
                spec["brand"], spec["model"], spec["capacity_gb"], spec["kind"],
            )
            forms.setdefault(identity, set()).add(spec["form_factor"])

    # Algunas tiendas omiten el formato. Si otra tienda lo conoce para el
    # mismo modelo, capacidad y tipo, y solo hay un formato posible, se completa
    # antes de calcular la clave para no duplicar el producto. Nunca se mezcla
    # un HDD con un SSD del mismo nombre.
    for spec, _, _ in parsed:
        if spec.get("form_factor"):
            continue
        identity = (spec["brand"], spec["model"], spec["capacity_gb"], spec["kind"])
        known = forms.get(identity) or set()
        if len(known) == 1:
            spec["form_factor"] = spec["inch"] = next(iter(known))

    best = {}
    for spec, observation, price in parsed:
        key = product_key(spec)
        offer = {
            "store": observation["store"],
            "url": observation["url"],
            "price": round(float(price), 2),
            "title": spec["title"],
            "rating": observation.get("rating"),
            "reviews": observation.get("reviews", 0) or 0,
        }
        current = best.get(key)
        if current is None:
            item = {
                **spec,
                "key": key,
                "price": offer["price"],
                "url": offer["url"],
                "store": offer["store"],
                "rating": offer["rating"],
                "reviews": offer["reviews"],
                "offers_detail": [offer],
                "offers": 1,
            }
            best[key] = item
            continue

        known = {(o["store"], o["url"], o["price"]) for o in current["offers_detail"]}
        if (offer["store"], offer["url"], offer["price"]) not in known:
            current["offers_detail"].append(offer)
        current["offers"] = len(current["offers_detail"])
        if offer["price"] < current["price"]:
            current.update(
                price=offer["price"], url=offer["url"], store=offer["store"],
                rating=offer["rating"] if offer["rating"] else current.get("rating"),
                reviews=offer["reviews"] if offer["reviews"] else current.get("reviews", 0),
            )
        if offer.get("rating") and (
            not current.get("rating") or offer.get("reviews", 0) > current.get("reviews", 0)
        ):
            current["rating"], current["reviews"] = offer["rating"], offer["reviews"]

    items = list(best.values())
    for item in items:
        item["tb"] = round(item["capacity_gb"] / 1000, 3)
        item["ppt"] = round(item["price"] / item["tb"], 2) if item["tb"] else None
        item.setdefault("form_factor", item.get("inch"))
    items.sort(key=lambda d: (d["ppt"] is None, d["ppt"] or 0, d["price"], d["key"]))
    unique = len(items)
    return {
        "meta": {
            "time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "pages": pages_ok,
            "raw": len(raw),
            "unique": unique,
            "shown": len(items),
            "sources": per_source,
        },
        "items": items,
        "highlights": highlights(items),
    }


def highlights(items):
    if not items:
        return {}
    cheapest = min(items, key=lambda d: d["price"])
    rated = [d for d in items if d.get("rating")]
    most_rated = (
        max(rated, key=lambda d: (
            d["rating"] * (1 - 1 / (1 + d["reviews"] / 10)),
            d["reviews"],
        ))
        if rated else None
    )
    ppts = [d["ppt"] for d in items if d.get("ppt") is not None]
    low, high = (min(ppts), max(ppts)) if ppts else (0, 0)

    def score(item):
        cheap = 1 - (item["ppt"] - low) / (high - low) if high > low else 1
        rate = (item.get("rating") or 0) / 5
        cache = min((item.get("cache") or 0) / 512, 1)
        return .5 * cheap + .25 * rate + .15 * (1 if item.get("nas") else 0) + .1 * cache

    return {"cheapest": cheapest, "rated": most_rated, "best": max(items, key=score)}


def demo_dataset():
    """Datos deterministas para probar la UI sin internet.

    Mantiene primero las mismas capacidades y orden aleatorio que la versión
    anterior para que las pruebas de regresión puedan comparar los productos
    NAS de 4–20 TB, y añade después capacidades fuera de ese rango.
    """
    rnd = random.Random(7)
    lines = [
        ("Seagate", "IronWolf", "ST{n}VN006", 256, 22),
        ("Seagate", "IronWolf Pro", "ST{n}NT001", 256, 29),
        ("Western Digital", "Red Plus", "WD{n}EFPX", 256, 24),
        ("Western Digital", "Red Pro", "WD{n}KFGX", 512, 31),
        ("Toshiba", "N300", "HDWG{n}UZSVA", 256, 25),
        ("Seagate", "Exos", "ST{n}NM000", 256, 27),
    ]
    raw = []
    for tb in (4, 6, 8, 10, 12, 14, 16, 18, 20):
        for store in ("PcComponentes", "Coolmod", "PcBox"):
            for brand, line, part, cache, base in lines:
                if rnd.random() < .35:
                    continue
                price = round(tb * base * rnd.uniform(.85, 1.2) + 12, 2)
                name = (
                    f'Disco Duro {brand} {line} {tb}TB 3.5" {cache}MB NAS '
                    f'{part.format(n=tb * 1000)}'
                )
                raw.append(dict(
                    name=name, brand=brand, price=price,
                    url="https://example.com/" + str(rnd.random())[2:8],
                    rating=round(rnd.uniform(4.0, 4.9), 1) if rnd.random() < .8 else None,
                    reviews=rnd.randint(3, 900), store=store,
                ))
    # Ampliación: 2,5" y capacidades fuera de 4–20 TB.
    extra_lines = lines + [
        ("Seagate", "Barracuda", "ST{n}LM000", 128, 18),
        ("Western Digital", "Blue", "WD{n}AZVA", 128, 17),
    ]
    for tb in (1, 2, 3, 5, 22, 24, 32):
        for store in ("PcComponentes", "Coolmod", "PcBox"):
            for brand, line, part, cache, base in extra_lines:
                if rnd.random() < .35:
                    continue
                inch = "2.5" if tb <= 5 and line in ("Barracuda", "Blue") else "3.5"
                price = round(tb * base * rnd.uniform(.85, 1.2) + 12, 2)
                name = (
                    f'Disco Duro {brand} {line} {tb}TB {inch}" {cache}MB '
                    f'{part.format(n=tb * 1000)}'
                )
                raw.append(dict(
                    name=name, brand=brand, price=price,
                    url="https://example.com/" + str(rnd.random())[2:8],
                    rating=round(rnd.uniform(4.0, 4.9), 1) if rnd.random() < .8 else None,
                    reviews=rnd.randint(3, 900), store=store,
                ))
    # SSD internos: SATA 2,5" y M.2 NVMe, con varias tiendas por producto.
    ssd_lines = [
        ("Samsung", "990 PRO", "M.2", "NVMe", 95),
        ("Kingston", "NV3", "M.2", "NVMe", 60),
        ("Crucial", "BX500", "2.5", "SATA", 55),
        ("Western Digital", "SA510", "2.5", "SATA", 62),
        ("Kioxia", "Exceria Plus G3", "M.2", "NVMe", 70),
    ]
    for gb in (500, 1000, 2000, 4000):
        for store in ("PcComponentes", "Coolmod", "PcBox"):
            for brand, line, form, iface, base in ssd_lines:
                if rnd.random() < .35:
                    continue
                price = round((gb / 1000) * base * rnd.uniform(.85, 1.2) + 8, 2)
                name = f"Disco SSD {brand} {line} {gb}GB {form} {iface}"
                raw.append(dict(
                    name=name, brand=brand, price=price,
                    url="https://example.com/ssd-" + str(rnd.random())[2:8],
                    rating=round(rnd.uniform(4.0, 4.9), 1) if rnd.random() < .8 else None,
                    reviews=rnd.randint(3, 900), store=store,
                ))
    sources = [
        {"name": source["name"], "pages": 1, "items": 20, "note": "", "ok": True}
        for source in config.SOURCES
    ]
    return build_dataset(raw, len(sources), sources)
