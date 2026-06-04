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
from datetime import UTC, datetime
from urllib.parse import parse_qs, quote, urlparse

import requests

_CLIENT_ID = "LidlPlusNativeClient"
_AUTH_API = "https://accounts.lidl.com"
_COUPONS_API = "https://coupons.lidlplus.com/app/api"
_TIMEOUT = 30


def _generate_pkce():
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _build_auth_url(country: str, language: str):
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
    auth_url = f"{_AUTH_API}/connect/authorize?{query}"
    return auth_url, code_verifier, redirect_uri


def _extract_code(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get("code", [None])[0] or ""


def _accept_legal_terms(page) -> None:
    try:
        checkbox = page.locator("input[type='checkbox']").first
        if checkbox.is_visible(timeout=1000):
            checkbox.click()
            page.locator("button[type='submit']").first.click(timeout=1000)
    except Exception:
        pass


class LidlPlusClient:
    def __init__(self, refresh_token: str, country: str, language: str) -> None:
        self._refresh_token = refresh_token
        self._country = country
        self._language = language
        self._token = ""
        self._expires: datetime | None = None

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    def _default_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "App-Version": "14.21.2",
            "Operating-System": "iOS",
            "App": "com.lidl.eci.lidl.plus",
            "Accept-Language": self._country,
            "Country": self._country,
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/133.0.6943.89 Mobile Safari/537.36"
            ),
        }

    def get_access_token(self) -> str:
        if self._expires and datetime.now(UTC) < self._expires and self._token:
            return self._token
        secret = base64.b64encode(f"{_CLIENT_ID}:secret".encode()).decode()
        resp = requests.post(
            f"{_AUTH_API}/connect/token",
            data={"refresh_token": self._refresh_token, "grant_type": "refresh_token"},
            headers={
                "Authorization": f"Basic {secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=_TIMEOUT,
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Auth failed: {data['error']}")
        self._token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._expires = datetime.now(UTC) + __import__("datetime").timedelta(
            seconds=data["expires_in"]
        )
        return self._token

    def coupons(self) -> dict:
        self.get_access_token()
        resp = requests.get(
            f"{_COUPONS_API}/v2/promotionsList",
            headers=self._default_headers(),
            timeout=_TIMEOUT,
        )
        return resp.json()

    def coupon_promotions_v1(self) -> dict:
        self.get_access_token()
        resp = requests.get(
            f"{_COUPONS_API}/v1/promotionslist",
            headers=self._default_headers(),
            timeout=_TIMEOUT,
        )
        return resp.json()

    def activate_coupon(self, coupon_id: str) -> None:
        self.get_access_token()
        resp = requests.post(
            f"{_COUPONS_API}/v1/promotions/{coupon_id}/activation",
            headers=self._default_headers(),
            timeout=_TIMEOUT,
        )
        if resp.status_code != 409 and resp.status_code > 400:
            resp.raise_for_status()

    def activate_coupon_promotion_v1(self, promotion_id: str) -> None:
        self.get_access_token()
        resp = requests.post(
            f"{_COUPONS_API}/v1/promotions/{promotion_id}/activation",
            headers=self._default_headers(),
            timeout=_TIMEOUT,
        )
        if resp.status_code != 409 and resp.status_code > 400:
            resp.raise_for_status()


def cmd_login(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright

    auth_url, code_verifier, redirect_uri = _build_auth_url(args.country, args.language)

    print("Opening browser for Lidl Plus login...")
    print("Log in with your credentials and complete 2FA if prompted.\n")

    code = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context()
        page = context.new_page()

        def handle_request(request):
            nonlocal code
            url = request.url
            if "callback" in url and "code=" in url:
                code = _extract_code(url)

        page.on("request", handle_request)
        page.goto(auth_url)

        print("Waiting for login to complete...")
        while not code:
            page.wait_for_timeout(2000)
            _accept_legal_terms(page)

        browser.close()

    if not code:
        print("Failed to capture authorization code.")
        sys.exit(1)

    print("Authorization code received, exchanging for tokens...")

    token_response = requests.post(
        "https://accounts.lidl.com/connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": _CLIENT_ID,
        },
        headers={
            "Authorization": "Basic "
            + base64.b64encode(b"LidlPlusNativeClient:secret").decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    tokens = token_response.json()
    if "error" in tokens:
        print(f"Token exchange failed: {tokens['error']}")
        sys.exit(1)

    refresh_token = tokens["refresh_token"]
    print("\nLogin successful!")
    print("Refresh token (save for Home Assistant):")
    print(refresh_token)


def cmd_auth(args: argparse.Namespace) -> None:
    client = LidlPlusClient(args.refresh_token, args.country, args.language)
    try:
        token = client.get_access_token()
        print("Authentication successful!")
        print(f"  Access token: {token[:20]}...")
        print(f"  Refresh token: {client.refresh_token[:20]}...")
        print("\nUpdated refresh token (save this for Home Assistant):")
        print(client.refresh_token)
    except RuntimeError as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)


def cmd_coupon_list(args: argparse.Namespace) -> None:
    client = LidlPlusClient(args.refresh_token, args.country, args.language)
    try:
        client.get_access_token()

        print("=== Coupons (V2) ===")
        coupons = client.coupons()
        _print_coupons(coupons, key="coupons")

        print("\n=== Coupons (V1) ===")
        coupons_v1 = client.coupon_promotions_v1()
        _print_coupons(coupons_v1, key="promotions")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_coupon_activate(args: argparse.Namespace) -> None:
    client = LidlPlusClient(args.refresh_token, args.country, args.language)
    try:
        client.get_access_token()
        activated = 0

        print("=== Activating coupons (V2) ===")
        coupons = client.coupons()
        for section in coupons.get("sections", []):
            for coupon in section.get("coupons", []):
                if coupon["isActivated"]:
                    print(f"  [already active] {coupon['title']}")
                    continue
                if _is_expired(coupon):
                    print(f"  [expired] {coupon['title']}")
                    continue
                try:
                    client.activate_coupon(coupon["id"])
                    print(f"  [activated] {coupon['title']}")
                    activated += 1
                except Exception as e:
                    print(f"  [failed] {coupon['title']}: {e}")

        print("\n=== Activating coupons (V1) ===")
        coupons_v1 = client.coupon_promotions_v1()
        for section in coupons_v1.get("sections", []):
            for coupon in section.get("promotions", []):
                if coupon["isActivated"]:
                    print(f"  [already active] {coupon['title']}")
                    continue
                if _is_expired_v1(coupon):
                    print(f"  [expired] {coupon['title']}")
                    continue
                try:
                    client.activate_coupon_promotion_v1(coupon["id"])
                    print(f"  [activated] {coupon['title']}")
                    activated += 1
                except Exception as e:
                    print(f"  [failed] {coupon['title']}: {e}")

        print(f"\nTotal activated: {activated}")
        print(f"\nUpdated refresh token: {client.refresh_token}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


_SKIP_TITLES = {"Aktionsrabatt", "Wiedereröffnung"}


def _print_coupons(data: dict, key: str) -> None:
    for section in data.get("sections", []):
        for coupon in section.get(key, []):
            if coupon.get("isOnlineShop"):
                continue
            if coupon.get("title") in _SKIP_TITLES:
                continue
            status = "active" if coupon.get("isActivated") else "inactive"
            discount = coupon.get("discount", {}).get("title", "")
            desc = coupon.get("discount", {}).get("description", "")
            label = f"{discount} {coupon['title']}".strip() if discount else coupon["title"]
            detail = f" ({desc})" if desc else ""
            print(f"  [{status}] {label}{detail} (id: {coupon['id']})")


def _is_expired(coupon: dict) -> bool:
    end = coupon.get("endValidityDate")
    if end and datetime.fromisoformat(end) < datetime.now(UTC):
        return True
    start = coupon.get("startValidityDate")
    if start and datetime.fromisoformat(start) > datetime.now(UTC):
        return True
    return False


def _is_expired_v1(coupon: dict) -> bool:
    validity = coupon.get("validity", {})
    end = validity.get("end")
    if end and datetime.fromisoformat(end) < datetime.now(UTC):
        return True
    start = validity.get("start")
    if start and datetime.fromisoformat(start) > datetime.now(UTC):
        return True
    return False


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--country", default="DE", help="Country code (default: DE)")
    p.add_argument("--language", default="de", help="Language code (default: de)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lidl Plus CLI - authenticate and manage coupons"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser(
        "login", help="Log in via browser and obtain a refresh token"
    )
    _add_common_args(login_parser)

    auth_parser = subparsers.add_parser(
        "auth", help="Test a refresh token and print the updated token"
    )
    _add_common_args(auth_parser)
    auth_parser.add_argument(
        "--refresh-token", required=True, help="OAuth refresh token"
    )

    coupon_parser = subparsers.add_parser("coupon", help="Coupon operations")
    _add_common_args(coupon_parser)
    coupon_parser.add_argument(
        "--refresh-token", required=True, help="OAuth refresh token"
    )
    coupon_sub = coupon_parser.add_subparsers(dest="coupon_command", required=True)
    coupon_sub.add_parser("list", help="List available coupons")
    coupon_sub.add_parser("activate", help="Activate all available coupons")

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
