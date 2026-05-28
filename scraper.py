"""Reddit, Instagram, and YouTube scraper.

Usage:
  python obseinew.py --company "Nike" --size 100                                           (Reddit)
  python obseinew.py --company "nike" --source instagram --storage-state state.json        (Instagram hashtag)
  python obseinew.py --source youtube --url "https://www.youtube.com/watch?v=XXXXX"        (YouTube: single video)
  python obseinew.py --source youtube --company "Nike" --videos 5                          (YouTube: search + scrape 5 videos)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from typing import Any, Dict, Iterable, List
from urllib.parse import quote_plus, unquote

import httpx
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

YOUTUBE_COMMENTS_SCHEMA = {
    "baseSelector": "ytd-comment-thread-renderer",
    "fields": [
        {"name": "author", "selector": "#author-text", "type": "text"},
        {"name": "text", "selector": "#content-text", "type": "text"},
        {"name": "likes", "selector": "#vote-count-middle", "type": "text"},
        {"name": "published_time", "selector": "#header-author #published-time-text", "type": "text"},
    ],
}

YOUTUBE_SEARCH_SCHEMA = {
    "baseSelector": "ytd-video-renderer",
    "fields": [
        {"name": "title", "selector": "#video-title", "type": "text"},
        {"name": "url", "selector": "#video-title", "type": "attribute", "attribute": "href"},
    ],
}

REDDIT_SEARCH_SCHEMA = {
    "baseSelector": "div.search-result",
    "fields": [
        {
            "name": "title",
            "selector": "a.title, a.search-title",
            "type": "text",
        },
        {
            "name": "excerpt",
            "selector": "div.search-expando p, div.usertext-body p",
            "type": "text",
        },
        {
            "name": "post_url",
            "selector": "a.title, a.search-title",
            "type": "attribute",
            "attribute": "href",
        },
        {"name": "subreddit", "selector": "a.subreddit", "type": "text"},
        {"name": "author", "selector": "a.author", "type": "text"},
    ],
}

INSTAGRAM_SEARCH_SCHEMA = {
    "baseSelector": "article, div[role='presentation'], div[role='feed']",
    "fields": [
        {
            "name": "caption",
            "selector": "span, h2, div[data-caption], .html-span",
            "type": "text",
        },
        {
            "name": "author",
            "selector": "a[title], header span a, header h2 a, .x1iyjqo2",
            "type": "text",
        },
        {
            "name": "post_url",
            "selector": "a[href*='/p/'], a[href*='reel']",
            "type": "attribute",
            "attribute": "href",
        },
        {
            "name": "likes",
            "selector": "svg[aria-label*='like'], span:contains('like')",
            "type": "text",
        },
    ],
}


async def fetch_reddit_posts_crawl4ai(query: str, size: int = 100, storage_state: Any = None, cookies: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Use crawl4ai to search old.reddit.com and extract post metadata."""
    encoded_query = quote_plus(query)
    url = f"https://old.reddit.com/search?q={encoded_query}&sort=latest"
    
    # Define a consistent user agent
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )

    browser_config = BrowserConfig(
        headless=True,
        user_agent=user_agent,
        storage_state=storage_state,
        cookies=cookies,
        enable_stealth=True
    )

    run_config = CrawlerRunConfig(
        wait_for="css:body",
        wait_for_timeout=10000,
        page_timeout=30000,
        scan_full_page=True,
        scroll_delay=0.5,
        max_scroll_steps=2,
        target_elements=["div.search-result"],
        extraction_strategy=JsonCssExtractionStrategy(schema=REDDIT_SEARCH_SCHEMA),
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            result = await asyncio.wait_for(crawler.arun(url=url, config=run_config), timeout=90)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "crawl4ai timed out while fetching Reddit results. Try again later or reduce --size."
            )
        except RuntimeError as e:
            if "Wait condition failed" in str(e):
                raise RuntimeError(
                    "Reddit did not load expected content. The script now uses old.reddit.com, but the page may still be blocked or changed."
                ) from e
            raise

    if not result.success or not result.extracted_content:
        return []

    return json.loads(result.extracted_content)


