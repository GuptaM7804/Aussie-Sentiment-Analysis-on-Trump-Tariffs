import unittest
import json
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))
import harvest

class TestLoadKeywords(unittest.TestCase):

    def setUp(self):
        self.valid_keywords = {"keywords": ["trump", "tariffs"]}
        self.valid_file = "test_keywords.json"
        self.invalid_json_file = "invalid_keywords.json"
        self.bad_format_file = "test_keywords.txt"
        self.nonexistent_file = "nonexistent.json"

        with open(self.valid_file, "w") as f:
            json.dump(self.valid_keywords, f)

        with open(self.invalid_json_file, "w") as f:
            f.write("not a json")

        with open(self.bad_format_file, "w") as f:
            f.write("trump, tariffs")

    def tearDown(self):
        for f in [self.valid_file, self.invalid_json_file, self.bad_format_file]:
            if os.path.exists(f):
                os.remove(f)

    def test_valid_keywords_file(self):
        keywords = harvest.load_keywords(self.valid_file)
        self.assertEqual(keywords, ["trump", "tariffs"])

    def test_missing_file(self):
        keywords = harvest.load_keywords(self.nonexistent_file)
        self.assertEqual(keywords, [])

    def test_invalid_json(self):
        keywords = harvest.load_keywords(self.invalid_json_file)
        self.assertEqual(keywords, [])

    def test_wrong_format_file(self):
        with self.assertRaises(ValueError):
            harvest.load_keywords(self.bad_format_file)

class TestFetchReddit(unittest.TestCase):

    @patch("harvest.praw.Reddit")
    def test_fetch_reddit_data(self, mock_reddit):
        mock_submission = MagicMock()
        mock_submission.selftext = "Sample text"
        mock_submission.title = "Sample title"
        mock_submission.created_utc = 1680000000
        mock_submission.author.name = "user123"
        mock_submission.comments.list.return_value = []
        mock_subreddit = MagicMock()
        mock_subreddit.search.return_value = [mock_submission]
        mock_reddit.return_value.subreddit.return_value = mock_subreddit

        results = harvest.fetch_reddit_data(["trump"], ["australia"], mock_reddit.return_value, post_limit=1, comments_per_post_limit=0)
        self.assertIsInstance(results, int)
        self.assertGreaterEqual(results, 1)

class TestFetchMastodon(unittest.TestCase):
    
    @patch("harvest.helpers.bulk")  # Patch the Elasticsearch bulk upload
    @patch("harvest.Mastodon")
    def test_fetch_mastodon_data(self, mock_mastodon, mock_bulk):
        # Make bulk upload succeed silently
        mock_bulk.return_value = (True, [])

        mock_client = MagicMock()
        mock_client.api_base_url = "https://mastodon.au"
        mock_client.search.return_value = {
            "statuses": [
                {
                    "created_at": "2024-04-01T12:00:00Z",
                    "content": "Test toot",
                    "account": {"username": "tester"}
                }
            ]
        }
        mock_mastodon.return_value = mock_client

        results = harvest.fetch_mastodon_data(["tariffs"], mock_client, max_results=1)
        self.assertIsInstance(results, int)
        self.assertEqual(results, 1)

class TestHandler(unittest.TestCase):

    @patch("harvest.fetch_reddit_data")
    @patch("harvest.initialize_reddit")
    @patch("harvest.load_keywords")
    def test_handler_reddit(self, mock_keywords, mock_init_reddit, mock_fetch_reddit):
        mock_keywords.return_value = ["trump"]
        mock_fetch_reddit.return_value = 1
        mock_init_reddit.return_value = MagicMock()

        result = harvest.handler(None, type("Event", (), {"body": json.dumps({"platform": "reddit"})}))
        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["total_items_processed_for_es"], 1)

    @patch("harvest.fetch_mastodon_data")
    @patch("harvest.load_keywords")
    def test_handler_mastodon(self, mock_keywords, mock_fetch_masto):
        mock_keywords.return_value = ["tariffs"]
        mock_fetch_masto.return_value = 1

        result = harvest.handler(None, type("Event", (), {"body": json.dumps({"platform": "mastodon"})}))
        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["total_items_processed_for_es"], 1)

    def test_handler_with_empty_keywords(self):
        event = type("Event", (), {"body": json.dumps({"platform": "reddit", "keywords": []})})
        result = harvest.handler(None, event)
        self.assertEqual(result["status"], "error")

class TestElasticsearchUpload(unittest.TestCase):

    @patch("harvest.helpers.bulk")
    @patch("harvest.Elasticsearch")
    def test_upload_to_elasticsearch(self, mock_es, mock_bulk):
        mock_bulk.return_value = (5, [])
        docs = [{"content": "test", "platform": "reddit"} for _ in range(5)]
        harvest.upload_to_elasticsearch(docs)
        mock_bulk.assert_called_once()

    @patch("harvest.helpers.bulk")
    @patch("harvest.Elasticsearch")
    def test_upload_empty_docs(self, mock_es, mock_bulk):
        docs = []
        harvest.upload_to_elasticsearch(docs)
        mock_bulk.assert_not_called()


if __name__ == "__main__":
    unittest.main()
