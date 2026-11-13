"""Normalización de precios, capacidades y productos."""
from __future__ import annotations

import re
import unicodedata

BRANDS = [
    "Western Digital", "Seagate", "Toshiba", "HGST", "Hitachi", "Synology",
    "QNAP", "Samsung", "Ugreen", "WD", "LaCie", "Buffalo", "Dell", "HP",
    "Kingston", "Crucial", "SanDisk", "Kioxia", "Lexar", "Intenso", "Apacer",
    "Corsair", "ADATA", "Transcend", "PNY", "Patriot", "Silicon Power",
    "Verbatim", "Sabrent", "Netac", "Micron", "Solidigm", "SK hynix",
    "Plextor", "Mushkin", "TeamGroup", "Fanxiang", "Hiksemi", "Emtec",
    "Lenovo",
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

# Un título es SSD si menciona SSD/NVMe/M.2/mSATA; el resto se trata como HDD.
SSD_HINT_RE = re.compile(r"\bssd\b|\bnvme\b|\bm\.?\s?2\b|\bmsata\b", re.I)
# Familias de SSD que aparecen en varias tiendas con nombres parecidos.
SSD_LINE_RE = re.compile(
    r"\b(990\s?PRO|990\s?EVO|980\s?PRO|980|970\s?EVO(?:\s?Plus)?|970\s?PRO|"
    r"870\s?EVO|870\s?QVO|860\s?EVO|860\s?QVO|"
    r"SN\d{3,4}[A-Z]?|SA510|NV5000|NV\d{1,4}|KC\d{3,4}|A400|Fury Renegade|"
    r"P310|P3\s?Plus|P3|P5\s?Plus|BX500|MX500|T500|T700|"
    r"Exceria(?:\s?Plus)?(?:\s?G\d)?|NQ\d{3}|NM\d{3}|"
    r"MP600(?:\s?Pro)?|S70\s?Blade|US75|S55|X150|"
    r"Optimus(?:\s?\w+){0,3})\b",
    re.I,
)

# Productos que no son discos internos (accesorios, externos, packs). El tipo
# HDD/SSD se decide después; aquí solo se descarta lo que no es un disco.
BAD_RE = re.compile(
    r"extern[oa]|external|portátil|portatil|enclosure|"
    r"carcasa|caddy|adaptador|dock|estación de acoplamiento|"
    r"cable|hdd enclosure|disco duro externo|unidad óptica|"
    r"paquete|bundle|\bpack\b|doble pack|"
    r"\b\d+x\s*\d+(?:[.,]\d+)?\s*(?:TB|GB|TO|GO|T|G)\b|"
    r"servidor nas|estación nas|todo en uno|"
    r"memoria usb|pendrive|tarjeta de memoria|"
    # Líneas comerciales de discos externos/portátiles.
    r"\bcanvio\b|\bexpansion\b|\belements\b|\bmy book\b|\bmy passport\b|"
    r"\bbackup plus\b|\bgame drive\b|\bone touch\b|\bfastwriter\b|"
    r"\bd2 professional\b|\brugged\b|\bportable\b",
    re.I,
)
HDD_HINT_RE = re.compile(
    r"disco duro|hdd|unidad de disco duro|hard drive|"
    r"ironwolf|barracuda|skyhawk|exos|ultrastar|red plus|red pro|purple|"
    r"n300|hat\d{4}|mg\d{2}|p300|s300|x300|l200",
    re.I,
)
# "To"/"Go" son las unidades que usa LDLC en su versión española. PcBox usa
# a veces "1000G" o "512 G" sin la B final.
CAP_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(TB|Tb|TO|To|T|GB|Gb|GO|Go|G)\b", re.I
)
CACHE_RE = re.compile(r"(\d{2,3})\s?MB\b", re.I)
RPM_RE = re.compile(r"(\d{4,5})\s?RPM\b", re.I)
FORM_RE = re.compile(
    r"(?<![\d.])(3[.,]5|2[.,]5)\s*(?:\"|”|''|pulgadas|\bin\b|-inch|zoll)?",
    re.I,
)
M2_RE = re.compile(r"\bm\.?\s?2\b(?:\s*(?:2[12][0-9]0))?", re.I)
MSATA_RE = re.compile(r"\bmsata\b", re.I)
INTERFACE_RE = re.compile(
    r"\b(NVMe|PCIe(?:\s?(?:Gen)?\s?[345](?:\.0)?(?:\s?x?\d+)?)?|"
    r"SATA(?:\s?III|\s?3)?|SAS|USB(?:\s?[23](?:\.\d)?)?)\b",
    re.I,
)

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
        gb = n * 1000 if unit.upper() in ("TB", "TO", "T") else n
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


