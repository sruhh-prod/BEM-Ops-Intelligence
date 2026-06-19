# Property Intelligence Knowledge Base
## Field Analysis & Schema Proposal
**Generated:** 2026-06-17  
**Source:** `hostaway_listings_raw.json` — 100 listings, 145 unique fields  

---

## Part 1 — Field-by-Field Analysis

Every field evaluated for its operational intelligence value, population rate, and MVP eligibility.

Legend for MVP column:
- **YES** — include in MVP; high value, reliable data
- **DERIVED** — not stored directly; computed or extracted from another field
- **FUTURE** — useful later, not MVP-critical
- **NO** — exclude; low value, duplicate, or channel-specific noise

---

### IDENTITY & NAMING

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `id` | 100% | Hostaway's unique listing ID. Primary key for all joins, API calls, and cross-system linking (Breezeway uses this as `reference_property_id`). | **YES** |
| `name` | 100% | Public channel-facing listing name. Used in guest communications and search. | **YES** |
| `internalListingName` | 100% | Best ops identifier — contains address + unit + listing name in one string (e.g. `5605 Tchoupitoulas 1/1 (Uptown) · ...`). Human-readable primary key for operations teams. | **YES** |
| `externalListingName` | 100% | Redundant with `name` in all observed cases. | NO |
| `airbnbName` | 100% | Airbnb-specific title. Useful if names diverge per channel, but duplicates `name` in most cases. | FUTURE |
| `bookingcomPropertyName` | 100% | Booking.com-specific name. Same logic as airbnbName. | NO |
| `homeawayPropertyName` | 100% | VRBO/HomeAway-specific name. Same logic. | NO |
| `homeawayPropertyHeadline` | 100% | VRBO headline, usually matches `name`. | NO |
| `marriottListingName` | 21% | Marriott-specific name, sparsely populated. | NO |

---

### LOCATION

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `street` / `address` | 100% | Full street address. Both fields contain identical values. Use `street`. | **YES** (`street`) |
| `publicAddress` | 100% | Guest-facing address — may intentionally omit unit number. Identical to `street` in all observed cases. | NO (redundant) |
| `city` | 100% | City. All 100 listings are New Orleans. Essential for multi-market expansion. | **YES** |
| `state` | 100% | State code (`LA`). | **YES** |
| `zipcode` | 100% | ZIP code. Enables neighborhood grouping and density analysis. | **YES** |
| `countryCode` | 100% | `US` for all listings. Low signal now, needed at scale. | FUTURE |
| `country` | 100% | Long-form country name. Redundant with `countryCode`. | NO |
| `lat` / `lng` | 100% | GPS coordinates. Enables map views, proximity queries, routing for ops. | **YES** |
| `timeZoneName` | 100% | `America/Chicago` for all. Required for correct check-in/out time display. | **YES** |

---

### PROPERTY CONFIGURATION

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `bedroomsNumber` | 100% | Bedroom count. Core sizing field — drives cleaning scope, supply quantities, pricing. | **YES** |
| `bedsNumber` | 100% | Total bed count (may exceed bedrooms for sofa beds, etc.). | **YES** |
| `bathroomsNumber` | 100% | Bathroom count. Affects cleaning time and scope. | **YES** |
| `bathroomType` | 100% | `private` for all listings. Not operationally useful at current scale. | NO |
| `guestBathroomsNumber` | 15% | Guest-accessible bathrooms specifically. Overlaps with `bathroomsNumber`. | NO |
| `personCapacity` | 100% | Max occupancy (min=2, max=17, avg=5.6). Drives supply ordering, cleaning complexity, and guest communications. | **YES** |
| `guestsIncluded` | 100% | Guests included in base price before extra-person fee applies. | FUTURE |
| `roomType` | 100% | `entire_home` for all 100 listings. No differentiation. | NO |
| `propertyTypeId` | 100% | Numeric type: 2=House (52), 1=Apartment (24), 50=Condo (11), 6=Townhouse (9), other (4). Needs a lookup table but high operational value. | **YES** |
| `listingBedTypes` | 97% | Bed type per bedroom (queen, king, twin, etc.). Essential for guest expectation management and setup verification. | **YES** |
| `squareMeters` | 0% | Unpopulated entirely. | NO |

