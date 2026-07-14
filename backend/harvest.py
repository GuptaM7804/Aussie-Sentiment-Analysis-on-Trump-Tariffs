
import praw
from mastodon import Mastodon
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import time
import traceback # For more detailed error logging in handler
from elasticsearch import Elasticsearch, helpers
import hashlib # For generating fallback IDs if needed, though platform IDs are preferred
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# load environment variables from .env file
load_dotenv()

#ES_HOST = os.environ.get("ES_HOST", "http://elasticsearch:9200")
ES_HOST = os.environ.get("ES_HOST", "https://elasticsearch-master.elastic.svc.cluster.local:9200")
#ES_PORT = int(os.environ.get("ES_PORT", "9200"))
ES_USER = os.environ.get("ES_USER", "elastic")
ES_PASS = os.environ.get("ES_PASS", "elastic")
ES_INDEX = os.environ.get("ES_INDEX", "social-media-harvest")
ELASTICSEARCH_BATCH_SIZE = 50 # Batch size for Elasticsearch uploads


# use environment variables to protect sensitive data
REDDIT_CONFIG = {
    "client_id": os.environ.get("REDDIT_CLIENT_ID"),
    "client_secret": os.environ.get("REDDIT_CLIENT_SECRET"),
    "user_agent": os.environ.get("REDDIT_USER_AGENT", "MyCommentHarvester/0.4")
}

MASTODON_CONFIGS = [
    {
        "base_url": "https://mastodon.au",
        "access_token": os.environ.get("MASTODON_AU_TOKEN")
    },
    {
        "base_url": "https://aus.social",
        "access_token": os.environ.get("MASTODON_AUS_SOCIAL_TOKEN")
    }
]

SUBREDDITS = [
    "australia",
    "AusFinance",
    "AustralianPolitics",
    "AusEcon",
    "australian",
    "sydney",
    "melbourne"
]

# load keywords from JSON file containing a list of keywords
def load_keywords(file_path):
    _, file_extension = os.path.splitext(file_path)
    if file_extension != ".json":
        raise ValueError("Unsupported file format for keywords. Please use a .json file.")

    try:
        with open(file_path, "r") as f:
            keywords_data = json.load(f)
            keywords = keywords_data.get("keywords", [])
            if not keywords:
                print(f"[WARN] No keywords found in {file_path}.")
            return keywords
    except FileNotFoundError:
        print(f"[ERROR] Keywords file not found: {file_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decoding failed for {file_path}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error loading keywords from {file_path}: {e}")
        return []

# start reddit API
def initialize_reddit(client_id, client_secret, user_agent):
    return praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)

def generate_document_id(platform_prefix, item_id):
    """Generates a consistent document ID."""
    if item_id is None or str(item_id).strip() == "":
        # Fallback if item_id is missing, though highly unlikely for these platforms
        return f"{platform_prefix}_missingid_{hashlib.md5(str(time.time()).encode()).hexdigest()}"
    return f"{platform_prefix}_{str(item_id)}"

