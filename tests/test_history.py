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


def make_partial(data, summary="SSD"):
    """Marca un dataset como búsqueda acotada (no detecta ausencias)."""
    data["meta"]["partial"] = True
    data["meta"]["scope"] = summary
    return data


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

    def test_list_products_and_series_include_kind(self):
        raw = [
            dict(name='Seagate IronWolf 4TB 3.5" ST4000VN006', brand='Seagate',
                 price=100.0, url='https://shop/hdd', store='Shop'),
            dict(name='Samsung 990 PRO 2TB SSD M.2 NVMe', brand='Samsung',
                 price=150.0, url='https://shop/ssd', store='Shop'),
        ]
        data = build_dataset(
            raw, 1,
            [{"name": "Shop", "pages": 1, "items": 2, "note": "", "ok": True}],
        )
        self.store.record_search(data)
        hdd = self.store.list_products(kind="HDD")
        ssd = self.store.list_products(kind="SSD")
        self.assertEqual(hdd["total"], 1)
        self.assertEqual(ssd["total"], 1)
        self.assertEqual(hdd["items"][0]["kind"], "HDD")
        self.assertEqual(ssd["items"][0]["kind"], "SSD")
        self.assertEqual({s["kind"] for s in self.store.price_series()}, {"HDD", "SSD"})

    def test_partial_search_updates_and_never_marks_missing(self):
        first = make_data([4, 8])
        self.store.record_search(first)
        key_a = next(item["key"] for item in first["items"] if item["capacity_gb"] == 4000)
        self.store.set_favorite(key_a, True)

        # Dos búsquedas acotadas seguidas que no incluyen el 4 TB.
        for _ in range(3):
            partial = make_partial(make_data([8], price_offset=5))
            self.store.record_search(partial)

        # El producto ausente sigue disponible y no ha generado avisos.
        product = self.store.get_product(key_a)["product"]
        self.assertEqual(product["available"], 1)
        self.assertEqual(product["favorite"], 1)
        self.assertEqual(self.store.stats()["missing"], 0)
        self.assertEqual(self.store.notifications(), [])

        # El producto que sí entra en el ámbito se ha actualizado: sube el
        # último precio pero se conserva el mejor histórico.
        key_b = next(item["key"] for item in first["items"] if item["capacity_gb"] == 8000)
        updated = self.store.get_product(key_b)["product"]
        self.assertAlmostEqual(updated["last_price"], 113.0, places=2)
        self.assertAlmostEqual(updated["best_price"], 108.0, places=2)

    def test_partial_search_inserts_new_products(self):
        self.store.record_search(make_partial(make_data([4, 8])))
        listing = self.store.list_products()
        self.assertEqual(listing["total"], 2)

    def test_complete_search_after_partial_still_detects_missing(self):
        first = make_data([4, 8])
        self.store.record_search(first)
        key_a = next(item["key"] for item in first["items"] if item["capacity_gb"] == 4000)
        self.store.set_favorite(key_a, True)

        # La acotada no marca ausencia.
        self.store.record_search(make_partial(make_data([8])))
        self.assertEqual(self.store.get_product(key_a)["product"]["available"], 1)

        # Dos completas sin el 4 TB sí lo marcan.
        self.store.record_search(make_data([8]))
        self.store.record_search(make_data([8]))
        self.assertEqual(self.store.get_product(key_a)["product"]["available"], 0)

    def test_searches_record_scope(self):
        self.store.record_search(make_partial(make_data([8]), summary="SSD · 1 tienda"))
        recent = self.store.recent_searches()
        self.assertIn("scope_json", recent[0])
        self.assertIn("SSD", recent[0]["scope_json"])

    def test_old_schema_without_scope_column_still_records(self):
        """Una base antigua sin scope_json debe seguir funcionando."""
        with self.store._connect() as conn:
            conn.execute("ALTER TABLE searches DROP COLUMN scope_json")
        self.store.record_search(make_data([8]))
        self.assertEqual(len(self.store.recent_searches()), 1)

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