async def fetch_youtube_video_urls(query: str, num_videos: int = 3) -> List[Dict[str, str]]:
    """Search YouTube and return up to num_videos video URLs matching the query."""
    encoded = quote_plus(query)
    search_url = f"https://www.youtube.com/results?search_query={encoded}"

    config = CrawlerRunConfig(
        wait_for="ytd-video-renderer",
        wait_for_timeout=20000,
        page_timeout=30000,
        scan_full_page=False,
        scroll_delay=0.5,
        max_scroll_steps=2,
        target_elements=["ytd-video-renderer"],
        extraction_strategy=JsonCssExtractionStrategy(schema=YOUTUBE_SEARCH_SCHEMA),
    )

    print(f"Searching YouTube for: {query}")
    async with AsyncWebCrawler() as crawler:
        try:
            result = await asyncio.wait_for(crawler.arun(url=search_url, config=config), timeout=60)
        except asyncio.TimeoutError:
            print("Timed out fetching YouTube search results.")
            return []

    if not result.success or not result.extracted_content:
        print("Failed to extract YouTube search results.")
        return []

    videos = json.loads(result.extracted_content)
    # href values are relative (/watch?v=...) — make them absolute
    out = []
    for v in videos:
        href = v.get("url", "")
        if href.startswith("/watch"):
            out.append({"title": v.get("title", ""), "url": f"https://www.youtube.com{href}"})
        if len(out) >= num_videos:
            break

    print(f"Found {len(out)} videos")
    return out