def parse_spec(title: str, brand_hint: str = "", hints: dict | None = None):
    """Extrae las características de un título de HDD o SSD interno.

    ``hints`` permite a un extractor (por ejemplo el agregador Geeknetic)
    aportar capacidad, formato, tipo o interfaz cuando el título no los lleva.
    Devuelve ``None`` si no parece un disco interno. No aplica límites de
    capacidad: un disco de 500 GB o de 32 TB es igual de válido.
    """
    hints = hints or {}
    if not title or BAD_RE.search(title):
        return None

    kind = str(
        hints.get("kind")
        or ("SSD" if (SSD_HINT_RE.search(title) or SSD_LINE_RE.search(title)) else "HDD")
    ).upper()
    if kind not in ("HDD", "SSD"):
        kind = "HDD"

    capacity_gb = hints.get("capacity_gb") or parse_capacity_gb(title)
    if not capacity_gb:
        return None
    capacity_gb = int(round(float(capacity_gb)))

    form_factor = hints.get("form_factor")
    if not form_factor:
        if kind == "SSD" and MSATA_RE.search(title):
            form_factor = "mSATA"
        elif M2_RE.search(title):
            form_factor = "M.2"
        else:
            form = FORM_RE.search(title)
            if form:
                value = form.group(1).replace(",", ".")
                # Evita confundir "2.5GbE" o "3.5 Gbps" con un formato de disco.
                if value in ("2.5", "3.5") and not re.search(
                    rf"{re.escape(form.group(1))}\s*(?:Gb|Gbps|GHz)", title, re.I
                ):
                    form_factor = value
    if form_factor not in ("2.5", "3.5", "M.2", "mSATA"):
        form_factor = None

    if kind == "HDD":
        if not form_factor and not HDD_HINT_RE.search(title):
            return None
        # Heurística conservadora: estas gamas de NAS/empresa son de 3,5"
        # cuando la ficha omite el formato y la capacidad es de escritorio.
        if not form_factor and capacity_gb >= 4000 and re.search(
            r"ironwolf|red (?:plus|pro)|\bred\b|n300|exos|ultrastar|"
            r"skyhawk|purple|hat\d{4}|mg\d{2}",
            title, re.I,
        ):
            form_factor = "3.5"

    brand = detect_brand(title, brand_hint)
    line = (SSD_LINE_RE if kind == "SSD" else LINE_RE).search(title)
    part = None if kind == "SSD" else PART_RE.search(title)
    cache = CACHE_RE.search(title)
    rpm = RPM_RE.search(title) if kind == "HDD" else None

    model_parts = []
    if line:
        model_parts.append(line.group(1).strip())
    if part:
        model_parts.append(part.group(1).strip())
    model = " ".join(dict.fromkeys(model_parts)) or _normalize(title)[:70]
    if kind == "SSD" and not model_parts:
        model = f"{model[:60]} · {human_capacity(capacity_gb)}"

    if hints.get("interface"):
        iface = str(hints["interface"])
    elif re.search(r"\bnvme\b", title, re.I):
        iface = "NVMe"
    elif re.search(r"\bpcie\b", title, re.I):
        iface = "PCIe"
    elif re.search(r"\bsata(?:\s?III|\s?3)?\b", title, re.I):
        iface = "SATA"
    elif re.search(r"\bsas\b", title, re.I):
        iface = "SAS"
    elif re.search(r"\busb\b", title, re.I):
        # Los discos USB suelen ser externos; BAD_RE ya filtra "externo".
        return None
    else:
        iface = "—"

    return {
        "brand": brand,
        "model": model,
        "line": line.group(1).strip() if line else None,
        "part": part.group(1) if part else None,
        "capacity_gb": capacity_gb,
        "tb": round(capacity_gb / 1000, 3),
        "cache": int(cache.group(1)) if cache else None,
        "inch": form_factor if form_factor in ("2.5", "3.5") else None,
        "form_factor": form_factor,
        "interface": iface,
        "rpm": int(rpm.group(1)) if rpm else None,
        "nas": bool(NAS_RE.search(title)),
        "kind": kind,
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
    key = f"{brand}:{_slug(identity)}:{int(spec.get('capacity_gb') or 0)}"
    # El sufijo solo se añade a los SSD: las claves HDD ya guardadas no cambian.
    if str(spec.get("kind") or "HDD").upper() == "SSD":
        key += ":ssd"
    return key


def human_capacity(capacity_gb) -> str:
    try:
        gb = int(capacity_gb)
    except (TypeError, ValueError):
        return "—"
    if gb >= 1000:
        return f"{gb / 1000:g} TB"
    return f"{gb} GB"
