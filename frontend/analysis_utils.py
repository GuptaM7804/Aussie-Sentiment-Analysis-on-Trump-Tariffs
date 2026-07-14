import json
import pandas as pd
from textblob import TextBlob
import matplotlib.pyplot as plt
import seaborn as sns
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
vader = SentimentIntensityAnalyzer()
from elasticsearch import Elasticsearch
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from dateutil import parser

def fetch_data_from_index(index_name, size=10000):
    url = f"https://elasticsearch-master.elastic.svc.cluster.local:9200/{index_name}/_search?pretty"  
    payload = {"size": size, "query": {"match_all": {}}}
    resp = requests.post(url, auth=("elastic","elastic"), json=payload, verify=False)
    resp.raise_for_status()
    hits = resp.json()["hits"]["hits"]
    records = []

    for hit in hits:
        record = hit["_source"]
        record["_id"] = hit["_id"]  
        records.append(record)
    return records

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def analyse_sentiment(text):
    try:
        textblob_sentiment = TextBlob(text).sentiment.polarity
        vader_sentiment = vader.polarity_scores(text)['compound']
        subjectivity = TextBlob(text).sentiment.subjectivity
        total_sentiment = (textblob_sentiment + vader_sentiment) / 2
        return {
            'textblob_sentiment': textblob_sentiment,
            'vader_sentiment': vader_sentiment,
            'total_sentiment': total_sentiment,
            'subjectivity': subjectivity,
            'sentiment': 'positive' if total_sentiment > 0 else 'negative' if total_sentiment < 0 else 'neutral'
        }
    except Exception as e:
        print(f"[ERROR] Sentiment analysis failed for text: {text[:60]}... — {e}")
        return {
            'textblob_sentiment': 0.0,
            'vader_sentiment': 0.0,
            'total_sentiment': 0.0,
            'subjectivity': 0.0,
            'sentiment': 'neutral'
        }

def process_item(item):
    if "content" in item and "source" in item:
        _id = item.get('_id', '')
        raw_dt = item.get('timestamp')  # original string

        # parse date string to datetime object
        try:
            dt_obj = parser.parse(raw_dt)
            # Convert to ISO 8601 format with timezone (assume UTC if none)
            iso_dt = dt_obj.isoformat()
            # If your parsed datetime is naive (no tzinfo), add UTC explicitly:
            if dt_obj.tzinfo is None:
                from datetime import timezone
                dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                iso_dt = dt_obj.isoformat()
        except Exception as e:
            print(f"[WARN] Failed to parse datetime '{raw_dt}': {e}")
            iso_dt = None

        post = {
            'platform': item.get('platform'),
            'id': item.get('reddit_id'),
            'type': 'comment' if _id.startswith('reddit_comment_') else 'post',
            'source': item.get('source'),
            'text': clean_text(item.get('content')),
            'datetime': iso_dt,
            'author': item.get('author'),
            'parent_id': item.get('parent_post_id'),
        }
        sentiment = analyse_sentiment(post['text'])
        return {**post, **sentiment}
    return None

def preprocess_data(records):
    cleaned_data = []
    for i, item in enumerate(records):
        if i % 1000 == 0:
            print(f"Processing record {i}")
        try:
            processed = process_item(item)
            if processed:
                cleaned_data.append(processed)
        except Exception as e:
            print(f"[WARN] Failed to process item: {e}")
    return cleaned_data


def save_to_json(data, output):
    with open(output, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    print(f"Data saved to {output}")

def print_table(title, dataframe):
    print(f"\n\033[1m{title}\033[0m")
    print("-" * 40)
    print(dataframe.to_string(index=False, justify='center', 
                            formatters={
                                'Total Posts': '{:,}'.format,
                                'Negative Posts': '{:,}'.format
                            }))
    print("-" * 40)


if __name__ == "__main__":
    fetch_data_from_index()
