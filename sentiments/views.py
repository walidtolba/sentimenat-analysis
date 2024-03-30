from django.shortcuts import render
from typing import Dict
from playwright.sync_api import sync_playwright
import jmespath
import requests

API_URL = "https://api-inference.huggingface.co/models/CAMeL-Lab/bert-base-arabic-camelbert-da-sentiment"
headers = {"Authorization": "Bearer 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"}

def scrape_tweet(url: str) -> dict:
    """
    Scrape a single tweet page for Tweet thread e.g.:
    https://twitter.com/Scrapfly_dev/status/1667013143904567296
    Return parent tweet, reply tweets and recommended tweets
    """
    _xhr_calls = []

    def intercept_response(response):
        """capture all background requests and save them"""
        # we can extract details from background requests
        if response.request.resource_type == "xhr":
            _xhr_calls.append(response)
        return response

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # enable background request intercepting:
        page.on("response", intercept_response)
        # go to url and wait for the page to load
        page.goto(url)
        page.wait_for_selector("[data-testid='tweet']")

        # find all tweet background requests:
        tweet_calls = [f for f in _xhr_calls if "TweetResultByRestId" in f.url]
        for xhr in tweet_calls:
            data = xhr.json()
            return data['data']['tweetResult']['result']

def parse_tweet(data: Dict) -> Dict:
    """Parse Twitter tweet JSON dataset for the most important fields"""
    result = jmespath.search(
        """{
        created_at: legacy.created_at,
        attached_urls: legacy.entities.urls[].expanded_url,
        attached_urls2: legacy.entities.url.urls[].expanded_url,
        attached_media: legacy.entities.media[].media_url_https,
        tagged_users: legacy.entities.user_mentions[].screen_name,
        tagged_hashtags: legacy.entities.hashtags[].text,
        favorite_count: legacy.favorite_count,
        bookmark_count: legacy.bookmark_count,
        quote_count: legacy.quote_count,
        reply_count: legacy.reply_count,
        retweet_count: legacy.retweet_count,
        quote_count: legacy.quote_count,
        text: legacy.full_text,
        is_quote: legacy.is_quote_status,
        is_retweet: legacy.retweeted,
        language: legacy.lang,
        user_id: legacy.user_id_str,
        id: legacy.id_str,
        conversation_id: legacy.conversation_id_str,
        source: source,
        views: views.count
    }""",
        data,
    )
    result["poll"] = {}
    poll_data = jmespath.search("card.legacy.binding_values", data) or []
    for poll_entry in poll_data:
        key, value = poll_entry["key"], poll_entry["value"]
        if "choice" in key:
            result["poll"][key] = value["string_value"]
        elif "end_datetime" in key:
            result["poll"]["end"] = value["string_value"]
        elif "last_updated_datetime" in key:
            result["poll"]["updated"] = value["string_value"]
        elif "counts_are_final" in key:
            result["poll"]["ended"] = value["boolean_value"]
        elif "duration_minutes" in key:
            result["poll"]["duration"] = value["string_value"]
    user_data = jmespath.search("core.user_results.result", data)
    if user_data:
        result["user"] = ''
    return result




def scrape_twitter(url):
        data = parse_tweet(scrape_tweet(url))
        return data['text']

def sentiment_analysis(text):
    output = query({
	"inputs": text,
})
    print(output)
    return output[0]


def twitter_page(request):
    url = request.GET.get('url')
    if url:
        try:
            text = scrape_twitter(url)
            sentiment = sentiment_analysis(text)
        except KeyError:
            sentiment = [{'label': 'neutral', 'score': 0}, {'label': 'positive', 'score': 0}, {'label': 'negative', 'score': 0}]
            text = 'server is starting, please try agin after 20 seconds.'
        except:
            sentiment = [{'label': 'neutral', 'score': 0}, {'label': 'positive', 'score': 0}, {'label': 'negative', 'score': 0}]
            text = 'Invalid URL, please enter a valid URL.'
        return render(request, 'api/twitter.html', {'sentiment_result': sentiment, 'tweet_text': text})
    return render(request, 'api/twitter.html')


def query(payload):
	response = requests.post(API_URL, headers=headers, json=payload)
	return response.json()