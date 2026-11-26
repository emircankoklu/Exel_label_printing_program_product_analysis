import unittest

import pandas as pd

from fisv9 import _group_products, _printer_bytes


class ProductGroupingTests(unittest.TestCase):
    def test_merges_duplicate_price_rows_and_classifies_old_and_new(self):
        dataframe = pd.DataFrame(
            [
                ["123456", " Ürün A ", "1.00", "2.00", "3"],
                ["123456", "Ürün A", "1.20", "2.00", "2"],
                ["123456", "Ürün A", "1.50", "2.50", "4"],
            ],
            columns=["Barkodu", "Ürün Adı", "Alış Fiyatı", "Satış Fiyatı", "Kalan"],
        )

        products = _group_products(dataframe)

        self.assertEqual(len(products), 1)
        product = products[0]
        self.assertEqual(product["Parti_Durumu"], "Fiyatı değişen")
        self.assertEqual(product["Eski_Fiyat"], 2.0)
        self.assertEqual(product["Yeni_Fiyat"], 2.5)
        self.assertEqual([batch["adet"] for batch in product["Fiyatlar"]], [5, 4])

    def test_single_price_is_kept_in_its_own_category(self):
        dataframe = pd.DataFrame(
            [["987654", "Ürün B", 4.25]],
            columns=["Barkod", "Ürün Adı", "Satış Fiyatı"],
        )

        product = _group_products(dataframe)[0]

        self.assertEqual(product["Parti_Durumu"], "Tek fiyat")
        self.assertEqual(product["Eski_Fiyat"], product["Yeni_Fiyat"])

    def test_keeps_intermediate_prices_for_manual_selection(self):
        dataframe = pd.DataFrame(
            [
                ["123456", "Ürün C", 2.00, 2],
                ["123456", "Ürün C", 2.25, 3],
                ["123456", "Ürün C", 2.50, 4],
            ],
            columns=["Barkod", "Ürün Adı", "Satış Fiyatı", "Kalan"],
        )

        product = _group_products(dataframe)[0]

        self.assertEqual(
            [batch["fiyat"] for batch in product["Fiyatlar"]],
            [2.0, 2.25, 2.5],
        )


class PrinterPayloadTests(unittest.TestCase):
    def test_generates_selected_language_and_respects_label_limit(self):
        payload, count = _printer_bytes(
            [{"barcode": "123456", "name": "Kahve", "price": "12,50", "quantity": 2}],
            "zpl",
        )

        self.assertEqual(count, 2)
        self.assertEqual(payload.count(b"^XA"), 2)
        self.assertIn(b"12.50", payload)

        with self.assertRaisesRegex(ValueError, "en fazla"):
            _printer_bytes(
                [{"barcode": "123456", "name": "Kahve", "price": 12, "quantity": 501}],
                "zpl",
            )

    def test_rejects_unknown_printer_language(self):
        with self.assertRaisesRegex(ValueError, "Yazıcı dili"):
            _printer_bytes(
                [{"barcode": "123456", "name": "Kahve", "price": 12, "quantity": 1}],
                "unknown",
            )

    def test_zpl_data_cannot_inject_printer_control_sequences(self):
        payload, _ = _printer_bytes(
            [{"barcode": "123^XA~", "name": "Ürün^FS~", "price": 12, "quantity": 1}],
            "zpl",
        )

        self.assertNotIn(b"123^XA~", payload)
        self.assertNotIn("Ürün^FS~".encode("utf-8"), payload)


if __name__ == "__main__":
    unittest.main()
