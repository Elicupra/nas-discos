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

    def test_rejects_external_and_bundles(self):
        for title in [
            'Disco duro externo WD 4TB USB 3.0',
            'Seagate Expansion 8TB 3.5',
            'Toshiba Canvio Flex 4TB',
            'Ugreen DXP2800 + 2x 6 TB NAS',
            'Samsung T7 Shield SSD externo 2TB',
        ]:
            self.assertIsNone(parse_spec(title), title)

    def test_accepts_internal_ssd_sata_and_m2(self):
        for title, capacity, form, iface in [
            ('Samsung 990 PRO 2TB SSD M.2 NVMe PCIe 4.0', 2000, 'M.2', 'NVMe'),
            ('Disco Duro 480GB 2.5" KINGSTON SSD SATA3 A400', 480, '2.5', 'SATA'),
            ('KINGSTON 1000G NV3 M.2 2280 NVMe SSD 6000MB/s', 1000, 'M.2', 'NVMe'),
            ('WD Blue SA510 2.5" 500GB SSD SATA 3', 500, '2.5', 'SATA'),
            ('KINGSTON Disco SSD KC600 SATA3 mSATA de 512 G', 512, 'mSATA', 'SATA'),
        ]:
            spec = parse_spec(title)
            self.assertIsNotNone(spec, title)
            self.assertEqual(spec["kind"], "SSD", title)
            self.assertEqual(spec["capacity_gb"], capacity, title)
            self.assertEqual(spec["form_factor"], form, title)
            self.assertEqual(spec["interface"], iface, title)

    def test_ssd_and_hdd_do_not_share_key(self):
        hdd = parse_spec('Toshiba P300 4TB 3.5" SATA3')
        ssd = parse_spec('Samsung 990 PRO 4TB SSD M.2 NVMe')
        self.assertEqual(hdd["kind"], "HDD")
        self.assertEqual(ssd["kind"], "SSD")
        self.assertFalse(product_key(hdd).endswith(":ssd"))
        self.assertTrue(product_key(ssd).endswith(":ssd"))
        self.assertNotEqual(product_key(hdd), product_key(ssd))

    def test_hdd_key_stays_stable(self):
        spec = parse_spec('Disco Duro Toshiba L200 500GB 2.5"')
        self.assertEqual(product_key(spec), "toshiba:l200-500-2-5:500")

    def test_key_stable_with_part_number(self):
        a = parse_spec('Seagate IronWolf 4TB 3.5" ST4000VN006')
        b = parse_spec('DISCO DURO SEAGATE IRONWOLF 4000GB 3.5 ST4000VN006')
        self.assertEqual(product_key(a), product_key(b))


if __name__ == "__main__":
    unittest.main()
