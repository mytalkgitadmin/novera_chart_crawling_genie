"""Tests for GENIE parser."""

import unittest
from music_metrics_collector.collectors.genie import GenieCollector
from music_metrics_collector.fetcher import Fetcher
from music_metrics_collector.models import TrackInfo


class TestGenieParser(unittest.TestCase):
    """Test cases for GENIE parser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.fetcher = Fetcher(mode="requests", timeout_sec=10)
        self.collector = GenieCollector(self.fetcher)
    
    def test_build_url(self):
        """Test URL building."""
        url = self.collector.build_url("12345678")
        self.assertIn("genie.co.kr", url)
        self.assertIn("12345678", url)
    
    def test_parse_metrics_sample_html(self):
        """Test parsing metrics from sample HTML."""
        # Sample HTML structure (simplified)
        html = """
        <html>
        <body>
            <div class="song-info">
                <dl class="info-list">
                    <dd class="value">1,234,567</dd>
                </dl>
            </div>
            <div class="song-info">
                <dl class="info-list">
                    <dd class="value">987,654</dd>
                </dl>
            </div>
        </body>
        </html>
        """
        
        result = self.collector.parse_metrics(html)
        # Should extract numbers even if not perfectly structured
        # This is a basic test - actual parsing may need adjustment based on real HTML
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'total_plays'))
        self.assertTrue(hasattr(result, 'total_listeners'))
    
    def test_parse_metrics_with_korean_units(self):
        """Test parsing metrics with Korean units."""
        html = """
        <html>
        <body>
            <div>재생수: 12.3만</div>
            <div>청취자수: 5.6만</div>
        </body>
        </html>
        """
        
        result = self.collector.parse_metrics(html)
        self.assertIsNotNone(result)
    
    def tearDown(self):
        """Clean up."""
        self.fetcher.close()


if __name__ == '__main__':
    unittest.main()

