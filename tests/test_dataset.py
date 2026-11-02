import json
import unittest
from pathlib import Path

from disksearch.parsing import parse_spec, product_key
from disksearch.search import build_dataset, demo_dataset


class DatasetTests(unittest.TestCase):
    def test_no_nas_requirement_and_no_capacity_limit(self):
        raw = [
            dict(name='Disco Duro Toshiba L200 500GB 2.5"', brand='Toshiba',
                 price=30.0, url='https://shop/p1', store='Shop'),
            dict(name='Seagate Exos 32TB 3.5 SATA3', brand='Seagate',
                 price=500.0, url='https://shop/p2', store='Shop'),
        ]
        data = build_dataset(raw, 1, [{"name": "Shop", "pages": 1, "items": 2, "note": "", "ok": True}])
        self.assertEqual(data["meta"]["unique"], 2)
        self.assertEqual({item["capacity_gb"] for item in data["items"]}, {500, 32000})

    def test_cheapest_offer_and_all_offers_are_kept(self):
        raw = [
            dict(name='Seagate IronWolf 4TB 3.5" ST4000VN006', brand='Seagate',
                 price=220.0, url='https://a/p', store='A'),
            dict(name='Seagate IronWolf 4TB 3.5" ST4000VN006', brand='Seagate',
                 price=200.0, url='https://b/p', store='B'),
        ]
        data = build_dataset(raw, 2, [])
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["price"], 200.0)
        self.assertEqual(item["offers"], 2)
        self.assertEqual(len(item["offers_detail"]), 2)

    def test_unknown_form_factor_merges_with_known_same_model(self):
        raw = [
            dict(name='Seagate IronWolf NAS 2 TB SATA3', brand='Seagate',
                 price=200.0, url='https://a/p', store='A'),
            dict(name='Seagate IronWolf NAS 2TB 3.5 SATA3', brand='Seagate',
                 price=206.0, url='https://b/p', store='B'),
        ]
        data = build_dataset(raw, 2, [])
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["form_factor"], "3.5")
        self.assertEqual(item["offers"], 2)
        self.assertEqual(item["price"], 200.0)

    def test_demo_regression_keeps_previous_4_to_20_tb_products(self):
        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "baseline_demo.json").read_text(encoding="utf-8")
        )
        current = demo_dataset()
        by_key = {item["key"]: item for item in current["items"]}
        for old in baseline["items"]:
            spec = parse_spec(old["title"], old["brand"])
            key = product_key(spec)
            self.assertIn(key, by_key, old["title"])
            self.assertAlmostEqual(by_key[key]["price"], old["price"], places=2)

    def test_demo_has_more_than_old_top_100_limit_and_2_5_inch(self):
        data = demo_dataset()
        self.assertGreater(len(data["items"]), 100)
        self.assertTrue(any(item["form_factor"] == "2.5" for item in data["items"]))


if __name__ == "__main__":
    unittest.main()
