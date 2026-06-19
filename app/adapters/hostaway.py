"""
Hostaway source adapter.

Pulls properties (listings) and reservations from the Hostaway API.
Maps Hostaway field names to our Supabase schema.

Hostaway is a supporting system. It provides:
  - Property identity, location, configuration
  - Channel listing URLs and export status
  - Reservations and guest data
  - House rules, access instructions, WiFi (where populated)

Hostaway does NOT provide tasks, comments, or people.
Those come from Breezeway.
"""

from __future__ import annotations


import os
import time
import datetime
import requests

from .base import BaseAdapter

_TOKEN_URL     = "https://api.hostaway.com/v1/accessTokens"
_LISTINGS_URL  = "https://api.hostaway.com/v1/listings"
_RESERVATIONS_URL = "https://api.hostaway.com/v1/reservations"
_PAGE_SIZE     = 100


# ---------------------------------------------------------------------------
# Property type lookup (Hostaway propertyTypeId → human-readable)
# ---------------------------------------------------------------------------
_PROPERTY_TYPE_MAP = {
    1: "Apartment",
    2: "House",
    3: "Bed & Breakfast",
    6: "Townhouse",
    8: "Villa",
    10: "Cabin",
    48: "Guest Suite",
    50: "Condo",
}

# Amenity names that signal specific boolean flags
_AMENITY_FLAGS = {
    "has_pool":               {"pool"},
    "has_hot_tub":            {"hot tub", "jacuzzi"},
    "has_ev_charger":         {"ev charger", "electric vehicle"},
    "has_washer_dryer":       {"washing machine", "dryer"},
    "has_dishwasher":         {"dishwasher"},
    "has_private_entrance":   {"private entrance"},
    "has_contactless_checkin":{"contactless check-in", "contactless check-in/out"},
}

# Custom field IDs from BEM's Hostaway account
_CF_PARKING        = 47929
_CF_CHECKOUT_NOTES = 47947
_CF_EXTRA_CHECKIN  = 47948
_CF_UNIT_NOTES     = 48149