---

### ACCESS & ENTRY

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `airbnbAccess` | 100% | **Most critical ops field.** Contains the actual entry method in prose: lock type (keypad, lockbox, smart lock), door codes, location of lockbox, gate codes. This is the primary source for access intelligence — all other access fields are subordinate to this. | **YES** |
| `doorSecurityCode` | 1% | Structured door code field — only populated for 1 listing. Access codes for the other 99 are embedded in `airbnbAccess` free text. Flag for NLP extraction. | DERIVED |
| `keyPickup` | 0% | Entirely unpopulated. Key info lives in `airbnbAccess`. | NO |
| `specialInstruction` | 1% | Supplemental check-in notes. Rarely used — 1 listing says "Please check our welcome message." | FUTURE |
| `customFieldId=47948` | 1% | **"Additional Check-In Instructions"** — a custom field. Only 1 listing has a value (full gate + front door + lockbox code string). Extremely high value when populated. | **YES** |
| `checkInTimeStart` | 100% | Standard check-in start hour (15 = 3 PM for 98/100 listings, 16 for 2). | **YES** |
| `checkInTimeEnd` | 5% | Check-in end hour. `26` = anytime (flexible), `23` = 11 PM. Sparsely populated — default assumption should be anytime. | **YES** |
| `checkOutTime` | 100% | Standard check-out hour (11 AM for 99/100 listings). | **YES** |
| `checkinFee` | 100% | Late check-in fee. All zero in current dataset. | FUTURE |
| `allowSameDayBooking` | 100% | Whether same-day bookings are permitted (0 or 1). | FUTURE |
| `sameDayBookingLeadTime` | 100% | Hours of lead time needed for same-day bookings. | FUTURE |
| `instantBookable` | 100% | Whether instant book is on (86% yes). Impacts guest expectation around response time. | **YES** |

---

### HOUSE RULES

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `houseRules` | 100% | Full house rules text. Contains noise policies, age restrictions, event rules, smoking, pets, and check-out procedures. Primary source for rules enforcement and guest communications. | **YES** |
| `airbnbInteraction` | 99% | Host interaction expectations ("we're available 24/7 by call or text"). Useful for guest comms templates. | **YES** |
| `minNights` | 100% | Minimum stay (2 nights for 88 listings, 30 nights for 12 — indicating MTR/long-term units). Critical operational split. | **YES** |
| `maxNights` | 100% | Maximum stay (120 for most). | FUTURE |
| `cancellationPolicy` | 100% | `moderate` (40), `firm` (39), `strict` (21). Needed for guest dispute handling. | **YES** |

---

### WIFI

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `wifiUsername` | 9% | WiFi network name — structured field, populated for 9 listings. | **YES** |
| `wifiPassword` | 9% | WiFi password — structured field, populated for 9 listings. | **YES** |
| `listingAmenities` (WiFi entries) | 100% | All listings have `Internet`, `Wireless`, `Free WiFi`. 42 have `WiFi speed (100+ Mbps)`. Source for WiFi capability flags. | DERIVED |

**Note:** For the 91% without structured WiFi credentials, the password is embedded in `airbnbAccess` or `airbnbNotes` free text. NLP extraction required.

---

### PARKING

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `listingAmenities` (parking entries) | 100% | All listings have a parking amenity: Street (85), Free (41), Paid (11), Disabled (10), Garage (2). Primary structured parking source. | DERIVED |
| `customFieldId=47929` | 2% | **"Parking Details"** — a custom field with parking-specific prose instructions. High value when populated (e.g. "street parking available, remove valuables, lock doors"). Only 2 listings populated. | **YES** |
| `airbnbAccess` | 100% | Many listings include parking context in access field (e.g. "one off-street parking spot"). Requires extraction. | DERIVED |

---

