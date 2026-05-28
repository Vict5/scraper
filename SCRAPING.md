# Scraping Frameworks & Techniques

## Frameworks

### crawl4ai
The primary scraping engine used for Reddit, YouTube, and Instagram (browser fallback). It drives a real Chromium browser via Playwright under the hood, meaning pages that rely on JavaScript to render content — like YouTube and Reddit — work out of the box.

Key classes used:
- `AsyncWebCrawler` — async context manager that launches and manages the browser
- `CrawlerRunConfig` — per-request configuration (wait conditions, scroll behaviour, timeouts, extraction strategy)
- `BrowserConfig` — browser-level configuration (headless mode, user agent, stealth, session state)
- `JsonCssExtractionStrategy` — declarative CSS-selector schema that maps DOM elements to structured JSON fields

### httpx
Used exclusively for Instagram. Rather than driving a browser, the Instagram scraper calls Instagram's internal mobile REST API (`/api/v1/tags/{hashtag}/sections/`) directly over HTTP, with the session cookies from `state.json` for authentication. `httpx` is an async HTTP client with an API similar to `requests`.

### Playwright (indirect)
Playwright is the browser automation layer underneath `crawl4ai`. It is also used directly in `export_instagram_state.py` to perform a one-time interactive login to Instagram and export the resulting browser storage state (cookies + localStorage) to `state.json`.

---

## Extraction Techniques

### JsonCssExtractionStrategy (CSS selector schemas)
Each platform has a declarative schema — a `baseSelector` that identifies repeating container elements, and a list of `fields` that extract text or attributes from child elements using CSS selectors. This keeps extraction logic separate from crawl logic and produces structured JSON directly.

```
YOUTUBE_COMMENTS_SCHEMA   →  baseSelector: ytd-comment-thread-renderer
YOUTUBE_SEARCH_SCHEMA     →  baseSelector: ytd-video-renderer
REDDIT_SEARCH_SCHEMA      →  baseSelector: div.search-result
INSTAGRAM_SEARCH_SCHEMA   →  baseSelector: article, div[role='presentation']
```

### Internal API scraping (Instagram)
Instead of parsing the DOM, the Instagram scraper POSTs to the same REST endpoint Instagram's own mobile app uses:

```
POST https://www.instagram.com/api/v1/tags/{hashtag}/sections/
```

This returns clean JSON (captions, usernames, like counts, post codes) and is far more reliable than DOM scraping because it is unaffected by frontend CSS class changes. Authentication is provided via session cookies loaded from `state.json`.

The approach required two fixes to make session cookies work:
- **URL-decoding**: Playwright stores cookie values percent-encoded (e.g. `%3A` instead of `:`). They must be decoded with `urllib.parse.unquote` before passing to `httpx`, otherwise the server rejects the session.
- **POST not GET**: The endpoint returns `405` for GET requests; it only accepts `POST` with a `application/x-www-form-urlencoded` body.

### Pagination
Instagram results are paginated via `next_max_id` tokens returned in each API response. The scraper loops, passing the token back in each subsequent POST, until the requested `--size` is reached or no more pages exist.

### Markdown fallback (Instagram browser scrape)
When the browser-based Instagram scrape returns no structured content, the scraper falls back to parsing the raw markdown representation of the page. It looks for heuristic signals (`@`, `http`, digit + "like") to reconstruct partial post objects. This is a last resort and produces lower-quality data.

---

## Anti-Detection Techniques

### Stealth mode
`BrowserConfig(enable_stealth=True)` activates crawl4ai's built-in stealth patches — it removes or spoofs browser properties (e.g. `navigator.webdriver`) that headless browsers normally expose and that sites use to detect automation.

### Navigator override & magic mode (Instagram browser fallback)
`CrawlerRunConfig(override_navigator=True, magic=True, simulate_user=True)` applies additional fingerprint normalisation and simulates human-like interaction patterns.

### Randomised scroll delays
Instagram browser scrapes use `random.uniform(2.0, 4.0)` seconds between scroll steps rather than a fixed interval, making timing patterns harder to fingerprint.

### Consistent user agent
A fixed, realistic Chrome or mobile Safari user agent is set explicitly rather than using crawl4ai's default, ensuring the UA matches the expected profile for the target platform (desktop Chrome for Reddit, mobile Safari for Instagram's API).

### Mobile user agent + app ID header (Instagram API)
Instagram's internal API authenticates requests partly by matching the `User-Agent` and `x-ig-app-id` header against known Instagram app identifiers. The scraper uses a mobile Safari UA paired with app ID `936619743392459` (Instagram's web app ID) to appear as a legitimate mobile client.

### Inter-request delays (YouTube multi-video)
When scraping multiple YouTube videos in sequence, `asyncio.sleep(random.uniform(1.0, 2.5))` is inserted between each video to avoid triggering rate limits.

---

## Session Persistence

### Playwright storage state (`state.json`)
`export_instagram_state.py` logs in to Instagram via a real browser and exports the full storage state — cookies, localStorage, and session tokens — as `state.json`. This file is passed to subsequent runs via `--storage-state state.json`, allowing the scraper to authenticate as a logged-in user without repeating the login flow.

`crawl4ai` accepts this storage state natively via `BrowserConfig(storage_state=...)`. For `httpx` API calls, the cookies are extracted from the state dict and passed directly.

### Persistent browser profile (`pw_profile/`)
`export_instagram_state.py` also maintains a persistent Playwright browser profile directory. This preserves the browser's on-disk state (cache, IndexedDB, service workers) across sessions, further reinforcing the appearance of a returning user.

---

## Platform-Specific Notes

| Platform | Method | Auth required | Pagination |
|----------|--------|---------------|------------|
| Reddit | crawl4ai browser (`old.reddit.com`) | No | No (single search page) |
| Instagram | httpx → internal REST API | Yes (`state.json`) | Yes (`next_max_id`) |
| Instagram (fallback) | crawl4ai browser with stealth | Optional | No |
| YouTube comments | crawl4ai browser (`ytd-comment-thread-renderer`) | No | Via scroll steps |
| YouTube search | crawl4ai browser (`ytd-video-renderer`) | No | No |
