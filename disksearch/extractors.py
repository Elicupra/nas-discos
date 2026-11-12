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


def _product(name, price, url, store, brand="", rating=None, reviews=0, **extra):
    item = {
        "name": re.sub(r"\s+", " ", str(name or "")).strip(),
        "brand": brand or "",
        "price": price,
        "url": url,
        "rating": rating,
        "reviews": reviews or 0,
        "store": store,
    }
    item.update(extra)
    return item


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


_SSD_TITLE_RE = re.compile(r"\bssd\b|\bnvme\b|\bm\.?\s?2\b|\bmsata\b", re.I)


def _geek_form(value):
    low = (value or "").lower().replace(",", ".")
    if "m.2" in low:
        return "M.2"
    if "msata" in low:
        return "mSATA"
    match = re.search(r"\b(2\.5|3\.5)\b", low)
    return match.group(1) if match else None


def _geek_interface(value):
    low = (value or "").lower()
    if "nvme" in low:
        return "NVMe"
    if "pcie" in low:
        return "PCIe"
    if "sata" in low:
        return "SATA"
    if "sas" in low:
        return "SAS"
    return None


def _geek_interface_from_title(title, label_value):
    """La ficha SSD no incluye interfaz; inferimos del título."""
    low = (title or "").lower()
    if "nvme" in low or "pcie" in low:
        return "NVMe"
    if "sas" in low:
        return "SAS"
    return _geek_interface(label_value)


def _geek_brand(name):
    """Marca cuando el título solo trae la línea o el número de parte."""
    low = name.lower()
    if re.search(r"\bwd\b|ultrastar", low):
        return "Western Digital"
    if re.search(r"\bhdw[a-z0-9]|\bn300\b|\bmg\d{2}\b", low):
        return "Toshiba"
    return ""


def extract_geeknetic(html, base_url, store):
    """Agregador Geeknetic: tarjetas con specs y precio «desde».

    Solo se leen las listas del comparador. No se siguen los enlaces de
    afiliado ``ver-tienda`` ni se piden las fichas de cada producto.
    """
    from bs4 import BeautifulSoup
    from .parsing import parse_capacity_gb

    soup = BeautifulSoup(html, "html.parser")
    page_kind = "SSD" if re.search(r"/ssds?/", base_url, re.I) else "HDD"
    out = []
    for card in soup.select("article.product"):
        title_node = card.select_one(".product-title a") or card.select_one(".product-title")
        if not title_node:
            continue
        name = title_node.get_text(" ", strip=True)
        if not name:
            continue

        labels = {}
        for spec in card.select(".product-spec span"):
            text = spec.get_text(" ", strip=True)
            if ":" in text:
                label, value = text.split(":", 1)
                labels[label.strip().lower()] = value.strip()

        hints = {"kind": page_kind}
        capacity = parse_capacity_gb(labels.get("capacidad", ""))
        if capacity:
            hints["capacity_gb"] = capacity
        form = _geek_form(labels.get("formato") or labels.get("tamaño") or "")
        if form:
            hints["form_factor"] = form
        interface = _geek_interface_from_title(
            name, labels.get("tipo de interfaz", "")
        )
        if interface:
            hints["interface"] = interface
        # La categoría manda, salvo que la propia tarjeta diga claramente SSD.
        if "formato" in labels or _SSD_TITLE_RE.search(name):
            hints["kind"] = "SSD"

        price_node = card.select_one(".product-price-amount") or card.select_one(".product-price")
        price = parse_money(price_node.get_text(" ", strip=True)) if price_node else None

        offers = 0
        button = card.select_one(".product-button")
        if button:
            match = re.search(r"(\d+)\s*ofertas?", button.get_text(" ", strip=True), re.I)
            offers = int(match.group(1)) if match else 0

        link = card.select_one("a.product-img[href]") or card.select_one(".product-title a[href]")
        href = link.get("href", "") if link else ""
        if "ver-tienda" in href:
            href = ""
        out.append(_product(
            name, price, normalize_url(href, base_url), store,
            _geek_brand(name), hints=hints, offers_count=offers,
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
