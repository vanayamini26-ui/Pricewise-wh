"""Unit tests for the matching logic. Titles below are hand-written samples that
imitate how Amazon/Flipkart format titles; they are test inputs only and are
never shown in the app."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from matching import *  # noqa: E402,F401,F403


class T(unittest.TestCase):
    def test_parse(self):
        s = parse_title("Apple iPhone 15 (128 GB) - Black")
        self.assertEqual((s.brand, s.storage, s.ident), ("apple", 128, frozenset({"15"})))

    def test_same_variant_pairs(self):
        a = parse_title("Apple iPhone 15 (128 GB) - Black")
        f = parse_title("Apple iPhone 15 (Blue, 128 GB)")
        self.assertGreaterEqual(pair_score(a, f), 0.6)

    def test_samsung_pairs(self):
        a = parse_title("Samsung Galaxy S24 5G AI Smartphone (Onyx Black, 8GB, 128GB Storage)")
        f = parse_title("SAMSUNG Galaxy S24 5G (Marble Gray, 128 GB)")
        self.assertGreaterEqual(pair_score(a, f), 0.6)

    def test_pro_not_paired(self):
        self.assertEqual(pair_score(parse_title("Apple iPhone 15 (128 GB)"),
                                    parse_title("Apple iPhone 15 Pro (128 GB)")), 0)

    def test_storage_not_paired(self):
        self.assertEqual(pair_score(parse_title("Apple iPhone 15 (128 GB)"),
                                    parse_title("Apple iPhone 15 (256 GB)")), 0)

    def test_model_not_paired(self):
        self.assertEqual(pair_score(parse_title("Samsung Galaxy S24 (128 GB)"),
                                    parse_title("Samsung Galaxy S23 (128 GB)")), 0)

    def test_relevance(self):
        q = parse_title("iPhone 15 128GB")
        self.assertTrue(is_relevant(q, parse_title("Apple iPhone 15 (128 GB) - Black")))
        self.assertFalse(is_relevant(q, parse_title("Apple iPhone 15 Plus (128 GB)")))
        self.assertFalse(is_relevant(q, parse_title("Apple iPhone 15 (256 GB)")))
        self.assertFalse(is_relevant(q, parse_title("Samsung Galaxy S24 (128 GB)")))

    def test_laptop_memory(self):
        s = parse_title("HP Pavilion 15 Intel Core i5 16GB RAM 512GB SSD Windows 11 Laptop")
        self.assertEqual((s.ram, s.storage), (16, 512))
        s = parse_title("Dell Inspiron (16GB/512GB SSD)")
        self.assertEqual((s.ram, s.storage), (16, 512))

    def test_accessories(self):
        self.assertTrue(is_accessory("Spigen Case for iPhone 15", "iphone 15"))
        self.assertTrue(is_accessory("Tempered Glass Screen Protector iPhone 15", "iphone 15"))
        self.assertFalse(is_accessory("Apple iPhone 15 (128 GB)", "iphone 15"))
        self.assertFalse(is_accessory("Apple 20W USB-C Charger", "apple charger"))

    def test_electronics_filter(self):
        self.assertFalse(is_electronic("Men's Cotton Shirt"))
        self.assertFalse(query_is_allowed("running shoes"))
        self.assertTrue(is_electronic("boAt Rockerz 450 Bluetooth Headphones"))
        self.assertTrue(is_electronic("Samsung Galaxy S24"))


if __name__ == "__main__":
    unittest.main()