# get data from reddit ncorporating comment fetching
def fetch_reddit_data(keywords, subreddits, reddit_client, post_limit=50, comments_per_post_limit=None, replace_more_limit=5):
    print(f"Fetching posts and comments from Reddit...")
    current_batch = []
    total_posts_processed_count = 0
    total_comments_fetched_count = 0

    for subreddit_name in subreddits:
        try:
            subreddit_obj = reddit_client.subreddit(subreddit_name)
            print(f"Processing subreddit r/{subreddit_name}...")
            for keyword in keywords:
                print(f"  Searching for '{keyword}' in r/{subreddit_name}...")
                try:
                    for submission in subreddit_obj.search(keyword, limit=post_limit):
                        total_posts_processed_count += 1
                        content_value = submission.selftext if submission.selftext else submission.title
                        author_name = submission.author.name if submission.author else None
                        doc_id = generate_document_id("reddit_post", submission.id)

                        post_data_item = {
                            "document_id": doc_id,
                            "platform": "reddit",
                            "source": subreddit_name,
                            "content": content_value,
                            "timestamp": datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                            "author": author_name,
                            "reddit_id": submission.id
                        }
                        current_batch.append(post_data_item)

                        if len(current_batch) >= ELASTICSEARCH_BATCH_SIZE:
                            print(f"[INFO] Reddit Posts: Uploading batch of {len(current_batch)} items to Elasticsearch...")
                            upload_to_elasticsearch(current_batch)
                            current_batch.clear()

                        try:
                            if replace_more_limit is not None and replace_more_limit > 0:
                                submission.comments.replace_more(limit=replace_more_limit)
                            elif replace_more_limit == 0:
                                submission.comments.replace_more(limit=0)
                            else: # replace_more_limit is None
                                submission.comments.replace_more(limit=None)
                        except Exception as e_comments:
                            print(f"      [WARN] Error replacing more comments for post ID {submission.id}: {e_comments}")

                        comments_fetched_for_this_post = 0
                        for comment in submission.comments.list():
                            if not isinstance(comment, praw.models.Comment):
                                continue

                            if comments_per_post_limit is not None and comments_fetched_for_this_post >= comments_per_post_limit:
                                break

                            comment_author_name = comment.author.name if comment.author else None
                            comment_body = comment.body if comment.body is not None else ""
                            comment_doc_id = generate_document_id("reddit_comment", comment.id)

                            comment_data_item = {
                                "document_id": comment_doc_id,
                                "platform": "reddit",
                                "source": subreddit_name,
                                "content": comment_body,
                                "timestamp": datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
                                "author": comment_author_name,
                                "reddit_id": comment.id,
                                "parent_post_id": submission.id
                            }
                            current_batch.append(comment_data_item)
                            comments_fetched_for_this_post += 1
                            total_comments_fetched_count += 1

                            if len(current_batch) >= ELASTICSEARCH_BATCH_SIZE:
                                print(f"[INFO] Reddit Comments: Uploading batch of {len(current_batch)} items to Elasticsearch...")
                                upload_to_elasticsearch(current_batch)
                                current_batch.clear()
                except praw.exceptions.PRAWException as e_praw:
                    print(f"    PRAW API Error for '{keyword}' in r/{subreddit_name}: {e_praw}")
                    print(f"    Sleeping for 10 seconds before retrying or moving on...")
                    time.sleep(10)
                except Exception as e_search:
                    print(f"    General Error searching for '{keyword}' in r/{subreddit_name} or fetching its comments: {e_search}")
                    traceback.print_exc()
                    print(f"    Sleeping for 5 seconds before moving on...")
                    time.sleep(5)
        except Exception as e_sub:
            print(f"[ERROR] Could not process subreddit r/{subreddit_name}: {e_sub}")
            traceback.print_exc()
            print(f"    Sleeping for 10 seconds before moving to next subreddit...")
            time.sleep(10)

    if current_batch:
        print(f"[INFO] Reddit: Uploading final batch of {len(current_batch)} items to Elasticsearch...")
        upload_to_elasticsearch(current_batch)
        current_batch.clear()

    total_items_processed = total_posts_processed_count + total_comments_fetched_count
    print(f"Fetching from Reddit completed. Processed {total_posts_processed_count} posts and fetched {total_comments_fetched_count} comments. Total items for ES: {total_items_processed}")
    return total_items_processed

# call Mastodon API
def initialize_mastodon(base_url, access_token):
    return Mastodon(api_base_url=base_url, access_token=access_token)

# get data from Mastodon
def fetch_mastodon_data(keywords, mastodon_client, max_results=100):
    print(f" Fetching data from Mastodon instance: {mastodon_client.api_base_url}...")
    current_batch = []
    total_toots_processed_count = 0
    
    for keyword in keywords:
        fetched_count_for_keyword = 0
        try:
            print(f"  Searching for '{keyword}' on {mastodon_client.api_base_url}...")
            results = mastodon_client.search(q=keyword, resolve=True)
            time.sleep(2) 

            if "statuses" in results:
                for toot in results["statuses"]:
                    if fetched_count_for_keyword >= max_results:
                        break
                    
                    toot_platform_id = toot.get("id")
                    doc_id = generate_document_id("mastodon_toot", toot_platform_id)

                    raw_timestamp = toot.get("created_at")
                    timestamp_iso = None
                    if isinstance(raw_timestamp, datetime):
                        timestamp_iso = raw_timestamp.astimezone(timezone.utc).isoformat()
                    elif isinstance(raw_timestamp, str):
                        try:
                            timestamp_iso = datetime.strptime(raw_timestamp, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc).isoformat()
                        except ValueError:
                            try:
                                timestamp_iso = datetime.strptime(raw_timestamp, '%Y-%m-%dT%H:%M:%S%z').astimezone(timezone.utc).isoformat()
                            except ValueError:
                                print(f"    Could not parse Mastodon timestamp: {raw_timestamp}. Storing as is.")
                                timestamp_iso = raw_timestamp 
                    else:
                        timestamp_iso = str(raw_timestamp) 

                    toot_content = toot.get("content", "")
                    account_info = toot.get("account")
                    author_username = account_info["username"] if account_info and "username" in account_info else None

                    toot_data_item = {
                        "document_id": doc_id,
                        "platform": "mastodon",
                        "source": mastodon_client.api_base_url,
                        "content": toot_content,
                        "timestamp": timestamp_iso,
                        "author": author_username,
                        "mastodon_id": toot_platform_id
                    }
                    current_batch.append(toot_data_item)
                    fetched_count_for_keyword +=1
                    total_toots_processed_count += 1

                    if len(current_batch) >= ELASTICSEARCH_BATCH_SIZE:
                        print(f"[INFO] Mastodon: Uploading batch of {len(current_batch)} items to Elasticsearch...")
                        upload_to_elasticsearch(current_batch)
                        current_batch.clear()
            else:
                print(f"     No 'statuses' key in Mastodon search results for '{keyword}'. Result: {results}")

        except Exception as e:
            print(f"   Error fetching Mastodon data for keyword '{keyword}' from {mastodon_client.api_base_url}: {e}")
            traceback.print_exc()
            time.sleep(5) 
            
    if current_batch:
        print(f"[INFO] Mastodon: Uploading final batch of {len(current_batch)} items to Elasticsearch...")
        upload_to_elasticsearch(current_batch)
        current_batch.clear()
        
    print(f" Fetched {total_toots_processed_count} toots in total from {mastodon_client.api_base_url} for the keywords.")
    return total_toots_processed_count

