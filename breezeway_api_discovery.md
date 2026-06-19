# Breezeway API Discovery Report
**Generated:** 2026-06-17  
**Sources:** developer.breezeway.io, help.breezeway.io, breezeway.io  
**Purpose:** Evaluate Breezeway as a data source for Operations Intelligence platform

---

## 1. Public API Overview

Breezeway provides a **fully public REST API** at `https://api.breezeway.io/public/` with a dedicated developer hub at [developer.breezeway.io](https://developer.breezeway.io).

- **API Reference:** Organized, endpoint-by-endpoint documentation with OpenAPI spec available
- **Machine-readable index:** `https://developer.breezeway.io/llms.txt` (full Markdown + OpenAPI)
- **Webhook system:** Push notifications for real-time task and property status changes
- **Cross-company access:** Partners can query across multiple accounts with a single credential set

---

## 2. Authentication

| Property | Detail |
|---|---|
| **Type** | JWT (JSON Web Token) — not OAuth2 |
| **Token endpoint** | `POST https://api.breezeway.io/public/auth/v1/` |
| **Required params** | `client_id`, `client_secret` (JSON body) |
| **Access token lifetime** | 24 hours |
| **Refresh token lifetime** | 30 days (rotating — each refresh issues a new refresh token) |
| **Auth header format** | `Authorization: JWT <access_token>` |
| **Refresh endpoint** | `POST https://api.breezeway.io/public/auth/v1/refresh` |
| **Rate limit** | 1 req/min on token endpoints (HTTP 429 if exceeded) |

**Credential acquisition:** Requires an active Breezeway account. Submit a request form through the developer hub. Partners can apply for cross-company credentials (single key, multiple accounts).

**Comparison to Hostaway:** Hostaway uses OAuth2 `client_credentials` with a 2-year token. Breezeway uses rotating JWTs with 24-hour access tokens — requires token refresh management in any integration.

---

## 3. Available Endpoints — Full Inventory

### Authorization
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/auth/v1/` | Obtain access + refresh tokens |
| POST | `/public/auth/v1/refresh` | Refresh access token |

### Properties
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/home` | Create property |
| POST | `/public/inventory/v1/home/external/{id}` | Create/update by external ID |
| GET | `/public/inventory/v1/home/{id}` | Retrieve property |
| GET | `/public/inventory/v1/home/external/{id}` | Retrieve by external ID |
| PUT | `/public/inventory/v1/home/{id}` | Update property |
| PUT | `/public/inventory/v1/home/external/{id}` | Update by external ID |
| PATCH | `/public/inventory/v1/home/{id}/external-id` | Update external ID |
| GET | `/public/inventory/v1/home` | List all properties |
| GET | `/public/inventory/v1/home/external` | List by external ID |
| DELETE | `/public/inventory/v1/home/{id}` | Delete property |
| POST | `/public/inventory/v1/home/{id}/bedroom` | Increase bedroom count |
| POST | `/public/inventory/v1/home/{id}/bathroom` | Increase bathroom count |
| PUT | `/public/inventory/v1/home/{id}/photo` | Update default photo |

### Property Contacts
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/home/{id}/contact` | Create property contact |
| GET | `/public/inventory/v1/home/{id}/contact/{contact_id}` | Retrieve contact |
| PUT | `/public/inventory/v1/home/{id}/contact/{contact_id}` | Update contact |
| DELETE | `/public/inventory/v1/home/{id}/contact/{contact_id}` | Delete contact |
| GET | `/public/inventory/v1/home/{id}/contact` | List contacts |

### Property Tags
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/home/{id}/tag` | Add tags |
| PUT | `/public/inventory/v1/home/{id}/tag` | Update tags |
| DELETE | `/public/inventory/v1/home/{id}/tag` | Delete tags |
| GET | `/public/inventory/v1/home/tag` | List available tags |

### Reservations
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/reservation/external/{id}` | Create/update by external ID |
| POST | `/public/inventory/v1/reservation` | Create reservation |
| GET | `/public/inventory/v1/reservation/{id}` | Retrieve reservation |
| GET | `/public/inventory/v1/reservation/external/{id}` | Retrieve by external ID |
| PUT | `/public/inventory/v1/reservation/{id}` | Update reservation |
| DELETE | `/public/inventory/v1/reservation/{id}` | Delete reservation |
| GET | `/public/inventory/v1/reservation` | List reservations |
| GET | `/public/inventory/v1/reservation/external` | List by external ID |
| POST | `/public/inventory/v1/reservation/{id}/check-in` | Trigger check-in |
| POST | `/public/inventory/v1/reservation/{id}/check-out` | Trigger check-out |

### Tasks
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/task` | Create task |
| GET | `/public/inventory/v1/task/{id}` | Retrieve task |
| PUT | `/public/inventory/v1/task/{id}` | Update task |
| DELETE | `/public/inventory/v1/task/{id}` | Delete task |
| POST | `/public/inventory/v1/task/{id}/close` | Close task |
| POST | `/public/inventory/v1/task/{id}/approve` | Approve task |
| POST | `/public/inventory/v1/task/{id}/reopen` | Reopen task |
| GET | `/public/inventory/v1/task` | List tasks |
| POST | `/public/inventory/v1/task/{id}/comment` | Add comment to task |
| GET | `/public/inventory/v1/task/{id}/comments` | Retrieve task comments |
| POST | `/public/inventory/v1/task/{id}/photo` | Add photo to task |
| GET | `/public/inventory/v1/task/{id}/requirements` | Retrieve task checklist responses |

### Task Tags
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/task/{id}/tag` | Add tags |
| GET | `/public/inventory/v1/task/{id}/tag` | Get tags |
| DELETE | `/public/inventory/v1/task/{id}/tag` | Delete tags |
| GET | `/public/inventory/v1/task/tag` | List available tags |

### Reservation–Task Links
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/reservation/{id}/task` | Link task to reservation |
| DELETE | `/public/inventory/v1/reservation/{id}/task/{task_id}` | Unlink task |
| GET | `/public/inventory/v1/reservation/{id}/task` | Get tasks linked to reservation |

### People & Organization
| Method | Endpoint | Description |
|---|---|---|
| GET | `/public/inventory/v1/person` | List people |
| GET | `/public/inventory/v1/person/{id}` | Retrieve person |
| POST | `/public/inventory/v1/person/{id}/invitation` | Resend invitation |
| GET | `/public/inventory/v1/company` | List companies |
| GET | `/public/inventory/v1/subdepartment` | List subdepartments |

### Templates & Supplies
| Method | Endpoint | Description |
|---|---|---|
| GET | `/public/inventory/v1/template` | List task templates |
| GET | `/public/inventory/v1/supply` | List supplies |

### Webhooks
| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/inventory/v1/subscribe` | Create webhook subscription |
| DELETE | `/public/inventory/v1/subscribe/{id}` | Delete subscription |
| GET | `/public/inventory/v1/subscribe` | List subscriptions |

---

## 4. Tasks — Full Object Schema

Tasks are Breezeway's richest data object. The full task object contains:

### Identifiers & Relationships
| Field | Type | Description |
|---|---|---|
| `id` | int | Breezeway task ID |
| `company_id` | int | Company the task belongs to |
| `task_series_id` | int | Links recurring task instances |
| `parent_task_id` | int | For subtasks |
| `task_report_url` | string | URL to shareable task report |

### Core Details
| Field | Type | Description |
|---|---|---|
| `name` | string | Task name |
| `description` | string | Task description |
| `summary` | TaskNote | `{id, note, created_at, updated_at}` — rich note object |
| `template` | object | `{id, name}` — template used |
| `tags` | array | String tags |

### Department & Type
| Field | Type | Description |
|---|---|---|
| `department` | TypeDepartment | `{id, code, name}` — housekeeping / maintenance / inspection / safety |
| `type_department` | enum | `housekeeping`, `maintenance`, `inspection`, `safety` |
| `type_priority` | enum | `urgent`, `high`, `normal`, `low`, `watch` |
| `requested_by` | TypeTaskRequester | Who/what initiated the task (13 options) |
| `subdepartment_id` | int | Sub-team within a department |

### Status & Lifecycle
| Field | Type | Description |
|---|---|---|
| `status` | TypeTaskStatus | `{id, code, name}` |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modified |
| `deleted_at` | datetime | Soft delete timestamp |
| `due_date` | date | Scheduled date |
| `due_time` | time | Scheduled time |
| `end_date` | date | End of window |
| `started_at` | datetime | When work began |
| `finished_at` | datetime | When work completed |
| `assigned_at` | datetime | When assigned |

### People
| Field | Type | Description |
|---|---|---|
| `created_by` | CompanyPerson | `{id, full_name}` |
| `started_by` | CompanyPerson | `{id, full_name}` |
| `finished_by` | CompanyPerson | `{id, full_name}` |
| `assignments` | array | Array of TaskPeople objects |
| `assign_default_workers` | bool | Auto-assign from template/dept defaults |

### Time & Cost
| Field | Type | Description |
|---|---|---|
| `estimated_time` | float | Estimated hours |
| `total_time` | float | Actual time tracked |
| `estimated_rate` | float | Expected pay rate |
| `rate_paid` | float | Actual compensation |
| `rate_type` | enum | `piece` or `hourly` |
| `total_cost` | float | Total cost |
| `itemized_cost` | array | Line-item costs |
| `bill_to` | object | Who gets charged (newest addition) |
| `costs` | array | `[{id, cost, type_cost, description, created_at, updated_at, deleted_at}]` |
| `billable` | bool | Whether task is billable |

### Resources & Evidence
| Field | Type | Description |
|---|---|---|
| `supplies` | array | `[{id, name, size, quantity, unit_cost, description}]` |
| `photos` | array | Array of photo URLs |
| `requirements` | object | Checklist responses (retrieved via separate endpoint) |
| `home` | Home | `{id, name}` — linked property |
| `linked_reservation` | object | `{id, external_reservation_id}` |
| `reported_tasks` | array | IDs of tasks spawned from this task |

### Comments
| Field | Type | Description |
|---|---|---|
| `comments` | array | `[{id, comment, comment_by, created_at}]` |

---

## 5. Task Comments

- **Endpoint:** `GET /public/inventory/v1/task/{id}/comments`
- **Webhook event:** `task-comment-created`
- **Comment object fields:** `id`, `comment` (text), `comment_by` (person), `created_at`
- Comments are also embedded in the full task object response

---

## 6. Property Notes

Breezeway's property notes model is **more structured than Hostaway's**:

- **Property contacts** are a first-class API resource — create, update, delete, list, with multiple contacts per property
- **`summary` field on tasks** (`TaskNote` object with `id`, `note`, `created_at`, `updated_at`) acts as a structured note on any task
- **Property tags** allow categorical labeling
- **Lock/access data:** Breezeway natively manages access codes tied to reservations and smart locks — synced in real time (November 2025 addition: real-time lock status, battery level, time-bound access codes)
- **Note:** Dedicated "property notes" free-text field not confirmed in public API schema — this may be a UI-only feature or live within the property object body (requires authenticated test to confirm)

---

## 7. Guest Notes

- **Reservation Notes:** Notes from Guesty/Hostaway reservations are pulled into Breezeway's `Reservation Notes` field during sync
- **Guest access codes:** Retrieved from either the PMS Lock Manager or the reservation keycode field
- **Guest phone number:** Displayed in reservation flyout (November 2025)
- **Upsell/messaging fields:** Upsell name, conversation history, Airbnb channel filtering
- The reservation object supports `external_reservation_id` for cross-referencing back to Hostaway

---

## 8. Reservations

| Field Category | Fields |
|---|---|
| Identifiers | `id`, `external_reservation_id` |
| Property link | `home_id`, `reference_property_id` |
| Guest info | Guest name, phone number (confirmed in UI; API schema requires test) |
| Dates | Check-in date/time, check-out date/time |
| Notes | Reservation notes (pulled from PMS) |
| Access | Guest access codes (from PMS lock manager or keycode field) |
| Tags | Reservation tags |
| Task links | Tasks linked to this reservation |
| Lifecycle | `check-in` and `check-out` action endpoints |

Reservations sync from Hostaway every hour automatically once the integration is active.

---

## 9. Attachments / Photos

Breezeway manages photos at multiple levels:

| Attachment Type | Endpoint / Field |
|---|---|
| **Task photos** | `POST /task/{id}/photo` — add; `photos[]` array in task response |
| **Property default photo** | `PUT /home/{id}/photo` |
| **Property Photos** (resource) | Listed as a separate API resource in the index |
| **Task requirements** | `GET /task/{id}/requirements` — checklist responses may include photo requirements |

Photos in tasks are stored as a `string[]` of URLs in the task object.

---

## 10. Check-In Instructions

Breezeway is specifically designed around check-in automation:

| Source | What It Contains |
|---|---|
| **`airbnbAccess` (via Hostaway sync)** | Entry method prose — pulled into Breezeway reservation on sync |
| **Smart Lock integration** | Real-time access codes, lock status, battery level — 30+ lock device brands |
| **Reservation check-in endpoint** | `POST /reservation/{id}/check-in` — triggers check-in event |
| **Guest messaging** | Breezeway sends automated SMS with access codes, WiFi, and check-in instructions |
| **Breezeway Guide** | Guest-facing guidebook with WiFi password, departure instructions, local recs |
| **Time-bound access codes** | November 2025: codes with expiration tied to reservation window |

**Critical finding:** Breezeway is the downstream consumer of check-in instructions from Hostaway — but it adds a structured smart lock layer on top that Hostaway does not have.

---

## 11. Webhook Events (Real-Time)

### Task Events (13 total)
`task-created` · `task-committed` · `task-updated` · `task-deleted` · `task-assignment-updated` · `task-started` · `task-paused` · `task-resumed` · `task-completed` · `task-cost-updated` · `task-supplies-updated` · `task-comment-created`

### Property Events
`property-status` — fires on any property status change

Each webhook payload includes `event_type`, full task/property object, and `last_updated` for deduplication.

---

## 12. Data Hostaway Has That Breezeway Does Not

| Data | Hostaway | Breezeway |
|---|---|---|
| Listing descriptions (Airbnb/VRBO/Booking.com) | Full text | Not stored |
| Channel URLs (Airbnb, VRBO, Expedia) | All channels | Not stored |
| Pricing (base, extra person, fees, markup) | Full pricing model | Not stored |
| Cancellation policies | Per channel | Not stored |
| Booking lead times | Per channel | Not stored |
| Review ratings | `averageReviewRating` | Not stored |
| Listing images | Full gallery | Property default photo only |
| `airbnbSpace`, `airbnbSummary`, `airbnbTransit` | Full text | Not stored |
| Property license numbers | Yes (5%) | Not stored |

## 13. Data Breezeway Has That Hostaway Does Not

| Data | Breezeway | Hostaway |
|---|---|---|
| **Tasks** | Full task lifecycle, costs, assignees, comments, photos, requirements | None |
| **Task checklists/requirements** | Structured checklist with completion state | None |
| **Smart lock integration** | Real-time lock status, battery, time-bound codes | Not natively |
| **Task cost & billing** | Labor costs, supplies, `bill_to` | None |
| **Staff management** | People, subdepartments, assignments | None |
| **Maintenance history** | Full task history per property | None |
| **Inspection records** | Inspection tasks with photo evidence | None |
| **Automated workflows** | Template-driven task automation | None |
| **Real-time webhooks** | 13 task event types + property status | Polling only |
| **Property contacts (structured)** | First-class resource with CRUD API | Flat contact fields only |
| **Reservation–task links** | Tasks explicitly tied to reservations | None |
| **Guest messaging** | SMS automation with access codes | None |
| `cleannessStatus` (structured) | Task-driven clean status | Code only (63% populated) |

---

## 14. Recommendation: Primary Source of Truth

### Verdict: **Hybrid — with clear ownership boundaries**

Neither system alone is sufficient. They are architecturally complementary, not redundant.

---

### Ownership Map

| Data Domain | Primary Source | Reason |
|---|---|---|
| **Property identity** (name, address, GPS, beds/baths) | Hostaway | 100% populated, single source of record |
| **Channel listings** (Airbnb, VRBO, Booking.com URLs, descriptions) | Hostaway | Breezeway does not store channel data |
| **Pricing & financials** | Hostaway | Not available in Breezeway |
| **Guest access instructions** | Breezeway | Smart lock layer, time-bound codes, real-time status |
| **WiFi credentials** | Hostaway (raw) → Breezeway (distributed) | Extract from Hostaway; Breezeway delivers to guests |
| **House rules** | Hostaway | `houseRules` 100% populated, not in Breezeway |
| **Operational tasks** | Breezeway | Full task graph — Hostaway has nothing here |
| **Maintenance history** | Breezeway | Task records per property |
| **Cleaning status** | Breezeway | Task-driven; more reliable than Hostaway's 63% field |
| **Staff & assignments** | Breezeway | People API, subdepartments, assignments |
| **Costs & labor** | Breezeway | Task cost tracking not in Hostaway |
| **Inspection records** | Breezeway | Inspection task type with photo evidence |
| **Reservation sync** | Both (Hostaway creates, Breezeway consumes) | Breezeway polls Hostaway every hour |
| **Real-time events** | Breezeway | Webhook system; Hostaway requires polling |

---

### Architecture Recommendation

```
Hostaway  ──────────────────────────────┐
 • Property master record               │
 • Channel listings & URLs              │  JOIN on
 • Pricing & fees                       ├─ listing ID /
 • House rules & descriptions           │  external ID
 • Review ratings                       │
                                        │
Breezeway ──────────────────────────────┘
 • Task history (all types)
 • Cleaning & inspection records
 • Maintenance costs & labor
 • Smart lock & access codes (real-time)
 • Staff & assignment data
 • Reservation–task links
 • Webhooks for live updates
```

**Join key:** Breezeway's `reference_property_id` = Hostaway's `id`. Every Breezeway property can be created/retrieved using Hostaway's listing ID as the external reference, making the join lossless.

---

### Credential Status

| System | Status |
|---|---|
| Hostaway | **Connected** — credentials confirmed, 100 listings pulled |
| Breezeway | **Not yet connected** — requires submitting credential request form at developer.breezeway.io |

**Next step:** Request Breezeway API credentials. The form is at [developer.breezeway.io/docs/obtaining-credentials](https://developer.breezeway.io/docs/obtaining-credentials). Once issued, the same fetch-and-inventory approach used for Hostaway can be applied to Breezeway's `/home` and `/task` endpoints.