### AMENITIES (STRUCTURED)

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `listingAmenities` | 100% | Array of all amenity objects with `amenityId` and `amenityName`. 57 amenities on average per listing. The richest structured attribute source. Drives guest expectation management, supply checklists, and marketing. | **YES** (parsed/normalized) |

Key amenity signals for ops intelligence:

| Amenity | Count | Ops Relevance |
|---|---|---|
| Street parking / Free parking / Paid parking | 85–41 | Parking type per unit |
| Pets allowed | 15 | Pet policy — drives cleaning protocol |
| Pool / Hot tub | varies | Drives safety inspection and maintenance tasks |
| Washing Machine / Dryer | 97 | Laundry setup verification |
| Dishwasher | 86 | Kitchen equipment checklist |
| Private entrance | 96 | Entry type classification |
| Contactless Check-In/Out | ~70 | Confirms keyless entry |
| Long term stays allowed | 92 | MTR eligibility |
| WiFi speed (100+ Mbps) | 42 | WiFi tier classification |

---

### GUEST NOTES & DESCRIPTIONS

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `airbnbNotes` | 100% | Additional guest-facing notes: multi-property info, storm/safety notices, local tips. Often contains WiFi credentials. | **YES** |
| `airbnbSpace` | 100% | Detailed space description — layout, furnishings, unique features. Useful for property profiles and guest comms. | **YES** |
| `airbnbSummary` | 100% | Neighborhood and property summary. Duplicate of `description` in most cases. | NO (use `description`) |
| `description` | 100% | Master property description — richest narrative source. | **YES** |
| `airbnbTransit` | 100% | Transit and getting-around notes. High value for concierge-style guest communications. | **YES** |
| `airbnbNeighborhoodOverview` | 99% | Local area overview (restaurants, attractions, distances). Valuable for guest guides. | **YES** |
| `airbnbInteraction` | 99% | Host availability and response style note. | **YES** |
| `homeawayPropertyDescription` | 96% | VRBO/HomeAway description — near-duplicate of `description`. | NO |
| `bookingcomPropertyDescription` | 96% | Booking.com description — near-duplicate. | NO |
| `customFieldId=48149` | 1% | **"Unit Specific Notes"** — high-value custom field for property quirks (e.g. "owner's dog Doug lives on site"). Critical for ops briefings. | **YES** |
| `customFieldId=47947` | 2% | **"Special Check-Out Instructions"** — departure-specific instructions. | **YES** |

---

### FINANCIALS & PRICING

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `price` | 100% | Base nightly rate (in cents: 5000 = $50? or dollars: $5,000). Min=5000, Max=20000, avg=5600. Verify unit. Needed for revenue intelligence. | **YES** |
| `cleaningFee` | 100% | Cleaning fee per stay. Revenue and ops planning. | **YES** |
| `priceForExtraPerson` | 100% | Extra guest fee (avg $40/night). | FUTURE |
| `refundableDamageDeposit` | 100% | All zero — damage deposits not collected via Hostaway. | NO |
| `weeklyDiscount` | 93% | Weekly stay discount multiplier (e.g. 0.9 = 10% off). | FUTURE |
| `monthlyDiscount` | 93% | Monthly stay discount (e.g. 0.75 = 25% off). | FUTURE |
| `guestNightlyTax` | 100% | All zero. | NO |
| `guestStayTax` | 100% | All zero. | NO |
| `guestPerPersonPerNightTax` | 100% | All zero. | NO |
| `propertyRentTax` | 100% | All zero. | NO |
| `checkinFee` | 100% | All zero. | NO |
| `airbnbPetFeeAmount` | 15% | Pet fee per stay (e.g. $200). Only for 15 pet-friendly listings. | FUTURE |

---

### PERFORMANCE & QUALITY

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `averageReviewRating` | 99% | Review score out of 10 (min=9.2, max=10.0, avg=9.82). Quality signal. Flags underperforming properties for attention. | **YES** |
| `cleannessStatus` | 63% | Current clean/dirty status (all observed values = `2`). Inconsistently populated — 37% of listings have no status. Operationally important but unreliable from Hostaway. | **YES** (with caveat) |

---