def upload_to_elasticsearch(documents):
    if not documents:
        print("[INFO] No documents to upload for this batch.")
        return

    try:
        es = Elasticsearch(
            [ES_HOST],
            basic_auth=(ES_USER, ES_PASS),
            verify_certs=False
        )

        actions = []
        for doc_with_id_field in documents:
            doc_source = doc_with_id_field.copy() 
            doc_id_val = doc_source.pop("document_id", None)

            if doc_id_val:
                actions.append({
                    "_index": ES_INDEX,
                    "_id": doc_id_val,
                    "_source": doc_source
                })
            else:
                print(f"[WARN] Document ID missing for a document, ES will auto-generate one. Doc: {doc_source}")
                actions.append({
                    "_index": ES_INDEX,
                    "_source": doc_source
                })
        
        if not actions:
            print("[INFO] No actions to perform for Elasticsearch batch (e.g., all docs missed IDs).")
            return

        success, errors = helpers.bulk(es, actions, raise_on_error=False)
        print(f"[INFO] Elasticsearch: Successfully indexed/updated {success} documents in this batch.")
        if errors:
            print(f"[WARN] Encountered {len(errors)} errors while indexing this batch.")
            # for error_detail in errors: # Optionally log details of each error
            #     print(f"[DEBUG] ES Error Detail: {error_detail}")
    except Exception as e:
        print(f"[ERROR] Failed to upload batch to Elasticsearch: {e}")
        traceback.print_exc()


