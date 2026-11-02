import json
import unittest

from disksearch.extractors import (
    extract_alternate, extract_amazon, extract_coolmod, extract_products,
)
from disksearch.parsing import parse_spec


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
        self.assertIsNone(parse_spec(items[1]["name"]))

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


if __name__ == "__main__":
    unittest.main()
