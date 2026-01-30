"""Tests for number normalization."""

import unittest
from music_metrics_collector.normalizer import normalize_number, extract_number_from_text


class TestNormalizer(unittest.TestCase):
    """Test cases for number normalization."""
    
    def test_normalize_with_commas(self):
        """Test normalization of numbers with commas."""
        self.assertEqual(normalize_number("1,234,567"), 1234567)
        self.assertEqual(normalize_number("123,456"), 123456)
        self.assertEqual(normalize_number("1,234"), 1234)
    
    def test_normalize_korean_man(self):
        """Test normalization of Korean '만' (10,000)."""
        self.assertEqual(normalize_number("12.3만"), 123000)
        self.assertEqual(normalize_number("1만"), 10000)
        self.assertEqual(normalize_number("100만"), 1000000)
        self.assertEqual(normalize_number("12만"), 120000)
    
    def test_normalize_million(self):
        """Test normalization of 'M' (million)."""
        self.assertEqual(normalize_number("1.2M"), 1200000)
        self.assertEqual(normalize_number("1M"), 1000000)
        self.assertEqual(normalize_number("12.5M"), 12500000)
    
    def test_normalize_thousand(self):
        """Test normalization of 'K' (thousand)."""
        self.assertEqual(normalize_number("1.2K"), 1200)
        self.assertEqual(normalize_number("12K"), 12000)
        self.assertEqual(normalize_number("1K"), 1000)
    
    def test_normalize_plain_number(self):
        """Test normalization of plain numbers."""
        self.assertEqual(normalize_number("1234567"), 1234567)
        self.assertEqual(normalize_number("123"), 123)
        self.assertEqual(normalize_number("0"), 0)
    
    def test_normalize_invalid(self):
        """Test normalization of invalid inputs."""
        self.assertIsNone(normalize_number(""))
        self.assertIsNone(normalize_number("abc"))
        self.assertIsNone(normalize_number("no numbers here"))
    
    def test_extract_number_from_text(self):
        """Test extracting numbers from text."""
        self.assertEqual(extract_number_from_text("재생수: 1,234,567"), 1234567)
        self.assertEqual(extract_number_from_text("12.3만회"), 123000)
        self.assertEqual(extract_number_from_text("Total: 1.2M plays"), 1200000)
        self.assertEqual(extract_number_from_text("1234"), 1234)


if __name__ == '__main__':
    unittest.main()

