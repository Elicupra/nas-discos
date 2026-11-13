import json
import unittest
from pathlib import Path

from disksearch.extractors import (
    extract_alternate, extract_amazon, extract_coolmod, extract_geeknetic,
    extract_products,
)
from disksearch.parsing import parse_spec


FIXTURES = Path(__file__).parent / "fixtures"

JSONLD = """
<script type="application/ld+json">
{"@type":"Product","name":"Seagate IronWolf 4TB 3.5\\" ST4000VN006",
 "brand":{"name":"Seagate"},"url":"/p/1",
 "offers":{"@type":"Offer","price":"199,95","url":"/p/1"},
 "aggregateRating":{"ratingValue":"4.7","reviewCount":"12"}}
</script>
"""

COOLMOD = """
<article class="product-card">
  <a href="/seagate-ironwolf-4tb/" data-itemname="Seagate IronWolf 4TB 3.5 SATA3"
     data-itemid="1" data-itemprice="199.95" data-itembrand="Seagate"></a>
</article>
<article class="product-card">
  <a href="/ssd/" data-itemname="Samsung 870 Evo 8TB 2.5"
     data-itemid="2" data-itemprice="500" data-itembrand="Samsung"></a>
</article>
"""

ALTERNATE = """
<a class="card productBox" href="/Seagate/IronWolf/html/product/1">
  <div class="product-name">Seagate IronWolf ST4000VN006 disco duro interno 4 TB 3.5"</div>
  <span class="price">€ 213,90</span>
</a>
<a class="card productBox" href="/Seagate/Expansion/html/product/2">
  <div class="product-name">Seagate Expansion 8TB disco duro externo</div>
  <span class="price">€ 180,00</span>
</a>
"""

AMAZON = """
<div data-component-type="s-search-result">
  <h2><span>Disco Duro Seagate IronWolf 4TB 3.5" ST4000VN006</span></h2>
  <span class="a-price"><span class="a-offscreen">199,95 €</span></span>
  <a class="a-link-normal" href="/dp/B000TEST01/ref=x">Ver</a>
</div>
"""


class ExtractorTests(unittest.TestCase):
    def test_jsonld(self):
        items = extract_products(JSONLD, "https://shop.example/cat", "Shop")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["price"], 199.95)
        self.assertTrue(items[0]["url"].endswith("/p/1"))

    def test_coolmod(self):
        items = extract_coolmod(COOLMOD, "https://www.coolmod.com/cat", "Coolmod")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["price"], 199.95)
        self.assertIsNotNone(parse_spec(items[0]["name"]))
        self.assertEqual(parse_spec(items[1]["name"])["kind"], "SSD")

    def test_alternate(self):
        items = extract_alternate(ALTERNATE, "https://www.alternate.es/Discos-duros", "Alternate.es")
        self.assertEqual(items[0]["price"], 213.90)
        self.assertEqual(items[0]["brand"], "")
        self.assertIsNotNone(parse_spec(items[0]["name"]))
        self.assertIsNone(parse_spec(items[1]["name"]))

    def test_amazon(self):
        items = extract_amazon(AMAZON, "https://www.amazon.es/s?k=x", "Amazon.es")
        self.assertEqual(items[0]["price"], 199.95)
        self.assertEqual(items[0]["url"], "https://www.amazon.es/dp/B000TEST01")

    def test_geeknetic_hdd_and_ssd(self):
        hdd_html = (FIXTURES / "geeknetic_hdd.html").read_text(encoding="utf-8")
        ssd_html = (FIXTURES / "geeknetic_ssd.html").read_text(encoding="utf-8")
        hdd = extract_geeknetic(hdd_html, "https://www.geeknetic.es/comparador-precios/discos-duros/", "Geeknetic · agregado")
        ssd = extract_geeknetic(ssd_html, "https://www.geeknetic.es/comparador-precios/ssds/", "Geeknetic · agregado")
        self.assertGreater(len(hdd), 30)
        self.assertGreater(len(ssd), 30)
        # Todos traen hints y URL a la ficha, nunca a ver-tienda.
        for item in hdd + ssd:
            self.assertTrue(item["hints"])
            self.assertIsNotNone(item["price"])
            self.assertNotIn("ver-tienda", item["url"])
        # Al menos un HDD 3.5" SATA y un SSD M.2 NVMe.
        self.assertTrue(any(i["hints"].get("form_factor") == "3.5" for i in hdd))
        self.assertTrue(any(i["hints"].get("interface") == "SATA" for i in hdd))
        self.assertTrue(any(i["hints"].get("form_factor") == "M.2" for i in ssd))
        self.assertTrue(any(i["hints"].get("interface") == "NVMe" for i in ssd))
        # Se integran en build_dataset con parse_spec.
        for item in hdd + ssd:
            spec = parse_spec(item["name"], item["brand"], item.get("hints"))
            self.assertIsNotNone(spec, item["name"])
            self.assertEqual(spec["kind"], item["hints"]["kind"])


if __name__ == "__main__":
    unittest.main()
