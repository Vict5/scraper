"""Export Playwright storage_state for Instagram after logging in.

Usage examples:
  python export_instagram_state.py --output state.json
  python export_instagram_state.py --username youremail --password yourpass --output state.json

Notes:
- Prefer running with headless=False so you can complete CAPTCHA/2FA if required.
- You can omit --password to be prompted securely.
- Install Playwright: `pip install playwright` and then `playwright install`.
"""
from __future__ import annotations
import argparse
import getpass
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


def export_storage_state(username: str | None, password: str | None, output_path: str, headless: bool = False):
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Use a consistent user agent that matches the scraper
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

    with sync_playwright() as pw:
        # Use a persistent context so the profile (cookies, localStorage) survives between runs
        profile_dir = out.parent.joinpath("pw_profile")
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()
        # Capture Playwright console messages and request failures for diagnostics
        page.on("console", lambda msg: print("PW Console:", msg.text))
        page.on("requestfailed", lambda req: print("PW Request failed:", req.url))

        try:
            print("Opening Instagram login page...")
            page.goto("https://www.instagram.com/accounts/login/", timeout=60000)

            print("Waiting for login page or existing session state...")
            try:
                page.wait_for_selector("nav, input[name='username'], button[type='submit']", timeout=60000)
            except PWTimeoutError:
                print("Initial CSS page elements did not appear within 60 seconds.")
                if not headless:
                    print("Please complete the login manually in the browser window.")
                    input("Press Enter after you have logged in and the Instagram home page is visible...")
                else:
                    raise RuntimeError(
                        "Login page did not load in time. Run without --headless so you can complete login manually."
                    )

            # One-tap page may show a text-based button after navigation
            if "accounts/onetap" in page.url:
                print("Detected one-tap login page.")
                try:
                    page.wait_for_selector("text=Continue as", timeout=10000)
                    page.click("text=Continue as")
                    page.wait_for_selector("nav", timeout=90000)
                    print("One-tap redirect successful; logged in.")
                except Exception:
                    print("Unable to auto-click one-tap. Please click the Continue button in the browser.")
                    if not headless:
                        input("Press Enter after you have completed the one-tap login...")
                    try:
                        page.wait_for_selector("nav", timeout=180000)
                        print("Detected navigation bar after manual one-tap login.")
                    except PWTimeoutError:
                        print("Timed out waiting for manual one-tap completion. I will still save state if available.")

            elif page.locator("nav").count() > 0:
                print("Detected navigation bar; already logged in.")
            else:
                print("Not logged in; waiting for login form...")
                try:
                    page.wait_for_selector("input[name='username']", timeout=120000)
                except PWTimeoutError:
                    if not headless:
                        print("Login form did not appear. Please complete login manually in the browser.")
                        input("Press Enter after logging in manually...")
                    else:
                        raise RuntimeError(
                            "Login form did not appear in time. Run without --headless to log in manually."
                        )

                if username:
                    page.fill("input[name='username']", username)
                else:
                    print("No username provided; please enter it in the browser.")

                if password is not None:
                    page.fill("input[name='password']", password)
                else:
                    print("No password provided; please enter it in the browser.")

                if username and password is not None:
                    try:
                        page.click("button[type='submit']")
                    except Exception:
                        page.click("text=Log In")
                print("Complete any verification (CAPTCHA/2FA) in the browser window.")
                print("Waiting up to 3 minutes for login detection...")

                try:
                    page.wait_for_selector("nav", timeout=180000)
                    print("Detected navigation bar; likely logged in.")
                except PWTimeoutError:
                    if not headless:
                        print("Timed out waiting for 'nav'. If you are logged in, I will continue.")
                        input("Press Enter to continue and save storage state...")
                    else:
                        print("Timed out waiting for 'nav'. I will continue and save whatever state is available.")

            # Crucial: Navigate to home page to ensure all session cookies/storage are set
            print(f"Current URL before final home navigation: {page.url}")
            print("Navigating to home page to finalize session...")
            page.goto("https://www.instagram.com/", timeout=60000)
            try:
                page.wait_for_selector("nav", timeout=60000)
            except PWTimeoutError:
                print("Home nav did not appear; continuing anyway.")
            time.sleep(5)

            # Diagnostics: check in-memory storage state before saving
            print("Collecting storage_state (in-memory) for diagnostics...")
            try:
                storage = context.storage_state()
            except Exception as e:
                print("Failed to read in-memory storage_state:", e)
                storage = {}
            cookies = storage.get("cookies", []) if isinstance(storage, dict) else []
            print(f"Found {len(cookies)} cookies in storage_state.")
            if len(cookies) == 0 and not headless:
                print("No cookies detected. You may need to complete login manually or retry.")
                resp = input("Type 'retry' to wait and try again, or press Enter to save current state: ")
                if resp.strip().lower() == "retry":
                    print("Please complete login in the opened browser. Press Enter when done to re-check cookies...")
                    input()
                    try:
                        storage = context.storage_state()
                        cookies = storage.get("cookies", []) if isinstance(storage, dict) else []
                        print(f"After manual step: found {len(cookies)} cookies.")
                    except Exception as e:
                        print("Failed to read storage after manual step:", e)

            print("Saving storage state...")
            context.storage_state(path=str(out))
            print(f"Saved storage_state to: {out}")

        finally:
            try:
                # Close the persistent context (profile dir is preserved)
                context.close()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", help="Instagram username/email (optional)")
    parser.add_argument("--password", help="Instagram password (optional; will prompt if omitted)")
    parser.add_argument("--output", "-o", default="state.json", help="Output storage_state JSON file")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (not recommended for login)")
    args = parser.parse_args()

    pwd = args.password
    if args.username and pwd is None:
        # Prompt for password securely
        pwd = getpass.getpass(prompt="Instagram password: ")

    export_storage_state(args.username, pwd, args.output, headless=args.headless)


if __name__ == "__main__":
    main()
