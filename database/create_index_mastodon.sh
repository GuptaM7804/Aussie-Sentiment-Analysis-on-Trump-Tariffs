#!/bin/bash

curl -XPUT -k "https://128.250.224.48:9200/reddit-trump-tarrifs' \
    --header 'Content-Type: application/json' \
    --data @create_index_mastodon.json \
    --user 'elastic:elastic' | jq '.'
