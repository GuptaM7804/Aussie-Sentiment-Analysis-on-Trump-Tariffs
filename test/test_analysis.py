import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend')))
import analysis_utils

class TestAnalysisUtils(unittest.TestCase):

    def test_clean_text(self):
        raw_text = "Visit https://example.com! Thanks for the info."
        result = analysis_utils.clean_text(raw_text)
        self.assertEqual(result, "Visit Thanks for the info.")

    def test_analyse_sentiment_positive(self):
        result = analysis_utils.analyse_sentiment("What a wonderful experience!")
        self.assertEqual(result['sentiment'], 'positive')
        self.assertGreater(result['total_sentiment'], 0)

    def test_analyse_sentiment_negative(self):
        result = analysis_utils.analyse_sentiment("This is terrible and I hate it.")
        self.assertEqual(result['sentiment'], 'negative')
        self.assertLess(result['total_sentiment'], 0)

    def test_analyse_sentiment_neutral(self):
        text = "It is a book."
        result = analysis_utils.analyse_sentiment(text)
        self.assertEqual(result['sentiment'], 'neutral')

    def test_process_item_valid(self):
        item = {
            "_id": "reddit_comment_123",
            "platform": "reddit",
            "source": "australia",
            "content": "I love this place!",
            "timestamp": "2024-01-01T12:00:00Z",
            "author": "test_user",
            "reddit_id": "abc123",
            "parent_post_id": "xyz456"
        }
        result = analysis_utils.process_item(item)
        self.assertEqual(result['platform'], "reddit")
        self.assertEqual(result['type'], "comment")
        self.assertIn('sentiment', result)

    def test_process_item_missing_required_fields(self):
        item = {"content": "Just a text"}
        result = analysis_utils.process_item(item)
        self.assertIsNone(result)

    def test_preprocess_data(self):
        records = [
            {
                "_id": "reddit_post_1",
                "platform": "reddit",
                "source": "australia",
                "content": "I love the beaches!",
                "timestamp": "2024-01-01T00:00:00Z",
                "author": "user1",
                "reddit_id": "r123",
                "parent_post_id": None
            },
            {
                "_id": "reddit_comment_2",
                "platform": "reddit",
                "source": "australia",
                "content": "Terrible weather today.",
                "timestamp": "2024-01-02T00:00:00Z",
                "author": "user2",
                "reddit_id": "r456",
                "parent_post_id": "p789"
            }
        ]
        result = analysis_utils.preprocess_data(records)
        self.assertEqual(len(result), 2)
        self.assertTrue(all('sentiment' in r for r in result))

    @patch('analysis_utils.requests.post')
    def test_fetch_data_from_index_mocked(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"content": "mock text", "source": "mock_source"}, "_id": "mock_id_1"}
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = analysis_utils.fetch_data_from_index("mock_index", size=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['_id'], 'mock_id_1')

if __name__ == '__main__':
    unittest.main()
