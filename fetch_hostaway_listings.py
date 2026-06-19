"""
Hostaway Listings Fetcher
=========================
Authentication: OAuth2 client_credentials grant
Endpoint: GET https://api.hostaway.com/v1/listings
Output: hostaway_listings_raw.json

Required env vars:
  HOSTAWAY_CLIENT_ID     - your Hostaway Account ID (integer)
  HOSTAWAY_CLIENT_SECRET - your Hostaway secret key (string)
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

TOKEN_URL = "https://api.hostaway.com/v1/accessTokens"
LISTINGS_URL = "https://api.hostaway.com/v1/listings"
OUTPUT_FILE = "hostaway_listings_raw.json"
PAGE_SIZE = 100  # max items per request


def get_access_token(client_id: str, client_secret: str) -> str:
    """Exchange client credentials for a Bearer token."""
    print("Step 1: Authenticating with Hostaway API...")
    payload = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "general",
    }).encode("utf-8")

    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    token = body.get("access_token")
    if not token:
        print("ERROR: No access_token in response:", body, file=sys.stderr)
        sys.exit(1)

    print(f"  Auth successful. Token type: {body.get('token_type')}, "
          f"expires_in: {body.get('expires_in')} seconds")
    return token


def fetch_page(token: str, offset: int) -> dict:
    """Fetch one page of listings."""
    params = urllib.parse.urlencode({"limit": PAGE_SIZE, "offset": offset})
    url = f"{LISTINGS_URL}?{params}"

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_listings(token: str) -> list:
    """Page through the listings endpoint and return all results."""
    print("Step 2: Fetching listings...")
    all_listings = []
    offset = 0
    total_pages = None

    while True:
        page_num = (offset // PAGE_SIZE) + 1
        if total_pages:
            print(f"  Fetching page {page_num} of {total_pages} (offset={offset})...")
        else:
            print(f"  Fetching page {page_num} (offset={offset})...")

        data = fetch_page(token, offset)

        if data.get("status") != "success":
            print("ERROR: Unexpected response status:", data, file=sys.stderr)
            sys.exit(1)

        results = data.get("result", [])
        all_listings.extend(results)

        total_pages = data.get("totalPages", 1)
        current_page = data.get("page", page_num)

        print(f"  Got {len(results)} listings (running total: {len(all_listings)})")

        if current_page >= total_pages or not results:
            break

        offset += PAGE_SIZE

    return all_listings


def main():
    client_id = os.environ.get("HOSTAWAY_CLIENT_ID")
    client_secret = os.environ.get("HOSTAWAY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(
            "ERROR: Set HOSTAWAY_CLIENT_ID and HOSTAWAY_CLIENT_SECRET environment variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        token = get_access_token(client_id, client_secret)
        listings = fetch_all_listings(token)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} error: {body}", file=sys.stderr)
        sys.exit(1)

    output = {
        "total_count": len(listings),
        "listings": listings,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nStep 3: Saved {len(listings)} listings to {OUTPUT_FILE}")
    print("Done.")


if __name__ == "__main__":
    main()
