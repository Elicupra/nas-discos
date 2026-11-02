import unittest

from disksearch.parsing import (
    parse_capacity_gb, parse_price, parse_spec, product_key,
)


class ParsingTests(unittest.TestCase):
    def test_prices(self):
        self.assertEqual(parse_price("1.234,56 €"), 1234.56)
        self.assertEqual(parse_price("€ 213,90"), 213.90)
        self.assertEqual(parse_price("149.95"), 149.95)
        self.assertIsNone(parse_price(""))

    def test_capacity_without_bounds(self):
        self.assertEqual(parse_capacity_gb("Disco 500GB"), 500)
        self.assertEqual(parse_capacity_gb("Disco 1,92TB"), 1920)
        self.assertEqual(parse_capacity_gb("Disco 32TB"), 32000)
        self.assertEqual(parse_capacity_gb("Toshiba L200 2 To"), 2000)

    def test_accepts_small_and_large_internal_hdd(self):
        for title, capacity in [
            ('Disco Duro Toshiba L200 500GB 2.5"', 500),
            ('Disco Duro Seagate IronWolf 4TB 3.5" ST4000VN006', 4000),
            ('Seagate Exos 32TB 3.5 SATA3', 32000),
        ]:
            spec = parse_spec(title)
            self.assertIsNotNone(spec, title)
            self.assertEqual(spec["capacity_gb"], capacity)

    def test_rejects_ssd_external_and_bundles(self):
        for title in [
            'Samsung 870 Evo 8TB 2.5 SATA3',
            'Disco duro externo WD 4TB USB 3.0',
            'Seagate Expansion 8TB 3.5',
            'Toshiba Canvio Flex 4TB',
            'Ugreen DXP2800 + 2x 6 TB NAS',
            'Dell 480GB SSD SATA',
        ]:
            self.assertIsNone(parse_spec(title), title)

    def test_key_stable_with_part_number(self):
        a = parse_spec('Seagate IronWolf 4TB 3.5" ST4000VN006')
        b = parse_spec('DISCO DURO SEAGATE IRONWOLF 4000GB 3.5 ST4000VN006')
        self.assertEqual(product_key(a), product_key(b))


if __name__ == "__main__":
    unittest.main()
