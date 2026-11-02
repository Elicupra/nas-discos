import tempfile
import unittest
from pathlib import Path

from disksearch.history import HistoryStore
from disksearch.search import build_dataset


def make_data(capacities, store="Shop", ok=True, price_offset=0):
    raw = []
    for tb in capacities:
        raw.append(dict(
            name=f'Seagate IronWolf {tb}TB 3.5" ST{tb * 1000}VN006',
            brand="Seagate", price=100.0 + tb + price_offset,
            url=f"https://{store.lower()}.example/{tb}", store=store,
        ))
    return build_dataset(
        raw, 1,
        [{"name": store, "pages": 1, "items": len(raw), "note": "", "ok": ok}],
    )


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.tmp.name) / "history.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_favorites_and_listing(self):
        data = make_data([4, 8])
        self.store.record_search(data)
        key = data["items"][1]["key"]
        self.assertTrue(self.store.set_favorite(key, True))
        self.assertEqual(self.store.favorites(), [key])
        listing = self.store.list_products(favorites=True)
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["items"][0]["key"], key)
        self.assertEqual(self.store.stats()["favorites"], 1)

    def test_missing_after_two_reliable_searches_and_back(self):
        first = make_data([4, 8])
        self.store.record_search(first)
        key_a = next(item["key"] for item in first["items"] if item["capacity_gb"] == 4000)
        self.store.set_favorite(key_a, True)

        # Primera ausencia: todavía disponible.
        second = make_data([8])
        self.store.record_search(second)
        product = self.store.get_product(key_a)["product"]
        self.assertEqual(product["available"], 1)
        self.assertEqual(self.store.stats()["missing"], 0)

        # Segunda ausencia fiable: desaparece y genera aviso no intrusivo.
        third = make_data([8])
        self.store.record_search(third)
        product = self.store.get_product(key_a)["product"]
        self.assertEqual(product["available"], 0)
        self.assertIsNotNone(product["missing_since"])
        self.assertEqual(self.store.stats()["missing"], 1)
        notices = self.store.notifications()
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["kind"], "missing")
        self.assertIn("ya no aparece", notices[0]["message"])

        # Reaparición: vuelve a estar disponible y se avisa.
        fourth = make_data([4, 8], price_offset=5)
        self.store.record_search(fourth)
        product = self.store.get_product(key_a)["product"]
        self.assertEqual(product["available"], 1)
        self.assertIsNone(product["missing_since"])
        self.assertEqual(self.store.stats()["missing"], 0)
        kinds = [notice["kind"] for notice in self.store.notifications()]
        self.assertIn("back", kinds)

        detail = self.store.get_product(key_a)
        self.assertGreaterEqual(len(detail["offers"]), 1)
        self.assertGreaterEqual(len(detail["price_history"]), 1)

    def test_blocked_source_does_not_mark_missing(self):
        first = make_data([4])
        self.store.record_search(first)
        key = first["items"][0]["key"]
        # Dos búsquedas sin productos y con la fuente no fiable.
        for _ in range(2):
            self.store.record_search(make_data([], ok=False))
        product = self.store.get_product(key)["product"]
        self.assertEqual(product["available"], 1)

    def test_dismiss_notification(self):
        first = make_data([4])
        self.store.record_search(first)
        key = first["items"][0]["key"]
        self.store.set_favorite(key, True)
        self.store.record_search(make_data([8]))
        self.store.record_search(make_data([8]))
        notice = self.store.notifications()[0]
        self.assertTrue(self.store.dismiss_notification(notice["id"]))
        self.assertEqual(self.store.notifications(), [])
        self.assertEqual(self.store.stats()["notifications"], 0)


if __name__ == "__main__":
    unittest.main()
