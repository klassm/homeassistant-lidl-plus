# Lidl Plus Integration for Home Assistant

A Home Assistant custom integration that automatically activates all available Lidl Plus digital coupons every 6 hours and exposes active coupons as a sensor.

## Installation

1. Install via [HACS](https://hacs.xyz/) or copy `custom_components/lidl_plus/` to your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration** and search for "Lidl Plus".

## Obtaining a Refresh Token

This integration requires a Lidl Plus refresh token. You can obtain one using the CLI tool included in this repository:

```bash
# Install dependencies
uv sync --group dev
uv run playwright install chromium

# Run the login command
scripts/auth.py login --country DE --language de
```

A browser window will open to Lidl's login page. After you log in and complete any 2FA, the CLI automatically captures the token and prints your refresh token. Copy this token into the Home Assistant config flow.

> **Note:** Refresh tokens may be rotated by Lidl. This integration automatically persists the updated token after each authentication.

## How It Works

Every 6 hours, the integration:

1. Refreshes the OAuth access token
2. Activates all available, unactivated coupons
3. Fetches current coupon state and updates the sensor

## Sensor

A `sensor.lidl_plus_coupons` entity is created per config entry, showing the number of currently valid active coupons. Attributes include:

| Attribute | Description |
|-----------|-------------|
| `total_coupons` | Total coupons found |
| `active_coupons` | Coupons that are activated |
| `valid_coupons` | Active coupons that haven't expired |
| `activated_last_cycle` | Coupons activated in the last refresh |
| `coupon_names` | List of active coupon titles |
| `coupons` | Detailed list with title, discount, and end date |

## Multiple Accounts

You can add multiple Lidl Plus accounts (e.g. different countries). Each gets its own sensor and activation cycle.

## Configuration

| Key       | Description                          | Default |
|-----------|--------------------------------------|---------|
| `token`   | Lidl Plus OAuth refresh token        | —       |
| `country` | Your country code (DE, NL, BE, etc.) | `DE`    |
| `language`| Your language code (de, nl, fr, etc.)| `de`    |

## CLI Tool

The `scripts/auth.py` tool can also be used standalone:

```bash
# Log in and obtain a refresh token
scripts/auth.py login --country DE --language de

# Test an existing refresh token
scripts/auth.py auth --refresh-token TOKEN --country DE --language de

# List available coupons
scripts/auth.py coupon list --refresh-token TOKEN --country DE --language de

# Activate all coupons
scripts/auth.py coupon activate --refresh-token TOKEN --country DE --language de
```