class HostawayAdapter(BaseAdapter):

    def __init__(self):
        self._client_id     = os.environ["HOSTAWAY_CLIENT_ID"]
        self._client_secret = os.environ["HOSTAWAY_CLIENT_SECRET"]
        self._token: str | None = None

    # ------------------------------------------------------------------
    # BaseAdapter interface
    # ------------------------------------------------------------------

    def source_name(self) -> str:
        return "hostaway"

    def get_properties(self) -> list[dict]:
        token = self._auth()
        raw   = self._paginate(token, _LISTINGS_URL)
        return [self._map_property(l) for l in raw]

    def get_reservations(self) -> list[dict]:
        token  = self._auth()
        params = self._reservation_window()
        raw    = self._paginate(token, _RESERVATIONS_URL, extra_params=params)
        return [self._map_reservation(r) for r in raw]

    def get_people(self) -> list[dict]:
        # Hostaway does not manage operational staff. Return empty.
        return []

    def get_tasks(self) -> list[dict]:
        # Hostaway does not manage tasks. Return empty.
        return []

    def get_task_comments(self) -> list[dict]:
        # Hostaway does not manage task comments. Return empty.
        return []

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _auth(self) -> str:
        if self._token:
            return self._token
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     self._client_id,
                "client_secret": self._client_secret,
                "scope":         "general",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _paginate(self, token: str, url: str, extra_params: dict | None = None) -> list[dict]:
        results = []
        offset  = 0
        headers = {"Authorization": f"Bearer {token}"}
        while True:
            params = {"limit": _PAGE_SIZE, "offset": offset, **(extra_params or {})}
            resp   = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            body   = resp.json()
            page   = body.get("result", [])
            results.extend(page)
            if not page or body.get("page", 1) >= body.get("totalPages", 1):
                break
            offset += _PAGE_SIZE
            time.sleep(0.25)   # polite rate limiting
        return results

    def _reservation_window(self) -> dict:
        back    = int(os.getenv("RESERVATION_WINDOW_DAYS_BACK", 30))
        forward = int(os.getenv("RESERVATION_WINDOW_DAYS_FORWARD", 90))
        start   = (datetime.date.today() - datetime.timedelta(days=back)).isoformat()
        end     = (datetime.date.today() + datetime.timedelta(days=forward)).isoformat()
        return {"dateArrivalStart": start, "dateArrivalEnd": end}

    # ------------------------------------------------------------------
    # Field mapping: listing → properties row
    # ------------------------------------------------------------------

    def _map_property(self, l: dict) -> dict:
        amenity_names = {a["amenityName"].lower() for a in (l.get("listingAmenities") or [])}
        custom        = {cf["customFieldId"]: cf.get("value") for cf in (l.get("customFieldValues") or [])}
        tags          = [t["name"] for t in (l.get("listingTags") or [])]

        parking_type  = self._derive_parking_type(amenity_names)
        parking_det   = custom.get(_CF_PARKING)

        wifi_net  = l.get("wifiUsername") or None
        wifi_pass = l.get("wifiPassword") or None

        door_code    = l.get("doorSecurityCode") or None
        extra_ci     = custom.get(_CF_EXTRA_CHECKIN) or None

        commission_pct = next(
            (int(t.rstrip("%")) for t in tags if t.endswith("%") and t[:-1].isdigit()),
            None,
        )
        license_cat = next((t for t in tags if t in {"STR", "Hotel License", "Commercial"}), None)
        rental_cat  = next((t for t in tags if t in {"MTR", "Full"}), None)

        # Score: 10 critical fields × 10 points each
        score = sum([
            10 if l.get("airbnbAccess") else 0,
            10 if (door_code or extra_ci) else 0,
            10 if (wifi_net and wifi_pass) else 0,
            10 if parking_type else 0,
            10 if l.get("houseRules") else 0,
            10 if l.get("contactPhone1") else 0,
            10 if l.get("checkInTimeStart") else 0,
            10 if l.get("airbnbListingUrl") else 0,
            10 if l.get("thumbnailUrl") else 0,
            10 if l.get("averageReviewRating") else 0,
        ])

        contact_name = " ".join(filter(None, [l.get("contactName"), l.get("contactSurName")]))

        return {
            # Source system keys (no breezeway_id yet — Migration 001 makes it nullable)
            "hostaway_id":              l["id"],
            "breezeway_external_id":    str(l["id"]),   # used as Breezeway reference_property_id

            # Naming
            "internal_name":            l.get("internalListingName") or l.get("name"),
            "public_name":              l.get("name"),
            "airbnb_name":              l.get("airbnbName"),
            "thumbnail_url":            l.get("thumbnailUrl"),

            # Location
            "street":                   l.get("street") or l.get("address"),
            "city":                     l.get("city"),
            "state":                    l.get("state"),
            "zipcode":                  l.get("zipcode"),
            "country_code":             l.get("countryCode", "US"),
            "lat":                      l.get("lat"),
            "lng":                      l.get("lng"),
            "timezone":                 l.get("timeZoneName", "America/Chicago"),

            # Configuration
            "property_type":            _PROPERTY_TYPE_MAP.get(l.get("propertyTypeId"), "Other"),
            "bedrooms":                 l.get("bedroomsNumber"),
            "beds":                     l.get("bedsNumber"),
            "bathrooms":                l.get("bathroomsNumber"),
            "max_guests":               l.get("personCapacity"),
            "is_long_term":             (l.get("minNights") or 0) >= 30,

            # Access & entry
            "access_instructions":      l.get("airbnbAccess") or None,
            "door_code":                door_code,
            "door_code_source":         ("structured" if door_code else None),
            "additional_checkin":       extra_ci,
            "checkin_time_start":       l.get("checkInTimeStart"),
            "checkin_time_end":         l.get("checkInTimeEnd"),
            "checkout_time":            l.get("checkOutTime"),
            "special_checkout_notes":   custom.get(_CF_CHECKOUT_NOTES) or None,

            # WiFi
            "wifi_network":             wifi_net,
            "wifi_password":            wifi_pass,
            "wifi_password_source":     ("structured" if wifi_pass else None),
            "wifi_speed_tier":          self._derive_wifi_tier(amenity_names),

            # Parking
            "parking_type":             parking_type,
            "parking_details":          parking_det,
            "has_disabled_parking":     "disabled parking spot" in amenity_names,

            # Policies
            "house_rules":              l.get("houseRules") or None,
            "unit_specific_notes":      custom.get(_CF_UNIT_NOTES) or None,
            "cancellation_policy":      l.get("cancellationPolicy"),
            "min_nights":               l.get("minNights"),
            "max_nights":               l.get("maxNights"),
            "pets_allowed":             "pets allowed" in amenity_names,
            "pet_fee_cents":            (l.get("airbnbPetFeeAmount") or 0) * 100 or None,
            "instant_bookable":         bool(l.get("instantBookable")),

            # Amenity flags (denormalized)
            **self._derive_amenity_flags(amenity_names),

            # Internal classification
            "license_category":         license_cat,
            "rental_category":          rental_cat,
            "owner_commission_pct":     commission_pct,
            "internal_tags":            tags,

            # STR compliance
            "str_license_number":       l.get("propertyLicenseNumber") or None,
            "str_license_type":         l.get("propertyLicenseType") or None,
            "str_license_issued":       l.get("propertyLicenseIssueDate") or None,
            "str_license_expires":      l.get("propertyLicenseExpirationDate") or None,

            # Channels
            "airbnb_url":               l.get("airbnbListingUrl") or None,
            "vrbo_url":                 l.get("vrboListingUrl") or None,
            "airbnb_active":            l.get("airbnbExportStatus") == "exported",
            "vrbo_active":              l.get("vrboExportStatus") == "exported",

            # Financials
            "base_price_cents":         l.get("price"),
            "cleaning_fee_cents":       (l.get("cleaningFee") or 0) * 100 or None,

            # Performance
            "review_rating":            l.get("averageReviewRating"),

            # Contact
            "contact_name":             contact_name or None,
            "contact_email":            l.get("contactEmail") or None,
            "contact_phone":            l.get("contactPhone1") or None,

            # Cleanliness default
            "cleanliness_status":       self._map_cleanliness(l.get("cleannessStatus")),

            # Data quality flags
            "dq_has_structured_wifi":       bool(wifi_net and wifi_pass),
            "dq_has_structured_door_code":  bool(door_code),
            "dq_has_parking_details":       bool(parking_det),
            "dq_has_additional_checkin":    bool(extra_ci),
            "dq_has_unit_notes":            bool(custom.get(_CF_UNIT_NOTES)),
            "dq_completeness_score":        score,

            # Sync metadata
            "hostaway_synced_at":       datetime.datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Field mapping: reservation → reservations row
    # ------------------------------------------------------------------

    def _map_reservation(self, r: dict) -> dict:
        # Hostaway reservation field names (standard PMS conventions)
        return {
            "hostaway_reservation_id":  str(r.get("id") or r.get("reservationId")),
            "guest_name":               r.get("guestName"),
            "guest_email":              r.get("guestEmail"),
            "guest_phone":              r.get("guestPhone"),
            "guest_count":              r.get("numberOfGuests") or r.get("guestCount"),
            "checkin_date":             r.get("arrivalDate"),
            "checkout_date":            r.get("departureDate"),
            "status":                   self._map_reservation_status(r.get("status", "")),
            "channel":                  r.get("channelName") or r.get("source"),
            "external_reservation_id":  r.get("confirmationCode"),
            "total_price_cents":        int((r.get("totalPrice") or 0) * 100),
            "cleaning_fee_cents":       int((r.get("cleaningFee") or 0) * 100),
            "reservation_notes":        r.get("guestNote") or r.get("reservationNotes"),
            "guest_access_code":        r.get("doorCode"),
            "hostaway_synced_at":       datetime.datetime.utcnow().isoformat(),
            # Pipeline resolves this to property UUID
            "_property_ref":            {"hostaway_id": r.get("listingId") or r.get("listingMapId")},
        }

    # ------------------------------------------------------------------
    # Derivation helpers
    # ------------------------------------------------------------------

    def _derive_parking_type(self, amenity_names: set) -> str | None:
        if "garage" in amenity_names or "carport" in amenity_names:
            return "garage"
        if "free parking" in amenity_names or "free parking on premises" in amenity_names:
            return "free"
        if "paid parking" in amenity_names or "paid parking off premises" in amenity_names:
            return "paid"
        if "street parking" in amenity_names:
            return "street"
        return None

    def _derive_wifi_tier(self, amenity_names: set) -> str | None:
        if "wifi speed (100+ mbps)" in amenity_names:
            return "100mbps"
        if "wifi speed (50+ mbps)" in amenity_names:
            return "50mbps"
        if "wifi speed (25+ mbps)" in amenity_names:
            return "25mbps"
        return None

    def _derive_amenity_flags(self, amenity_names: set) -> dict:
        flags = {}
        for col, keywords in _AMENITY_FLAGS.items():
            flags[col] = any(k in amenity_names for k in keywords)
        return flags

    def _map_cleanliness(self, code: str | None) -> str:
        return {"1": "clean", "2": "dirty", "3": "in_progress"}.get(str(code or ""), "unknown")

    def _map_reservation_status(self, status: str) -> str:
        mapping = {
            "new":          "confirmed",
            "confirmed":    "confirmed",
            "modified":     "confirmed",
            "inquiry":      "confirmed",
            "declined":     "cancelled",
            "cancelled":    "cancelled",
            "cancelledByGuest": "cancelled",
            "cancelledByHost":  "cancelled",
            "checkedIn":    "checked_in",
            "checkedOut":   "checked_out",
            "noShow":       "no_show",
        }
        return mapping.get(status, "confirmed")
