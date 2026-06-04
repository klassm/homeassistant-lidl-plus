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
import logging
import secrets
import sys
from datetime import UTC, datetime
from urllib.parse import parse_qs, quote, urlparse

import requests

sys.path.insert(0, "custom_components/lidl_plus")
from coupon_helpers import coupon_label, is_expired, is_special_promotion, should_show

_LOGGER = logging.getLogger(__name__)

_CLIENT_ID = "LidlPlusNativeClient"
_AUTH_API = "https://accounts.lidl.com"
_COUPONS_API = "https://coupons.lidlplus.com/app/api"
_TIMEOUT_SECONDS = 30
_WAIT_MS = 2000
_CHECKBOX_TIMEOUT_MS = 1000
_HTTP_CONFLICT = 409
_HTTP_BAD_REQUEST = 400

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
    """Return the Base64-encoded client secret."""
    return base64.b64encode(b"LidlPlusNativeClient:secret").decode()


class LidlPlusSyncClient:
    """Requests-based client matching the HA integration's api.py exactly."""

    def __init__(self, refresh_token: str, country: str, language: str) -> None:
        """Initialize the sync API client."""
        self.refresh_token = refresh_token
        self._country = country
        self._language = language
        self._token = ""
        self._expires: datetime | None = None

    def _api_headers(self) -> dict:
        """Return API request headers with the current access token."""
        return {
            **_DEFAULT_HEADERS,
            "Authorization": f"Bearer {self._token}",
            "Accept-Language": self._country,
            "Country": self._country,
        }

    def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self._expires and datetime.now(UTC) < self._expires and self._token:
            return self._token
        resp = requests.post(
            f"{_AUTH_API}/connect/token",
            data={"refresh_token": self.refresh_token, "grant_type": "refresh_token"},
            headers={
                "Authorization": f"Basic {_auth_secret()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=_TIMEOUT_SECONDS,
        )
        data = resp.json()
        if "error" in data:
            msg = f"Auth failed: {data['error']}"
            raise RuntimeError(msg)
        self._token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        from datetime import timedelta

        self._expires = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
        return self._token

    def coupons(self) -> dict:
        """Fetch V2 coupons from the API."""
        self.get_access_token()
        return requests.get(
            f"{_COUPONS_API}/v2/promotionsList",
            headers=self._api_headers(),
            timeout=_TIMEOUT_SECONDS,
        ).json()

    def coupon_promotions_v1(self) -> dict:
        """Fetch V1 coupon promotions from the API."""
        self.get_access_token()
        return requests.get(
            f"{_COUPONS_API}/v1/promotionslist",
            headers=self._api_headers(),
            timeout=_TIMEOUT_SECONDS,
        ).json()

    def activate_coupon(self, coupon_id: str) -> None:
        """Activate a V2 coupon by ID."""
        self.get_access_token()
        resp = requests.post(
            f"{_COUPONS_API}/v1/promotions/{coupon_id}/activation",
            headers=self._api_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        if resp.status_code != _HTTP_CONFLICT and resp.status_code > _HTTP_BAD_REQUEST:
            resp.raise_for_status()

    def activate_coupon_promotion_v1(self, promotion_id: str) -> None:
        """Activate a V1 coupon promotion by ID."""
        self.get_access_token()
        resp = requests.post(
            f"{_COUPONS_API}/v1/promotions/{promotion_id}/activation",
            headers=self._api_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        if resp.status_code != _HTTP_CONFLICT and resp.status_code > _HTTP_BAD_REQUEST:
            resp.raise_for_status()


# --- Login (Playwright + requests) ---


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge pair."""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _build_auth_url(country: str, language: str) -> tuple[str, str, str]:
    """Build the OAuth authorization URL with PKCE parameters."""
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
    """Extract the authorization code from a callback URL."""
    params = parse_qs(urlparse(url).query)
    return params.get("code", [None])[0] or ""


def cmd_login(args: argparse.Namespace) -> None:
    """Obtain a refresh token via browser-based login."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    auth_url, code_verifier, redirect_uri = _build_auth_url(args.country, args.language)

    _LOGGER.info("Opening browser for Lidl Plus login...")
    _LOGGER.info("Log in with your credentials and complete 2FA if prompted.")

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

        _LOGGER.info("Waiting for login to complete...")
        while not code:
            page.wait_for_timeout(_WAIT_MS)
            try:
                cb = page.locator("input[type='checkbox']").first
                if cb.is_visible(timeout=_CHECKBOX_TIMEOUT_MS):
                    cb.click()
                    page.locator("button[type='submit']").first.click(
                        timeout=_CHECKBOX_TIMEOUT_MS
                    )
            except PlaywrightError:
                pass

        browser.close()

    if not code:
        _LOGGER.error("Failed to capture authorization code.")
        sys.exit(1)

    _LOGGER.info("Exchanging authorization code for tokens...")
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
        timeout=_TIMEOUT_SECONDS,
    )
    tokens = resp.json()
    if "error" in tokens:
        _LOGGER.error("Token exchange failed: %s", tokens["error"])
        sys.exit(1)

    _LOGGER.info("Login successful!")
    _LOGGER.info("Refresh token (save for Home Assistant):")
    _LOGGER.info(tokens["refresh_token"])


# --- Shared coupon operations (using coupon_helpers) ---


def _print_coupons(data: dict, key: str) -> None:
    """Print coupons from a specific data section."""
    for section in data.get("sections", []):
        for coupon in section.get(key, []):
            if not should_show(coupon):
                continue
            status = "active" if coupon.get("isActivated") else "inactive"
            tag = " [in-store only]" if is_special_promotion(coupon) else ""
            _LOGGER.info("  [%s%s] %s", status, tag, coupon_label(coupon))


def _activate_all(client: LidlPlusSyncClient) -> int:
    """Activate all available coupons and return the count activated."""
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
                    _LOGGER.info("  [activated] %s", coupon_label(coupon))
                    activated += 1
                except requests.RequestException as e:
                    _LOGGER.warning("  [failed] %s: %s", coupon_label(coupon), e)
    except requests.RequestException:
        _LOGGER.exception("  V2 coupons error")

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
                    _LOGGER.info("  [activated] %s", coupon_label(coupon))
                    activated += 1
                except requests.RequestException as e:
                    _LOGGER.warning("  [failed] %s: %s", coupon_label(coupon), e)
    except requests.RequestException:
        _LOGGER.exception("  V1 coupons error")

    return activated


def cmd_auth(args: argparse.Namespace) -> None:
    """Test authentication with a refresh token."""
    client = LidlPlusSyncClient(args.refresh_token, args.country, args.language)
    try:
        token = client.get_access_token()
        _LOGGER.info("Authentication successful!")
        _LOGGER.info("  Access token: %s...", token[:20])
        _LOGGER.info("Updated refresh token (save for Home Assistant):")
        _LOGGER.info(client.refresh_token)
    except RuntimeError:
        _LOGGER.exception("Authentication failed")
        sys.exit(1)


def cmd_coupon_list(args: argparse.Namespace) -> None:
    """List all available coupons."""
    client = LidlPlusSyncClient(args.refresh_token, args.country, args.language)
    try:
        client.get_access_token()
        _LOGGER.info("=== Coupons (V2) ===")
        _print_coupons(client.coupons(), key="coupons")
        _LOGGER.info("=== Coupons (V1) ===")
        _print_coupons(client.coupon_promotions_v1(), key="promotions")
    except requests.RequestException:
        _LOGGER.exception("Error listing coupons")
        sys.exit(1)


def cmd_coupon_activate(args: argparse.Namespace) -> None:
    """Activate all available coupons."""
    client = LidlPlusSyncClient(args.refresh_token, args.country, args.language)
    try:
        client.get_access_token()
        _LOGGER.info("Activating coupons...")
        activated = _activate_all(client)
        _LOGGER.info("Total activated: %d", activated)
        _LOGGER.info("Updated refresh token: %s", client.refresh_token)
    except requests.RequestException:
        _LOGGER.exception("Error listing coupons")
        sys.exit(1)


# --- Main ---


def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Add common country/language arguments to a parser."""
    p.add_argument("--country", default="DE", help="Country code (default: DE)")
    p.add_argument("--language", default="de", help="Language code (default: de)")


def main() -> None:
    """Parse arguments and dispatch to the appropriate subcommand."""
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
