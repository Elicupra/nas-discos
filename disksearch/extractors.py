"""Extractores de productos por tienda."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "srsltid", "gclid", "gad_source", "gbraid", "wbraid", "msclkid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "ref", "ref_", "tag", "th", "psc",
}


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def normalize_url(url: str, base_url: str = "") -> str:
    if not url:
        return base_url
    url = urljoin(base_url, url)
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS]
    path = parts.path
    # Amazon: conservar solo el identificador de producto.
    if "amazon." in parts.netloc:
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", path)
        if match:
            path = f"/dp/{match.group(1)}"
            query = []
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), "")).rstrip("/")


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        key = (
            re.sub(r"\s+", " ", str(item.get("name", "")).lower())[:100],
            item.get("price"),
            normalize_url(item.get("url", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _product(name, price, url, store, brand="", rating=None, reviews=0):
    return {
        "name": re.sub(r"\s+", " ", str(name or "")).strip(),
        "brand": brand or "",
        "price": price,
        "url": url,
        "rating": rating,
        "reviews": reviews or 0,
        "store": store,
    }


def extract_products(html, base_url, store):
    """Extractor genérico: JSON-LD, JSON embebido y heurística de enlaces."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out = []

    # 1) JSON-LD (lo más fiable cuando existe)
    for tag in soup.select('script[type="application/ld+json"]'):
        text = tag.string or tag.get_text() or ""
        if not text.strip():
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        for obj in _walk(data):
            if str(obj.get("@type", "")).lower() != "product":
                continue
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = None
            if isinstance(offers, dict):
                price = parse_money(offers.get("price") or offers.get("lowPrice") or "")
            brand = obj.get("brand")
            brand = brand.get("name", "") if isinstance(brand, dict) else (brand or "")
            rating_data = obj.get("aggregateRating") or {}
            out.append(_product(
                obj.get("name", ""), price,
                normalize_url(obj.get("url") or (offers.get("url") if isinstance(offers, dict) else ""), base_url),
                store, brand,
                float(rating_data["ratingValue"]) if rating_data.get("ratingValue") else None,
                int(float(rating_data.get("reviewCount") or rating_data.get("ratingCount") or 0)),
            ))
    out = _dedupe(out)
    if out:
        return out

    # 1b) JSON embebido (Next.js, estado del cliente, ItemList, etc.)
    found = []
    for tag in soup.find_all("script"):
        if (tag.get("type") or "").lower() == "application/ld+json":
            continue
        text = (tag.string or "").strip()
        if not text or text[0] not in "[{":
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        for obj in _walk(data):
            name = obj.get("name") or obj.get("productName")
            if not isinstance(name, str) or not re.search(r"\d+(?:[.,]\d+)?\s?(?:TB|GB)\b", name, re.I):
                continue
            price = None
            for key in ("price", "finalPrice", "bestPrice", "priceValue", "Price"):
                if key in obj:
                    price = parse_money(obj[key])
                    if price:
                        break
            if price is None:
                offers = obj.get("offers")
                if isinstance(offers, dict):
                    price = parse_money(offers.get("price") or offers.get("lowPrice") or "")
            if not price:
                continue
            url = obj.get("url") or obj.get("link") or obj.get("slug") or ""
            brand = obj.get("brand")
            brand = brand.get("name", "") if isinstance(brand, dict) else (brand or "")
            found.append(_product(name, price, normalize_url(url, base_url), store, brand))
    if found:
        return _dedupe(found)

    # 2) Respaldo heurístico: enlace con capacidad y precio cercano.
    seen = set()
    for anchor in soup.select("a[href]"):
        heading = anchor.select_one("h2,h3,h4,[class*=title],[class*=name]")
        name = (heading.get_text(" ", strip=True) if heading
                else anchor.get("title") or anchor.get_text(" ", strip=True) or "").strip()
        if not re.search(r"\d+(?:[.,]\d+)?\s?(?:TB|GB)\b", name, re.I) or len(name) > 300:
            continue
        node, price, text = anchor, None, ""
        for _ in range(6):
            text = node.get_text(" ", strip=True)
            price = parse_money(text) if "€" in text else None
            if price or node.parent is None:
                break
            node = node.parent
        url = normalize_url(anchor["href"], base_url)
        if price and url not in seen:
            seen.add(url)
            rating_match = re.search(r"(\d[,.]\d)\s?/\s?5", text)
            reviews_match = re.search(r"(\d+)\s+opiniones", text)
            out.append(_product(
                name, price, url, store, "",
                float(rating_match.group(1).replace(",", ".")) if rating_match else None,
                int(reviews_match.group(1)) if reviews_match else 0,
            ))
    return out


def extract_amazon(html, base_url, store):
    """Resultados de búsqueda de Amazon."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select('div[data-component-type="s-search-result"]'):
        heading = card.select_one("h2 span") or card.select_one("h2")
        name = heading.get_text(" ", strip=True) if heading else ""
        if not name:
            continue
        price = None
        price_node = card.select_one("span.a-price span.a-offscreen") or card.select_one("span.a-price")
        if price_node:
            price = parse_money(price_node.get_text(" ", strip=True))
        link = card.select_one('a.a-link-normal[href*="/dp/"]') or card.select_one("a.a-link-normal[href]")
        href = link.get("href", "") if link else ""
        url = normalize_url(href, base_url)
        rating = None
        rating_node = card.select_one("span.a-icon-alt")
        if rating_node:
            match = re.search(r"(\d[\d,.]*)\s*(?:de|out of|/)\s*5", rating_node.get_text())
            if match:
                rating = float(match.group(1).replace(",", "."))
        out.append(_product(name, price, url, store, "", rating, 0))
    return out


def extract_coolmod(html, base_url, store):
    """Coolmod: las tarjetas exponen datos de producto en atributos data-*."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select("article.product-card"):
        anchor = card.select_one("a[data-itemname]")
        if not anchor:
            continue
        price = parse_money(anchor.get("data-itemprice") or "")
        if not price:
            price_node = card.select_one(".product_price, .price")
            price = parse_money(price_node.get_text(" ", strip=True)) if price_node else None
        out.append(_product(
            anchor.get("data-itemname") or anchor.get_text(" ", strip=True),
            price,
            normalize_url(anchor.get("href", ""), base_url),
            store,
            anchor.get("data-itembrand") or "",
        ))
    return _dedupe(out)


def extract_alternate(html, base_url, store):
    """Alternate.es: listado con tarjetas a.productBox y span.price."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select("a.productBox"):
        name_node = card.select_one("[class*=product-name], [class*=productName]")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        if not name:
            # La primera línea del bloque de texto contiene el título completo.
            text = card.get_text(" ", strip=True)
            name = text.split(" Capacidad:")[0].split(" €")[0].strip()
        price = None
        for price_node in card.select("span.price"):
            price = parse_money(price_node.get_text(" ", strip=True))
            if price:
                break
        out.append(_product(
            name, price, normalize_url(card.get("href", ""), base_url), store
        ))
    return _dedupe(out)


def extract_vtex(js, store):
    out = []
    for product in js if isinstance(js, list) else []:
        try:
            offer = product["items"][0]["sellers"][0]["commertialOffer"]
            if offer.get("Price") and offer.get("AvailableQuantity", 1):
                out.append(_product(
                    product.get("productName", ""), float(offer["Price"]),
                    normalize_url(product.get("link", "")), store,
                    product.get("brand", ""),
                ))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out


def parse_money(value):
    """Import local para evitar un ciclo entre extractores y parsing."""
    from .parsing import parse_price
    return parse_price(value)
