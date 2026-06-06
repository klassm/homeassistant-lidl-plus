#!/usr/bin/env -S uv run python3
"""
CLI tool for Lidl Plus authentication and coupon management.

Usage:
  scripts/auth.py login --country DE --language de
  scripts/auth.py auth --refresh-token TOKEN --country DE --language de
  scripts/auth.py coupon list --refresh-token TOKEN --country DE --language de
  scripts/auth.py coupon activate --refresh-token TOKEN --country DE --language de
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, quote, urlparse

import requests

sys.path.insert(0, "custom_components/lidl_plus")
from coupon_helpers import coupon_label, is_expired, is_special_promotion, should_show

_CLIENT_ID = "LidlPlusNativeClient"
_AUTH_API = "https://accounts.lidl.com"
_COUPONS_API = "https://coupons.lidlplus.com/app/api"
_TIMEOUT = 30

_DEFAULT_HEADERS = {
    "App-Version": "14.21.2",
    "Operating-System": "iOS",
    "App": "com.lidl.eci.lidl.plus",
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/133.0.6943.89 Mobile Safari/537.36"
    ),
}


def _auth_secret() -> str:
    return base64.b64encode(b"LidlPlusNativeClient:secret").decode()


class LidlPlusSyncClient:
    """Requests-based client matching the HA integration's api.py exactly."""

    def __init__(self, refresh_token: str, country: str, language: str) -> None:
        self.refresh_token = refresh_token
        self._country = country
        self._language = language
        self._token = ""
        self._expires: datetime | None = None

    def _api_headers(self) -> dict:
        return {
            **_DEFAULT_HEADERS,
            "Authorization": f"Bearer {self._token}",
            "Accept-Language": self._country,
            "Country": self._country,
        }

    def get_access_token(self) -> str:
        if self._expires and datetime.now(UTC) < self._expires and self._token:
            return self._token
        resp = requests.post(
            f"{_AUTH_API}/connect/token",
            data={"refresh_token": self.refresh_token, "grant_type": "refresh_token"},
            headers={
                "Authorization": f"Basic {_auth_secret()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=_TIMEOUT,
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Auth failed: {data['error']}")
        self._token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self._expires = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
        return self._token

    def coupons(self) -> dict:
        self.get_access_token()
        return requests.get(
            f"{_COUPONS_API}/v2/promotionsList",
            headers=self._api_headers(),
            timeout=_TIMEOUT,
        ).json()

    def coupon_promotions_v1(self) -> dict:
        self.get_access_token()
        return requests.get(
            f"{_COUPONS_API}/v1/promotionslist",
            headers=self._api_headers(),
            timeout=_TIMEOUT,
        ).json()

    def activate_coupon(self, coupon_id: str) -> None:
        self.get_access_token()
        resp = requests.post(
            f"{_COUPONS_API}/v1/promotions/{coupon_id}/activation",
            headers=self._api_headers(),
            timeout=_TIMEOUT,
        )
        if resp.status_code != 409 and resp.status_code > 400:
            resp.raise_for_status()

    def activate_coupon_promotion_v1(self, promotion_id: str) -> None:
        self.get_access_token()
        resp = requests.post(
            f"{_COUPONS_API}/v1/promotions/{promotion_id}/activation",
            headers=self._api_headers(),
            timeout=_TIMEOUT,
        )
        if resp.status_code != 409 and resp.status_code > 400:
            resp.raise_for_status()


# --- Login (Playwright + requests) ---


def _generate_pkce() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _build_auth_url(country: str, language: str) -> tuple[str, str, str]:
    code_verifier, code_challenge = _generate_pkce()
    redirect_uri = "com.lidlplus.app://callback"
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    locale = f"{language}-{country}"
    params = {
        "response_type": "code",
        "scope": "openid profile offline_access lpprofile lpapis",
        "redirect_uri": redirect_uri,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "client_id": _CLIENT_ID,
        "state": state,
        "nonce": nonce,
        "Country": country,
        "language": locale,
    }
    query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())
    return f"{_AUTH_API}/connect/authorize?{query}", code_verifier, redirect_uri


def _extract_code(url: str) -> str:
    params = parse_qs(urlparse(url).query)
    return params.get("code", [None])[0] or ""


def cmd_login(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright

    auth_url, code_verifier, redirect_uri = _build_auth_url(args.country, args.language)

    print("Opening browser for Lidl Plus login...")
    print("Log in with your credentials and complete 2FA if prompted.")
    print(
        "If the CLI doesn't detect the callback automatically, check the"
        " browser console for the redirect URL.\n"
    )

    code = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        page = browser.new_page()

        def on_request(request: object) -> None:
            nonlocal code
            url = getattr(request, "url", "")
            if "callback" in url and "code=" in url:
                code = _extract_code(url)

        page.on("request", on_request)
        page.goto(auth_url)

        print("Waiting for login to complete...")
        wait_count = 0
        while not code:
            page.wait_for_timeout(2000)
            wait_count += 1
            if wait_count >= 90:  # ~3 minutes
                break
            try:
                cb = page.locator("input[type='checkbox']").first
                if cb.is_visible(timeout=1000):
                    cb.click()
                    page.locator("button[type='submit']").first.click(timeout=1000)
            except Exception:
                pass

        if browser.is_connected():
            browser.close()

    if not code:
        fallback_url = input(
            "Could not auto-capture the callback URL.\n"
            "Paste the full URL from the browser console "
            "(com.lidlplus.app://callback?code=...): "
        ).strip()
        code = _extract_code(fallback_url)

    if not code:
        print("Failed to capture authorization code.")
        sys.exit(1)

    print("Exchanging authorization code for tokens...")
    resp = requests.post(
        f"{_AUTH_API}/connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": _CLIENT_ID,
        },
        headers={
            "Authorization": f"Basic {_auth_secret()}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=_TIMEOUT,
    )
    tokens = resp.json()
    if "error" in tokens:
        print(f"Token exchange failed: {tokens['error']}")
        sys.exit(1)

    print("\nLogin successful!")
    print("Refresh token (save for Home Assistant):")
    print(tokens["refresh_token"])


# --- Shared coupon operations (using coupon_helpers) ---


def _print_coupons(data: dict, key: str) -> None:
    for section in data.get("sections", []):
        for coupon in section.get(key, []):
            if not should_show(coupon):
                continue
            status = "active" if coupon.get("isActivated") else "inactive"
            tag = " [in-store only]" if is_special_promotion(coupon) else ""
            print(f"  [{status}{tag}] {coupon_label(coupon)}")


def _activate_all(client: LidlPlusSyncClient) -> int:
    activated = 0

    try:
        coupons = client.coupons()
        for section in coupons.get("sections", []):
            for coupon in section.get("coupons", []):
                if (
                    coupon["isActivated"]
                    or is_expired(coupon)
                    or is_special_promotion(coupon)
                ):
                    continue
                try:
                    client.activate_coupon(coupon["id"])
                    print(f"  [activated] {coupon_label(coupon)}")
                    activated += 1
                except Exception as e:
                    print(f"  [failed] {coupon_label(coupon)}: {e}")
    except Exception as e:
        print(f"  V2 coupons error: {e}")

    try:
        coupons_v1 = client.coupon_promotions_v1()
        for section in coupons_v1.get("sections", []):
            for coupon in section.get("promotions", []):
                if (
                    coupon["isActivated"]
                    or is_expired(coupon)
                    or is_special_promotion(coupon)
                ):
                    continue
                try:
                    client.activate_coupon_promotion_v1(coupon["id"])
                    print(f"  [activated] {coupon_label(coupon)}")
                    activated += 1
                except Exception as e:
                    print(f"  [failed] {coupon_label(coupon)}: {e}")
    except Exception as e:
        print(f"  V1 coupons error: {e}")

    return activated


def cmd_auth(args: argparse.Namespace) -> None:
    client = LidlPlusSyncClient(args.refresh_token, args.country, args.language)
    try:
        token = client.get_access_token()
        print("Authentication successful!")
        print(f"  Access token: {token[:20]}...")
        print("\nUpdated refresh token (save for Home Assistant):")
        print(client.refresh_token)
    except RuntimeError as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)


def cmd_coupon_list(args: argparse.Namespace) -> None:
    client = LidlPlusSyncClient(args.refresh_token, args.country, args.language)
    try:
        client.get_access_token()
        print("=== Coupons (V2) ===")
        _print_coupons(client.coupons(), key="coupons")
        print("\n=== Coupons (V1) ===")
        _print_coupons(client.coupon_promotions_v1(), key="promotions")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_coupon_activate(args: argparse.Namespace) -> None:
    client = LidlPlusSyncClient(args.refresh_token, args.country, args.language)
    try:
        client.get_access_token()
        print("Activating coupons...")
        activated = _activate_all(client)
        print(f"\nTotal activated: {activated}")
        print(f"Updated refresh token: {client.refresh_token}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


# --- Main ---


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--country", default="DE", help="Country code (default: DE)")
    p.add_argument("--language", default="de", help="Language code (default: de)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lidl Plus CLI - authenticate and manage coupons"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_p = subparsers.add_parser("login", help="Obtain a refresh token via browser")
    _add_common_args(login_p)

    auth_p = subparsers.add_parser("auth", help="Test a refresh token")
    _add_common_args(auth_p)
    auth_p.add_argument("--refresh-token", required=True)

    coupon_p = subparsers.add_parser("coupon", help="Coupon operations")
    _add_common_args(coupon_p)
    coupon_p.add_argument("--refresh-token", required=True)
    coupon_sub = coupon_p.add_subparsers(dest="coupon_command", required=True)
    coupon_sub.add_parser("list", help="List coupons")
    coupon_sub.add_parser("activate", help="Activate all coupons")

    args = parser.parse_args()

    if args.command == "login":
        cmd_login(args)
    elif args.command == "auth":
        cmd_auth(args)
    elif args.command == "coupon":
        if args.coupon_command == "list":
            cmd_coupon_list(args)
        elif args.coupon_command == "activate":
            cmd_coupon_activate(args)


if __name__ == "__main__":
    main()