async def fetch_youtube_comments(video_url: str, size: int = 100) -> List[Dict[str, Any]]:
    """Scrape comments from a YouTube video page using crawl4ai."""
    config = CrawlerRunConfig(
        wait_for="ytd-comment-thread-renderer",
        wait_for_timeout=300000,
        scan_full_page=True,
        scroll_delay=1.0,
        max_scroll_steps=max(8, size // 10),
        target_elements=["#comments"],
        extraction_strategy=JsonCssExtractionStrategy(schema=YOUTUBE_COMMENTS_SCHEMA),
    )

    print(f"Fetching YouTube comments from {video_url}...")
    async with AsyncWebCrawler() as crawler:
        try:
            result = await asyncio.wait_for(crawler.arun(url=video_url, config=config), timeout=360)
        except asyncio.TimeoutError:
            print("Timed out waiting for YouTube comments to load.")
            return []

    if not result.success or not result.extracted_content:
        print("Failed to extract YouTube comments.")
        return []

    comments = json.loads(result.extracted_content)
    print(f"Extracted {len(comments)} YouTube comments")
    return comments[:size]


async def _run_youtube(query: str, url: str | None, size: int, num_videos: int) -> List[Dict[str, Any]]:
    """Orchestrate YouTube scraping: single URL or search-then-scrape multiple videos."""
    if url:
        comments = await fetch_youtube_comments(url, size=size)
        for c in comments:
            c["video_url"] = url
        return comments

    if not query:
        raise ValueError("Provide --company (search query) or --url when using --source youtube")

    videos = await fetch_youtube_video_urls(query, num_videos=num_videos)
    if not videos:
        return []

    all_comments: List[Dict[str, Any]] = []
    for video in videos:
        comments = await fetch_youtube_comments(video["url"], size=size)
        for c in comments:
            c["video_url"] = video["url"]
            c["video_title"] = video["title"]
        all_comments.extend(comments)
        await asyncio.sleep(random.uniform(1.0, 2.5))

    return all_comments


async def fetch_instagram_posts_api(query: str, size: int = 100, storage_state: Any = None, cookies: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Hit Instagram's internal REST API directly using session cookies — avoids DOM scraping entirely."""
    # Playwright stores cookie values URL-encoded — decode before passing to httpx
    cookie_dict: Dict[str, str] = {}
    if storage_state and isinstance(storage_state, dict):
        for c in storage_state.get("cookies", []):
            cookie_dict[c["name"]] = unquote(c["value"])
    elif cookies:
        for c in cookies:
            cookie_dict[c["name"]] = unquote(c["value"])

    csrftoken = cookie_dict.get("csrftoken", "")
    session_id = cookie_dict.get("sessionid", "")

    if not session_id:
        print("No sessionid found in storage state — API approach requires a logged-in session.")
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15A372 Safari/604.1"
        ),
        "x-ig-app-id": "936619743392459",
        "x-csrftoken": csrftoken,
        "x-asbd-id": "129477",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.instagram.com/explore/tags/{query}/",
        "Origin": "https://www.instagram.com",
    }

    url = f"https://www.instagram.com/api/v1/tags/{query}/sections/"
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    posts: List[Dict[str, Any]] = []
    print(f"Fetching Instagram #{query} via internal API...")

    def _parse_sections(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = []
        for section in data.get("sections", []):
            for item in section.get("layout_content", {}).get("medias", []):
                media = item.get("media", {})
                caption_obj = media.get("caption") or {}
                result.append({
                    "caption": caption_obj.get("text", ""),
                    "author": media.get("user", {}).get("username", ""),
                    "post_url": f"https://www.instagram.com/p/{media.get('code', '')}/",
                    "likes": str(media.get("like_count", "")),
                })
        return result

    async with httpx.AsyncClient(cookies=cookie_dict, headers=headers, follow_redirects=True, timeout=30) as client:
        try:
            form = {"tab_type": "top", "count": str(min(size, 33)), "surface": "grid", "page": "1"}
            resp = await client.post(url, data=form)
            print(f"  API response status: {resp.status_code}")
            if resp.status_code == 401:
                print("  Session expired — re-run export_instagram_state.py to refresh state.json.")
                return []
            if resp.status_code != 200:
                print(f"  Unexpected status {resp.status_code}. Falling back to browser scrape.")
                return []

            data = resp.json()
            posts.extend(_parse_sections(data))

            # Paginate if more posts needed
            next_max_id = data.get("next_max_id")
            page = 2
            while next_max_id and len(posts) < size:
                await asyncio.sleep(random.uniform(1.5, 3.0))
                form_next = {**form, "next_max_id": next_max_id, "page": str(page)}
                resp = await client.post(url, data=form_next)
                if resp.status_code != 200:
                    break
                data = resp.json()
                posts.extend(_parse_sections(data))
                next_max_id = data.get("next_max_id")
                page += 1

        except httpx.RequestError as e:
            print(f"  API request failed: {e}")
            return []

    print(f"Extracted {len(posts)} posts via Instagram API")
    return posts[:size]


async def fetch_instagram_posts_crawl4ai(query: str, size: int = 100, storage_state: Any = None, cookies: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """Browser-based fallback: crawl4ai with stealth mode."""
    encoded_query = quote_plus(query)
    url = f"https://www.instagram.com/explore/tags/{encoded_query}/"
    
    # Use a consistent user agent, especially when using storage state
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

    browser_config = BrowserConfig(
        headless=True,
        user_agent=user_agent,
        storage_state=storage_state,
        cookies=cookies,
        enable_stealth=True
    )

    run_config = CrawlerRunConfig(
        wait_for="css:body",
        wait_for_timeout=25000,
        page_timeout=60000,
        scan_full_page=True,
        scroll_delay=random.uniform(2.0, 4.0),  # Random delays to appear human-like
        max_scroll_steps=5,
        target_elements=["article", "div[role='presentation']", "div[role='feed']"],
        extraction_strategy=JsonCssExtractionStrategy(schema=INSTAGRAM_SEARCH_SCHEMA),
        simulate_user=True,
        override_navigator=True,
        magic=True
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            print(f"Fetching Instagram #{query} with anti-detection measures...")
            result = await asyncio.wait_for(crawler.arun(url=url, config=run_config), timeout=150)
        except asyncio.TimeoutError:
            print("Initial attempt timed out. Retrying with extended delays...")
            run_config.scroll_delay = random.uniform(3.0, 5.0)
            run_config.max_scroll_steps = 3
            run_config.wait_for_timeout = 15000
            run_config.page_timeout = 40000
            try:
                result = await asyncio.wait_for(crawler.arun(url=url, config=run_config), timeout=120)
            except asyncio.TimeoutError:
                print("Second attempt timed out. Instagram may be blocking access.")
                return []
        except RuntimeError as e:
            print(f"RuntimeError during Instagram crawl: {e}")
            return []

    if not result.success:
        print(f"Crawl failed. Status: {getattr(result, 'status_code', 'unknown')}")
        return []

    if not result.extracted_content:
        print("No structured content extracted. Instagram may require login or be blocking requests.")
        print("Attempting fallback: extracting from markdown content...")
        
        if hasattr(result, 'markdown') and result.markdown:
            posts = _fallback_instagram_extraction(result.markdown)
            if posts:
                return posts
        return []

    try:
        extracted = json.loads(result.extracted_content)
        posts = extracted if isinstance(extracted, list) else []
        print(f"Extracted {len(posts)} posts from Instagram")
        return posts
    except json.JSONDecodeError:
        print("Warning: Could not parse Instagram extraction as JSON. Trying fallback...")
        if hasattr(result, 'markdown') and result.markdown:
            return _fallback_instagram_extraction(result.markdown)
        return []



def _fallback_instagram_extraction(markdown_text: str) -> List[Dict[str, Any]]:
    """Fallback extraction from markdown when structured extraction fails."""
    posts = []
    lines = markdown_text.split('\n')
    
    current_post = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try to identify post components from markdown
        if any(keyword in line.lower() for keyword in ['@', 'instagram', 'post', 'liked']):
            if current_post and any(current_post.values()):
                posts.append(current_post)
            current_post = {"caption": line, "author": "", "post_url": "", "likes": ""}
        elif current_post and line.startswith('@'):
            current_post["author"] = line
        elif current_post and line.startswith('http'):
            current_post["post_url"] = line
        elif current_post and any(char.isdigit() for char in line) and 'like' in line.lower():
            current_post["likes"] = line
    
    if current_post and any(current_post.values()):
        posts.append(current_post)
    
    print(f"Fallback extraction recovered {len(posts)} posts from markdown")
    return posts


# def try_import_obsei_analyzers():
#     """Attempt to import obsei analyzers. Return a dict of analyzer instances or None."""
#     try:
#         from obsei.analyzer.sentiment_analyzer import VaderSentimentAnalyzer
#         from obsei.analyzer.classification_analyzer import ZeroShotClassificationAnalyzer
#
#         return {
#             "sentiment": VaderSentimentAnalyzer(),
#             "text_classification": ZeroShotClassificationAnalyzer(
#                 model_name_or_path="facebook/bart-large-mnli"
#             ),
#         }
#     except Exception:
#         return None
#
#
# def load_transformers_pipelines():
#     """Create Hugging Face transformer pipelines for fallback analysis."""
#     try:
#         from transformers import pipeline
#
#         zero_shot = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
#         sentiment = pipeline("sentiment-analysis")
#         return zero_shot, sentiment
#     except Exception as e:
#         raise RuntimeError(
#             "transformers pipelines are required for fallback analysis: install `transformers` and `torch`."
#         ) from e
#
#
# def normalize_obsei_payload(payload: Any) -> Dict[str, Any]:
#     return {"scores": payload.segmented_data.get("classifier_data", {})}


def _load_cookies_file(path: str) -> List[Dict[str, Any]]:
    """Load a JSON cookies file in Playwright/Chrome format (list of dicts)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "cookies" in data:
            return data.get("cookies")
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"Failed to load cookies file {path}: {e}")
        return []


def print_live_result(index: int, total: int, post: Dict[str, Any], classification: Dict[str, Any], sentiment: Dict[str, Any], source: str = "reddit") -> None:
    if source.lower() == "instagram":
        caption = post.get("caption", "(no caption)")
        author = post.get("author", "(no author)")
        post_url = post.get("post_url", "(no url)")
        likes = post.get("likes", "(no likes info)")
        print(f"\n[{index}/{total}] {caption[:80]}...")
        print(f"  author: {author} | likes: {likes}")
        print(f"  url: {post_url}")
    else:
        title = post.get("title", "(no title)")
        post_url = post.get("post_url", "(no url)")
        subreddit = post.get("subreddit", "(no subreddit)")
        author = post.get("author", "(no author)")
        print(f"\n[{index}/{total}] {title}")
        print(f"  subreddit: {subreddit} | author: {author}")
        print(f"  url: {post_url}")
    
    print(f"  classification: {classification}")
    print(f"  sentiment: {sentiment}")


# def analyze_posts_in_real_time(
#     posts: List[Dict[str, Any]],
#     candidate_labels: List[str],
#     obsei_analyzers: dict | None = None,
#     source: str = "reddit",
# ) -> List[Dict[str, Any]]:
#     results: List[Dict[str, Any]] = []
#     total = len(posts)
#
#     if obsei_analyzers:
#         try:
#             from obsei.payload import TextPayload
#             from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig
#
#             sentiment_analyzer = obsei_analyzers["sentiment"]
#             classification_analyzer = obsei_analyzers["text_classification"]
#             classifier_config = ClassificationAnalyzerConfig(
#                 labels=candidate_labels,
#                 add_positive_negative_labels=False,
#             )
#
#             for idx, post in enumerate(posts, start=1):
#                 if source.lower() == "instagram":
#                     text = post.get("caption", "")
#                 else:
#                     text = f"{post.get('title', '')}\n\n{post.get('excerpt', '')}".strip()
#                 text = text.strip()
#                 if not text:
#                     continue
#                 payload = TextPayload(processed_text=text)
#                 sentiment_payload = sentiment_analyzer.analyze_input([payload])[0]
#                 classification_payload = classification_analyzer.analyze_input(
#                     [payload], analyzer_config=classifier_config
#                 )[0]
#                 classification_data = normalize_obsei_payload(classification_payload)
#                 sentiment_data = normalize_obsei_payload(sentiment_payload)
#                 result = {"post": post, "classification": classification_data, "sentiment": sentiment_data}
#                 print_live_result(idx, total, post, classification_data, sentiment_data, source=source)
#                 results.append(result)
#
#             return results
#         except Exception as e:
#             print("obsei analyzers failed during streaming analysis — falling back to transformers:", e)
#
#     zero_shot, sentiment = load_transformers_pipelines()
#
#     for idx, post in enumerate(posts, start=1):
#         if source.lower() == "instagram":
#             text = post.get("caption", "")
#         else:
#             text = f"{post.get('title', '')}\n\n{post.get('excerpt', '')}".strip()
#         text = text.strip()
#         if not text:
#             continue
#         classification_result = zero_shot(text, candidate_labels)
#         sentiment_result = sentiment(text)[0]
#         classification_data = {
#             "labels": classification_result.get("labels", []),
#             "scores": classification_result.get("scores", []),
#         }
#         sentiment_data = {
#             "label": sentiment_result.get("label"),
#             "score": float(sentiment_result.get("score", 0.0)),
#         }
#         result = {"post": post, "classification": classification_data, "sentiment": sentiment_data}
#         print_live_result(idx, total, post, classification_data, sentiment_data, source=source)
#         results.append(result)
#
#     return results


def run(
    company: str,
    size: int = 100,
    out_file: str | None = None,
    source: str = "reddit",
    use_proxy: bool = False,
    storage_state: Any = None,
    cookies: List[Dict[str, Any]] | None = None,
    url: str | None = None,
    num_videos: int = 3,
):
    if source.lower() == "instagram" and use_proxy:
        print("Note: Proxy support requires additional setup. See --proxy-list option.")

    if source.lower() == "reddit":
        posts = asyncio.run(fetch_reddit_posts_crawl4ai(company, size=size, storage_state=storage_state, cookies=cookies))
    elif source.lower() == "instagram":
        posts = asyncio.run(fetch_instagram_posts_api(company, size=size, storage_state=storage_state, cookies=cookies))
        if not posts:
            print("API approach returned 0 posts — falling back to browser scrape...")
            posts = asyncio.run(fetch_instagram_posts_crawl4ai(company, size=size, storage_state=storage_state, cookies=cookies))
    elif source.lower() == "youtube":
        posts = asyncio.run(_run_youtube(query=company, url=url, size=size, num_videos=num_videos))
    else:
        raise ValueError(f"Unknown source: {source}. Choose 'reddit', 'instagram', or 'youtube'.")

    if not posts:
        print(f"No posts found for query: {company} on {source}")
        if source.lower() == "instagram":
            print("\nTroubleshooting Instagram:")
            print("1. Instagram may require authentication for hashtag pages")
            print("2. Try with a different hashtag or popular search term")
            print("3. Use --retry flag to attempt multiple times with different user agents")
            print("4. Instagram API might be a more reliable alternative")
        return

    # candidate_labels = ["complaint", "praise", "news", "question", "discussion"]
    # obsei_analyzers = try_import_obsei_analyzers()
    # if obsei_analyzers:
    #     print(f"Using obsei analyzers for real-time streaming analysis from {source}")
    # else:
    #     print(f"obsei not available or incomplete — using transformers fallback for real-time analysis from {source}")
    # out = analyze_posts_in_real_time(posts, candidate_labels, obsei_analyzers=obsei_analyzers, source=source)

    print(f"Fetched {len(posts)} posts from {source}.")
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        print("Saved results to", out_file)
    else:
        print("Use --out to save as JSON.")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search Reddit/Instagram with real-time sentiment and classification analysis"
    )
    parser.add_argument("--company", "-c", default="", help="Company name or hashtag to search (Reddit/Instagram)")
    parser.add_argument("--url", "-u", help="YouTube video URL (required when --source youtube)")
    parser.add_argument("--size", "-n", type=int, default=100, help="Number of posts/comments to fetch")
    parser.add_argument("--out", "-o", help="Optional output JSON file to write results")
    parser.add_argument("--source", "-s", default="reddit", choices=["reddit", "instagram", "youtube"],
                       help="Data source: reddit, instagram, or youtube (default: reddit)")
    parser.add_argument("--videos", "-v", type=int, default=3, help="Number of YouTube videos to scrape comments from when using --source youtube without --url (default: 3)")
    parser.add_argument("--retry", action="store_true", help="Retry with multiple user agents on failure (Instagram only)")
    parser.add_argument(
        "--storage-state",
        help="Path to Playwright storage_state.json (preserves cookies/localStorage).",
    )
    parser.add_argument(
        "--cookies-file",
        help="Path to cookies JSON file (Playwright/Chrome format: list or {'cookies': [...]}).",
    )
    
    args = parser.parse_args(argv)

    try:
        cookies = None
        if args.cookies_file:
            cookies = _load_cookies_file(args.cookies_file)

        storage_state = args.storage_state
        if storage_state and isinstance(storage_state, str) and storage_state.endswith(".json"):
            try:
                with open(storage_state, "r", encoding="utf-8") as f:
                    storage_state = json.load(f)
                print(f"Loaded storage state from {args.storage_state}")
            except Exception as e:
                print(f"Failed to load storage state from {args.storage_state}: {e}")
                storage_state = None

        run(
            args.company,
            size=args.size,
            out_file=args.out,
            source=args.source,
            storage_state=storage_state,
            cookies=cookies,
            url=args.url,
            num_videos=args.videos,
        )
        return 0
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

