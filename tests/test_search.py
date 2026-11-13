"""Pruebas sin red de `run_search` y del callback de progreso.

Cubren la regresión que rompía `python nas_discos.py --once` y, con él, el
workflow diario: el callback de progreso recibe `(valor, etiqueta, tienda,
estado)` y la CLI lo ignoraba.
"""
import json
import unittest
from unittest import mock

from disksearch import search

PAGE = (
    '<script type="application/ld+json">'
    + json.dumps({
        "@type": "Product",
        "name": 'Disco Duro Seagate IronWolf 4TB 3.5" ST4000VN006',
        "brand": {"name": "Seagate"},
        "url": "/p/1",
        "offers": {"@type": "Offer", "price": "199,95", "url": "/p/1"},
    })
    + "</script>"
)


class FakeResponse:
    status_code = 200
    text = PAGE


class FakeSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, timeout=25):
        return FakeResponse()

    def close(self):
        pass


SOURCE = {
    "name": "Shop",
    "mode": "http",
    "extract": "generic",
    "urls": [{"url": "https://shop.example/cat?page={page}", "pages": 1}],
}


class SearchProgressTests(unittest.TestCase):
    def test_cli_progress_accepts_four_arguments(self):
        import nas_discos

        # Debe aceptar la firma real de run_search sin lanzar TypeError.
        nas_discos.cli_progress(0.5, "Shop · empezando", "Shop",
                                {"state": "buscando"})
        nas_discos.cli_progress(1.0, "Shop · ok")

    def test_run_search_calls_progress_with_store_and_info(self):
        seen = []

        def progress(value, label, store_name=None, info=None):
            seen.append((value, label, store_name, info))

        with mock.patch("requests.Session", FakeSession), \
                mock.patch.object(search.time, "sleep", lambda *_: None):
            data = search.run_search(progress, sources=[SOURCE])

        self.assertEqual(data["meta"]["unique"], 1)
        self.assertTrue(any(call[2] == "Shop" and call[3] for call in seen))


if __name__ == "__main__":
    unittest.main()
