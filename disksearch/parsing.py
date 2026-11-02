"""Normalización de precios, capacidades y productos."""
from __future__ import annotations

import re
import unicodedata

BRANDS = [
    "Western Digital", "Seagate", "Toshiba", "HGST", "Hitachi", "Synology",
    "QNAP", "Samsung", "Ugreen", "WD", "LaCie", "Buffalo", "Dell", "HP",
]

LINE_RE = re.compile(
    r"(IronWolf Pro|IronWolf|Red Plus|Red Pro|Purple Pro|Purple|"
    r"Blue|Black|Gold|Green|N300|N300 Pro|MG\d{2}[A-Z]*|Exos\s?\w*|"
    r"Ultrastar[\w ]{0,20}|Barracuda|SkyHawk(?:\s?AI)?|HAT\d+|"
    r"P300|S300|X300|L200|Enterprise|Surveillance)",
    re.I,
)
PART_RE = re.compile(
    r"\b("
    r"ST\d{4,5}[A-Z]{2}\d{3,4}|"
    r"ST\d{6,10}[A-Z]{0,2}\d{0,4}|"
    r"WD\d{2,3}[A-Z]{4,5}|"
    r"HDW[A-Z]\d{3}[A-Z]{2}\d|"
    r"HUH\d+[A-Z0-9]+|"
    r"MG\d{2}[A-Z]{2,4}\d{3,4}[A-Z]?|"
    r"HAT\d{4}[A-Z0-9-]*|"
    r"WD\d{2}[A-Z]{2}\d{2}"
    r")\b"
)
NAS_RE = re.compile(
    r"\bnas\b|ironwolf|red (plus|pro)|\bred\b|n300|ultrastar|exos|hat\d{4}|"
    r"skyhawk|purple|surveillance",
    re.I,
)

# Productos que no son discos internos. Se excluyen también packs y
# dispositivos NAS completos que a veces aparecen en las categorías.
BAD_RE = re.compile(
    r"\bssd\b|nvme|m\.2|extern[oa]|external|portátil|portatil|enclosure|"
    r"carcasa|caddy|adaptador|adaptador|dock|estación de acoplamiento|"
    r"cable|hdd enclosure|disco duro externo|unidad óptica|"
    r"paquete|bundle|servidor nas|estación nas|todo en uno|"
    r"memoria usb|pendrive|tarjeta de memoria|"
    # Líneas comerciales de discos externos/portátiles.
    r"\bcanvio\b|\bexpansion\b|\belements\b|\bmy book\b|\bmy passport\b|"
    r"\bbackup plus\b|\bgame drive\b|\bone touch\b|\bfastwriter\b|"
    r"\bd2 professional\b|\brugged\b|\bportable\b|"
    # Series de SSD que a veces aparecen mezcladas en categorías de HDD.
    r"\b(?:samsung\s+)?(?:8[5-9]0|9[0-9]0)\s+(?:evo|qvo|pro)\b|"
    r"\bcrucial\b|\bsandisk\b|\bkingston\b",
    re.I,
)
HDD_HINT_RE = re.compile(
    r"disco duro|hdd|unidad de disco duro|hard drive|"
    r"ironwolf|barracuda|skyhawk|exos|ultrastar|red plus|red pro|purple|"
    r"n300|hat\d{4}|mg\d{2}|p300|s300|x300|l200",
    re.I,
)
# "To"/"Go" son las unidades que usa LDLC en su versión española.
CAP_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(TB|Tb|TO|To|GB|Gb|GO|Go)\b", re.I)
CACHE_RE = re.compile(r"(\d{2,3})\s?MB\b", re.I)
RPM_RE = re.compile(r"(\d{4,5})\s?RPM\b", re.I)
FORM_RE = re.compile(
    r"(?<![\d.])(3[.,]5|2[.,]5)\s*(?:\"|”|''|pulgadas|\bin\b|-inch|zoll)?",
    re.I,
)
INTERFACE_RE = re.compile(r"\b(SATA(?:\s?III|\s?3)?|SAS|USB(?:\s?[23](?:\.\d)?)?)\b", re.I)

NUMBER_RE = r"\d+(?:\.\d{3})*(?:[.,]\d{1,2})?"


def _to_number(raw: str):
    try:
        if "," in raw and "." in raw:
            return float(raw.replace(".", "").replace(",", "."))
        if "," in raw:
            return float(raw.replace(",", "."))
        if raw.count(".") > 1 or re.fullmatch(r"\d+(?:\.\d{3})+", raw):
            return float(raw.replace(".", ""))
        return float(raw)
    except ValueError:
        return None


