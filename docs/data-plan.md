# Data Collection Plan

## Platforms
### Reddit
- Subreddits: r/Australia, r/AusFinance, r/AustralianPolitics, r/AusEcon
- Search terms: "trumptariffs", "trump", "tradewar", "temutrump", "ustariffs", "peterdutton", "america", "economy", "trade", "australia"
- Tool: PRAW (Python Reddit API Wrapper)

### Mastodon
- Instances: aus.social, mastodon.au
- Filter: hashtags or keyword-based search
- Tool: Mastodon.py

## Triggering (via Fission)
- Scheduled function: runs every 6 hours
- Stores posts with: timestamp, platform, content, keyword matched

## Storage
- ElasticSearch index fields:
  - `_id`, `platform`, `content`, `timestamp`, `keyword`, `sentiment_score`
