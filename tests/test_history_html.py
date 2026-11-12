"""Pruebas del generador de página estática del histórico (SPEC_8)."""
import json
import re
import unittest

from disksearch.history import HistoryStore
from disksearch.search import demo_dataset
from disksearch.ui import render_history_html


class TestHistoricoHtml(unittest.TestCase):
    def test_genera_html_con_historico(self):
        store = HistoryStore(":memory:")
        store.record_search(demo_dataset())
        html = render_history_html(store)
        self.assertIn("const BOOT=", html)
        match = re.search(r"const BOOT=(\{.*?\});\s*\n", html, re.S)
        self.assertIsNotNone(match, "el HTML debe embeber el histórico como const BOOT=")
        boot = json.loads(match.group(1))
        self.assertGreater(boot.get("total", 0), 0)
        self.assertGreater(len(boot.get("items", [])), 0)
        # la tabla de histórico y los datos están, sin dependencias de red
        self.assertIn('id="hrows"', html)
        self.assertNotIn("http://localhost", html)

    def test_cli_flag_genera_archivo(self):
        import pathlib
        import subprocess
        import sys
        import tempfile

        store = HistoryStore(":memory:")
        store.record_search(demo_dataset())
        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "history.sqlite3"
            store2 = HistoryStore(str(db))
            store2.record_search(demo_dataset())
            store2.close()
            salida = pathlib.Path(tmp) / "historico.html"
            result = subprocess.run(
                [sys.executable, "nas_discos.py", "--historico-html", str(salida),
                 "--db", str(db)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(salida.exists())
            html = salida.read_text(encoding="utf-8")
            self.assertIn("Histórico", html)

    def test_null_store_genera_pagina_vacia(self):
        from disksearch.ui import history_snapshot, render_history_html

        html = render_history_html(None)
        self.assertIn("const BOOT=", html)
        self.assertIn('id="hrows"', html)


if __name__ == "__main__":
    unittest.main()