def parse_price(value):
    """Convierte precios españoles (``1.234,56 €``) y números simples."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value).strip().replace("\xa0", " ")
    if not text:
        return None
    # Prioriza la cifra pegada al símbolo € (delante o detrás).
    for pattern in (rf"({NUMBER_RE})\s*(?:€|EUR)", rf"(?:€|EUR)\s*({NUMBER_RE})"):
        match = re.search(pattern, text, re.I)
        if match:
            number = _to_number(match.group(1))
            if number and number > 0:
                return number
    candidates = [
        number for raw in re.findall(NUMBER_RE, text)
        if (number := _to_number(raw)) and number > 0
    ]
    return candidates[0] if candidates else None


def parse_capacity_gb(title: str):
    """Devuelve la capacidad en GB sin redondear a TB enteros."""
    matches = CAP_RE.findall(title or "")
    if not matches:
        return None
    # En títulos con varios valores (p. ej. pack 2x6 TB) se elige el mayor.
    values = []
    for number, unit in matches:
        try:
            n = float(number.replace(",", "."))
        except ValueError:
            continue
        gb = n * 1000 if unit.upper() in ("TB", "TO") else n
        if 10 <= gb <= 100_000:
            values.append(gb)
    if not values:
        return None
    return int(round(max(values)))


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


def _slug(text: str) -> str:
    text = _normalize(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "sin-modelo"


def detect_brand(title: str, hint: str = "") -> str:
    low = f" {hint} {title} ".lower()
    for brand in BRANDS:
        if brand == "WD":
            if re.search(r"\bwd\b", low):
                return "Western Digital"
            continue
        if brand.lower() in low:
            return brand
    # Algunas fichas solo incluyen el número de parte.
    part = PART_RE.search(title)
    if part:
        value = part.group(1).upper()
        if value.startswith("ST"):
            return "Seagate"
        if value.startswith("WD"):
            return "Western Digital"
        if value.startswith(("HDW", "HUH", "MG")):
            return "Toshiba"
        if value.startswith("HAT"):
            return "Synology"
    return hint.strip() or "—"


def parse_spec(title: str, brand_hint: str = ""):
    """Extrae las características de un título.

    Devuelve ``None`` si no parece un disco duro interno. No aplica límites de
    capacidad: un HDD de 500 GB o de 32 TB es igual de válido.
    """
    if not title or BAD_RE.search(title):
        return None

    capacity_gb = parse_capacity_gb(title)
    if not capacity_gb:
        return None

    form = FORM_RE.search(title)
    form_factor = form.group(1).replace(",", ".") if form else None
    if form_factor not in ("2.5", "3.5"):
        form_factor = None

    # Evita confundir "2.5GbE" o "3.5 Gbps" con un formato de disco.
    if form and re.search(rf"{re.escape(form.group(1))}\s*(?:Gb|Gbps|GHz)", title, re.I):
        form_factor = None

    if not form_factor and not HDD_HINT_RE.search(title):
        return None

    # Heurística conservadora: estas gamas de NAS/empresa son de 3,5" cuando
    # la ficha omite el formato y la capacidad es de escritorio.
    if not form_factor and capacity_gb >= 4000 and re.search(
        r"ironwolf|red (?:plus|pro)|\bred\b|n300|exos|ultrastar|"
        r"skyhawk|purple|hat\d{4}|mg\d{2}",
        title, re.I,
    ):
        form_factor = "3.5"

    low = f"{brand_hint} {title}".lower()
    brand = detect_brand(title, brand_hint)
    line = LINE_RE.search(title)
    part = PART_RE.search(title)
    cache = CACHE_RE.search(title)
    rpm = RPM_RE.search(title)
    interface = INTERFACE_RE.search(title)
    model_parts = []
    if line:
        model_parts.append(line.group(1).strip())
    if part:
        model_parts.append(part.group(1).strip())
    model = " ".join(dict.fromkeys(model_parts)) or _normalize(title)[:70]

    iface = interface.group(1).upper().replace(" ", "") if interface else None
    if iface:
        iface = "SATA" if iface.startswith("SATA") else iface
        # Los discos USB suelen ser externos; BAD_RE ya filtra "externo".
        if iface.startswith("USB"):
            return None

    return {
        "brand": brand,
        "model": model,
        "line": line.group(1).strip() if line else None,
        "part": part.group(1) if part else None,
        "capacity_gb": capacity_gb,
        "tb": round(capacity_gb / 1000, 3),
        "cache": int(cache.group(1)) if cache else None,
        "inch": form_factor,
        "form_factor": form_factor,
        "interface": iface or "—",
        "rpm": int(rpm.group(1)) if rpm else None,
        "nas": bool(NAS_RE.search(title)),
        "kind": "HDD",
        "title": _normalize(title),
    }


def product_key(spec: dict) -> str:
    """Clave canónica estable entre búsquedas y tiendas.

    El número de parte manda cuando existe. Si no, se usa la línea + capacidad
    + formato; así un cambio de título comercial no crea un producto nuevo.
    """
    brand = _slug(spec.get("brand") or "sin-marca")
    line = (spec.get("line") or "").strip()
    part = (spec.get("part") or "").strip()
    # La línea comercial + capacidad + formato es más estable entre tiendas que
    # el número de parte, que unas fichas incluyen y otras no. El número de
    # parte se usa como respaldo cuando no hay línea reconocible.
    if line:
        identity = "|".join(
            str(x or "") for x in (
                line, spec.get("capacity_gb") or "", spec.get("form_factor") or "",
            )
        )
    elif part:
        identity = part
    else:
        identity = "|".join(
            str(x or "") for x in (
                spec.get("title") or "", spec.get("capacity_gb") or "",
                spec.get("form_factor") or "",
            )
        )
    return f"{brand}:{_slug(identity)}:{int(spec.get('capacity_gb') or 0)}"


def human_capacity(capacity_gb) -> str:
    try:
        gb = int(capacity_gb)
    except (TypeError, ValueError):
        return "—"
    if gb >= 1000:
        return f"{gb / 1000:g} TB"
    return f"{gb} GB"