# Handler: Point of entry for Fission
def handler(context, event):
    print("[INFO] Handler invoked.")
    total_items_processed_for_es = 0
    try:
        body = {}
        if event and hasattr(event, "body") and event.body:
            try:
                body = json.loads(event.body)
                print(f"[INFO] Parsed event body: {body}")
            except Exception as e:
                print(f"[WARN] Could not parse event.body JSON: {e}. Using default behavior.")
        else:
            print("[INFO] No event body provided or event.body is empty. Using default behavior (fetch all).")

        platform_to_fetch = body.get("platform", "all").lower()
        print(f"[INFO] Handler triggered with platform: {platform_to_fetch}")

        handler_reddit_post_limit = body.get("reddit_post_limit", 1000)
        handler_reddit_comments_per_post_limit = body.get("reddit_comments_per_post_limit", 300)
        handler_reddit_replace_more_limit = body.get("reddit_replace_more_limit", 20)
        handler_mastodon_max_results = body.get("mastodon_max_results", 5000)

        keywords_file_path = body.get("keywords_file", "keywords.json")
        keywords = load_keywords(keywords_file_path)
        if not keywords:
            print("[ERROR] No keywords loaded. Aborting handler.")
            return {"status": "error", "message": f"No keywords loaded from {keywords_file_path}."}

        if platform_to_fetch in ("reddit", "all"):
            if all(REDDIT_CONFIG.values()):
                print("[INFO] Initializing Reddit client for handler...")
                reddit_client = initialize_reddit(**REDDIT_CONFIG)
                reddit_items_count = fetch_reddit_data(
                    keywords,
                    SUBREDDITS,
                    reddit_client,
                    post_limit=handler_reddit_post_limit,
                    comments_per_post_limit=handler_reddit_comments_per_post_limit,
                    replace_more_limit=handler_reddit_replace_more_limit
                )
                total_items_processed_for_es += reddit_items_count
                print(f"[INFO] Handler: Processed {reddit_items_count} items from Reddit (uploaded to ES in batches).")
            else:
                print("[WARN] Handler: Reddit credentials missing or incomplete. Skipping Reddit harvest.")

        if platform_to_fetch in ("mastodon", "all"):
            for mastodon_config in MASTODON_CONFIGS:
                if mastodon_config["base_url"] and mastodon_config["access_token"]:
                    try:
                        print(f"[INFO] Handler: Initializing Mastodon client for {mastodon_config['base_url']}...")
                        mastodon_client = initialize_mastodon(**mastodon_config)
                        mastodon_items_count = fetch_mastodon_data(
                            keywords,
                            mastodon_client,
                            max_results=handler_mastodon_max_results
                        )
                        total_items_processed_for_es += mastodon_items_count
                        print(f"[INFO] Handler: Processed {mastodon_items_count} toots from {mastodon_config['base_url']} (uploaded to ES in batches).")
                    except Exception as e:
                        print(f"[ERROR] Handler: Error with Mastodon instance {mastodon_config['base_url']}: {e}")
                        traceback.print_exc()
                else:
                    print(f"[WARN] Handler: Mastodon instance {mastodon_config.get('base_url', 'UNKNOWN')} not fully configured. Skipping.")

        if total_items_processed_for_es == 0:
            print("[WARN] Handler: No data processed from any platform for Elasticsearch.")
            return {"status": "no_data", "message": "No data was processed or uploaded to Elasticsearch."}

        print(f"[INFO] Handler: Total items processed and sent to Elasticsearch: {total_items_processed_for_es}")
        
        return {
            "status": "success",
            "total_items_processed_for_es": total_items_processed_for_es,
            "message": "Data fetched and uploaded to Elasticsearch in batches."
        }
    except Exception as e:
        print(f"[ERROR] Handler encountered an unexpected error: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e), "total_items_processed_for_es": total_items_processed_for_es}


# Main function 
if __name__ == "__main__":
    print("[INFO] Running local execution of the script...")

    local_reddit_post_limit = 100
    local_reddit_comments_per_post_limit = 10
    local_reddit_replace_more_limit = 3
    local_mastodon_max_toots = 10
    # ELASTICSEARCH_BATCH_SIZE is used directly from global scope

    print(f"[CONFIG] Reddit fetch parameters: post_limit={local_reddit_post_limit}, comments_per_post_limit={local_reddit_comments_per_post_limit}, replace_more_limit={local_reddit_replace_more_limit}")
    print(f"[CONFIG] Mastodon fetch parameters: max_toots_per_keyword={local_mastodon_max_toots}")
    print(f"[CONFIG] Elasticsearch batch size: {ELASTICSEARCH_BATCH_SIZE}")
    
    KEYWORDS_FILE = "keywords.json"

    try:
        keywords = load_keywords(KEYWORDS_FILE)
        if not keywords:
            print(f"[ERROR] No keywords loaded from '{KEYWORDS_FILE}'. Exiting.")
            exit(1)
        print(f"[INFO] Keywords loaded: {keywords}")
    except Exception as e:
        print(f"[CRITICAL] Error loading keywords: {e}")
        exit(1)

    reddit_client = None
    if all(REDDIT_CONFIG.values()): 
        print("[INFO] Initializing Reddit client for local run...")
        reddit_client = initialize_reddit(**REDDIT_CONFIG)
    else:
        print("[WARN] Reddit credentials not fully configured. Skipping Reddit data collection.")

    total_items_processed_main = 0

    if reddit_client:
        print("[INFO] Starting Reddit data fetch for local run...")
        reddit_items_count = fetch_reddit_data(
            keywords,
            SUBREDDITS,
            reddit_client,
            post_limit=local_reddit_post_limit,
            comments_per_post_limit=local_reddit_comments_per_post_limit,
            replace_more_limit=local_reddit_replace_more_limit
        )
        total_items_processed_main += reddit_items_count
        print(f"[INFO] Processed {reddit_items_count} items (posts and comments) from Reddit (uploaded to ES in batches).")

    print("[INFO] Starting Mastodon data fetch for local run...")
    for mastodon_config in MASTODON_CONFIGS:
        if mastodon_config["base_url"] and mastodon_config["access_token"]:
            try:
                print(f"[INFO] Connecting to Mastodon instance: {mastodon_config['base_url']}")
                mastodon_client = initialize_mastodon(**mastodon_config)
                mastodon_items_count = fetch_mastodon_data(
                    keywords,
                    mastodon_client,
                    max_results=local_mastodon_max_toots
                )
                total_items_processed_main += mastodon_items_count
                print(f"[INFO] Processed {mastodon_items_count} toots from {mastodon_config['base_url']} (uploaded to ES in batches).")
            except Exception as e:
                print(f"[ERROR] Error with Mastodon instance {mastodon_config['base_url']}: {e}")
                traceback.print_exc()
        else:
            print(f"[WARN] Mastodon instance {mastodon_config.get('base_url', 'UNKNOWN')} not fully configured. Skipping.")

    if total_items_processed_main > 0:
        print(f"[INFO] Total items processed and sent to Elasticsearch: {total_items_processed_main}")
    else:
        print("[INFO] No data processed from any platform.")

    print("[INFO] Process finished.")