### CONTACT & OWNER

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `contactName` + `contactSurName` | 100% | Owner or manager name. | **YES** |
| `contactEmail` | 100% | Contact email (all `stay@bigeasymanagement.com` — same for every listing, indicating it's the company not owner). | **YES** |
| `contactPhone1` | 100% | Primary contact phone. | **YES** |
| `contactPhone2` | 1% | Secondary phone — 1 listing only. | FUTURE |
| `contactLanguage` | 2% | Language preference — 2 listings. | NO |

---

### CHANNEL & LISTING MANAGEMENT

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `airbnbListingUrl` | 100% | Airbnb listing URL. Useful for quick navigation to source channel. | **YES** |
| `vrboListingUrl` | 99% | VRBO URL. | **YES** |
| `expediaListingUrl` | 82% | Expedia URL. | FUTURE |
| `airbnbExportStatus` | 100% | All `exported`. Channel sync status. | FUTURE |
| `vrboExportStatus` | 74% | `exported` for 74 listings, null for 26. | FUTURE |
| `bookingcomExportStatus` | 9% | Only 9 on Booking.com. | FUTURE |
| `expediaExportStatus` | 9% | Only 9 on Expedia. | FUTURE |
| `instantBookable` | 100% | 86% instant book enabled. | **YES** |

---

### PROPERTY LICENSE

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `propertyLicenseNumber` | 5% | STR license number (e.g. `23-NSTR-17599`). Only 5 listings. Critical for compliance where applicable. | **YES** |
| `propertyLicenseType` | 3% | License type (e.g. `STR`). | **YES** |
| `propertyLicenseIssueDate` | 5% | License issue date. | **YES** |
| `propertyLicenseExpirationDate` | 5% | License expiration date. **Compliance alert trigger** — 2 of the 5 have already expired (2024-06-30). | **YES** |

---

### IMAGES

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `thumbnailUrl` | 88% | Primary thumbnail image URL. | **YES** |
| `listingImages` | 100% | Full image array with captions (avg 38 images, min 15, max 73). Captions describe rooms. | FUTURE |

---

### TAGS (INTERNAL TAXONOMY)

| Field | Population | Purpose | MVP |
|---|---|---|---|
| `listingTags` | 100% | Internal tag array. Key tags observed: `STR`(88), `Full`(91), `Commercial`(53), `1BR`/`2BR`/`3BR`/`4BR`/`5BR`, `MG`(29), `MTR`(12), `Pets Allowed`(15), `Hotel License`(11), `VRBO Approval Req'd`(13), `OM`(7). These encode operational categories not available in any other field. | **YES** |

Tag glossary (inferred):
- `Full` — full property listing (vs. room)
- `STR` / `Hotel License` — license type
- `Commercial` / `Commercial-C/D` — commercial zoning
- `MTR` — mid-term rental
- `MG` — likely Mardi Gras pricing tier
- `20%` / `25%` / `23%` / `22%` — owner commission percentages
- `VRBO Approval Req'd` — manual VRBO approval required
- `OM` / `MA` / `Resi-1` — likely internal operational classifications
- `Pets Allowed` — pet-friendly flag (matches `airbnbPetFeeAmount` population)

---

### CUSTOM FIELDS (HIGHEST VALUE DISCOVERIES)

| Field | Custom Field Name | Population | Purpose | MVP |
|---|---|---|---|---|
| `customFieldId=47929` | **Parking Details** | 2% | Parking-specific prose instructions. Critical for guest pre-arrival comms. Low population — requires data entry initiative. | **YES** |
| `customFieldId=47947` | **Special Check-Out Instructions** | 2% | Departure-specific instructions (e.g. returning parking permits). | **YES** |
| `customFieldId=47948` | **Additional Check-In Instructions** | 1% | Structured access codes and supplemental entry notes. | **YES** |
| `customFieldId=48149` | **Unit Specific Notes** | 1% | Property quirks, owner notes, special situations. | **YES** |

> **Critical finding:** These 4 custom fields are exactly the structured data fields that operations teams need — but only 1–2% of listings have them populated. The MVP should include these fields and make their completion a data quality initiative.

---

### FIELDS TO EXCLUDE FROM MVP

| Field | Reason |
|---|---|
| `airbnbBookingLeadTime` / `airbnbBookingLeadTimeAllowRequestToBook` | Channel-specific booking config |
| `airbnbOfficialListingMarkup` / `homeawayApiMarkup` / `marriottListingMarkup` / `bookingEngineMarkup` / `partnersListingMarkup` | Revenue/yield management — separate system concern |
| `airbnbCancellationPolicyId` / `vrboCancellationPolicyId` / `marriottCancellationPolicyId` / `bookingCancellationPolicyId` / `cancellationPolicyId` | Internal policy IDs; `cancellationPolicy` text is sufficient |
| `homeawayPropertyDescription` / `bookingcomPropertyDescription` / `airbnbSummary` | Near-duplicates of `description` |
| `homeawayPropertyName` / `bookingcomPropertyName` / `bookingcomPropertyRoomName` | Channel-specific names |
| `guestNightlyTax` / `guestStayTax` / `guestPerPersonPerNightTax` / `propertyRentTax` | All zero |
| `refundableDamageDeposit` | All zero |
| `checkinFee` | All zero |
| All invoicing fields | 0% populated |
| `isRentalAgreementActive` / `attachment` / `cleaningInstruction` / `listingFeeSetting` / `listingSettings` / `listingUnits` | 0% populated |
| `squareMeters` / `starRating` / `specialStatus` | 0% populated |
| `language` | `en` for all — no signal |
| `countryCode` | `US` for all — no signal at current scale |
| `bathroomType` | `private` for all — no signal |
| `roomType` | `entire_home` for all — no signal |
| `currencyCode` | `USD` for all — no signal |
| `insertedOn` | Admin metadata, not ops-relevant in MVP |

---

## Part 2 — Property Intelligence Schema (MVP)

### Design Principles

1. **Answer operational questions, not store raw data.** Every field maps to a specific question a team member might ask.
2. **One property, one truth.** No channel-specific duplicates. Channel URLs are pointers, not repeated content.
3. **Separate facts from free text.** Structured fields are first-class. Free text is preserved but labeled as requiring extraction.
4. **Expose data gaps explicitly.** Fields that should be populated but aren't are represented as `null` with a `_source` annotation.
5. **Breezeway-ready.** Schema is designed to accept Breezeway task data as a second layer via `hostaway_id` join key.

---

### Schema Definition

```
PROPERTY
├── IDENTITY
│   ├── hostaway_id              INT       — primary key, join key for Breezeway
│   ├── internal_name            STRING    — ops label (address + unit + name)
│   ├── public_name              STRING    — guest-facing name
│   └── thumbnail_url            STRING    — primary photo

├── LOCATION
│   ├── street                   STRING
│   ├── city                     STRING
│   ├── state                    STRING
│   ├── zipcode                  STRING
│   ├── lat                      FLOAT
│   ├── lng                      FLOAT
│   └── timezone                 STRING

├── CONFIGURATION
│   ├── property_type            STRING    — derived from propertyTypeId lookup
│   ├── bedrooms                 INT
│   ├── beds                     INT
│   ├── bathrooms                INT
│   ├── max_guests               INT
│   ├── bed_layout               ARRAY     — [{bedroom_number, bed_type, quantity}]
│   └── is_long_term             BOOL      — derived: minNights >= 30

├── ACCESS & ENTRY
│   ├── access_instructions      STRING    — airbnbAccess (primary)
│   ├── door_code                STRING    — doorSecurityCode if populated, else EXTRACTED
│   ├── additional_checkin       STRING    — customField "Additional Check-In Instructions"
│   ├── checkin_time_start       INT       — hour (e.g. 15 = 3 PM)
│   ├── checkin_time_end         INT       — hour (26 = anytime)
│   └── checkout_time            INT       — hour (e.g. 11 = 11 AM)

├── WIFI
│   ├── wifi_network             STRING    — wifiUsername if populated, else EXTRACTED
│   ├── wifi_password            STRING    — wifiPassword if populated, else EXTRACTED
│   └── wifi_speed_tier          STRING    — derived from listingAmenities

├── PARKING
│   ├── parking_type             STRING    — derived from listingAmenities (street/free/paid/garage)
│   ├── parking_details          STRING    — customField "Parking Details"
│   └── has_disabled_parking     BOOL      — derived from listingAmenities

├── HOUSE RULES & POLICIES
│   ├── house_rules              STRING    — full rules text
│   ├── checkout_instructions    STRING    — customField "Special Check-Out Instructions"
│   ├── unit_specific_notes      STRING    — customField "Unit Specific Notes"
│   ├── cancellation_policy      STRING    — moderate / firm / strict
│   ├── min_nights               INT
│   ├── pets_allowed             BOOL      — derived from listingAmenities
│   ├── pet_fee                  INT       — airbnbPetFeeAmount
│   └── instant_bookable         BOOL

├── AMENITIES
│   ├── amenity_list             ARRAY     — [{amenity_id, amenity_name}] full normalized list
│   ├── has_pool                 BOOL      — derived
│   ├── has_hot_tub              BOOL      — derived
│   ├── has_ev_charger           BOOL      — derived
│   ├── has_washer_dryer         BOOL      — derived
│   └── has_dishwasher           BOOL      — derived

├── GUEST COMMUNICATIONS
│   ├── description              STRING    — master property description
│   ├── space_description        STRING    — airbnbSpace (layout + features)
│   ├── neighborhood_overview    STRING    — airbnbNeighborhoodOverview
│   ├── transit_notes            STRING    — airbnbTransit
│   ├── guest_interaction_notes  STRING    — airbnbInteraction
│   └── additional_notes         STRING    — airbnbNotes

├── CHANNELS
│   ├── airbnb_url               STRING
│   ├── vrbo_url                 STRING
│   ├── airbnb_active            BOOL      — derived from airbnbExportStatus
│   └── vrbo_active              BOOL      — derived from vrboExportStatus

├── FINANCIALS
│   ├── base_price               INT       — price (verify unit: cents vs dollars)
│   ├── cleaning_fee             INT
│   └── review_rating            FLOAT

├── COMPLIANCE
│   ├── str_license_number       STRING
│   ├── str_license_type         STRING
│   ├── str_license_issued       DATE
│   └── str_license_expires      DATE      — alert if within 90 days or expired

├── CONTACT
│   ├── contact_name             STRING    — first + last
│   ├── contact_email            STRING
│   └── contact_phone            STRING

├── INTERNAL CLASSIFICATION (from listingTags)
│   ├── license_category         STRING    — STR / Hotel License / Commercial
│   ├── rental_category          STRING    — MTR / Full
│   ├── owner_commission_pct     INT       — extracted from % tags (20/22/23/25%)
│   └── internal_tags            ARRAY     — all raw tag names preserved

└── DATA QUALITY METADATA
    ├── has_structured_wifi      BOOL      — wifiPassword populated
    ├── has_structured_door_code BOOL      — doorSecurityCode populated
    ├── has_parking_details      BOOL      — customField 47929 populated
    ├── has_additional_checkin   BOOL      — customField 47948 populated
    ├── has_unit_notes           BOOL      — customField 48149 populated
    ├── license_expired          BOOL      — str_license_expires < today
    └── last_synced_from_hostaway DATETIME
```

---

### Operational Question Mapping

Every schema section is designed to answer specific questions from each team:

#### Communications Team
| Question | Schema Field(s) |
|---|---|
| What's the WiFi password at this property? | `wifi_network`, `wifi_password` |
| How do guests get in? | `access_instructions`, `door_code`, `additional_checkin` |
| What are the house rules for this property? | `house_rules` |
| What time can guests check in/out? | `checkin_time_start`, `checkin_time_end`, `checkout_time` |
| Is parking available and where? | `parking_type`, `parking_details` |
| Is this property pet-friendly? What's the fee? | `pets_allowed`, `pet_fee` |
| What's near this property? | `neighborhood_overview`, `transit_notes` |
| What makes this property special? | `space_description`, `additional_notes` |

#### Operations Team
| Question | Schema Field(s) |
|---|---|
| What's the layout of this property? | `bedrooms`, `beds`, `bathrooms`, `bed_layout`, `max_guests` |
| What appliances are in this unit? | `amenity_list`, `has_washer_dryer`, `has_dishwasher` |
| Are there any quirks with this unit? | `unit_specific_notes` |
| What are the check-out requirements? | `checkout_instructions`, `house_rules` |
| Is the property clean/ready? | `cleannessStatus` (from Hostaway) + Breezeway task data |
| Which properties are long-term rentals? | `is_long_term`, `min_nights`, internal tag `MTR` |
| Which properties allow pets and what's the protocol? | `pets_allowed`, `pet_fee`, `house_rules` |
| How do we get access if there's an emergency? | `access_instructions`, `door_code`, `contact_phone` |

#### Leadership Team
| Question | Schema Field(s) |
|---|---|
| How many properties do we manage? | Count of `hostaway_id` |
| What's our portfolio breakdown by size? | `bedrooms`, `property_type` distribution |
| Which properties have the highest review ratings? | `review_rating` sorted |
| Which properties are on which channels? | `airbnb_active`, `vrbo_active` |
| What's our average cleaning fee? | `cleaning_fee` aggregated |
| Which STR licenses are expiring soon? | `str_license_expires` — alert within 90 days |
| Which properties are instant bookable? | `instant_bookable` |
| What's our commission structure by property? | `owner_commission_pct` from tags |

---

## Part 3 — Data Quality Gap Analysis

### Fields to Populate Immediately (Ops Impact)

| Custom Field | Current Population | Target | Action |
|---|---|---|---|
| Parking Details (47929) | 2% | 100% | Data entry campaign — short text, huge guest value |
| Additional Check-In Instructions (47948) | 1% | 100% | Migrate door codes out of `airbnbAccess` prose |
| Unit Specific Notes (48149) | 1% | 100% | Ops team review session per property |
| Special Check-Out Instructions (47947) | 2% | 100% | Standardize departure notes |
| `wifiPassword` / `wifiUsername` | 9% | 100% | Extract from `airbnbAccess`/`airbnbNotes` via NLP |
| `doorSecurityCode` | 1% | 100% | Extract from `airbnbAccess` via regex |

### Derived Fields to Compute at Ingest

| Schema Field | Source | Derivation |
|---|---|---|
| `property_type` | `propertyTypeId` | Lookup: 1=Apartment, 2=House, 3=B&B, 6=Townhouse, 8=Villa, 10=Cabin, 48=Guest Suite, 50=Condo |
| `parking_type` | `listingAmenities` | Filter amenityName contains "parking"; map to street/free/paid/garage |
| `has_pool` | `listingAmenities` | amenityName == "Pool" |
| `has_washer_dryer` | `listingAmenities` | amenityName in ["Washing Machine", "Dryer"] |
| `wifi_speed_tier` | `listingAmenities` | Extract from "WiFi speed (X Mbps)" amenity |
| `pets_allowed` | `listingAmenities` | amenityName == "Pets allowed" |
| `is_long_term` | `minNights` | minNights >= 30 |
| `airbnb_active` | `airbnbExportStatus` | == "exported" |
| `vrbo_active` | `vrboExportStatus` | == "exported" |
| `license_category` | `listingTags` | Tag in ["STR", "Hotel License", "Commercial"] |
| `owner_commission_pct` | `listingTags` | Tag matches regex `^\d{2}%$` |
| `license_expired` | `str_license_expires` | date < today |

### Hostaway Fields Where Breezeway Wins

| Intelligence Need | Hostaway Limitation | Breezeway Solution |
|---|---|---|
| Real-time cleanliness | `cleannessStatus` 63% populated, not real-time | Task-driven, always current |
| Access code structure | Embedded in prose, 1% structured | Smart lock API, time-bound codes |
| Maintenance history | No task concept | Full task graph per property |
| Inspection records | None | Inspection task type with photos |
| Staff assignments | None | People + subdepartment API |
