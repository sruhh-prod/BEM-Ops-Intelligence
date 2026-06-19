# BEM Operations Intelligence Center — Database Schema
**Platform:** Supabase (PostgreSQL)  
**Generated:** 2026-06-17  
**Design principle:** Surface operational risk before it reaches a guest.

---

## Architecture Overview

The schema has three layers:

**Layer 1 — Source Data** (synced from external systems)
- `properties` — from Breezeway (enriched with Hostaway identity)
- `reservations` — from Hostaway
- `tasks` — from Breezeway
- `task_comments` — from Breezeway
- `task_requirements` — from Breezeway (checklist responses)
- `people` — from Breezeway (staff/assignees)

**Layer 2 — Intelligence** (computed by the platform)
- `operational_risks` — derived risk signals per reservation
- `recurring_issues` — detected patterns across tasks
- `thursday_call_items` — curated leadership intelligence

**Layer 3 — AI Assistance**
- `pascal_insights` — AI-generated summaries, recommendations, alerts
- `pascal_conversations` — conversation history per property or context

**Supporting**
- `sync_log` — pipeline health and audit trail
- `property_amenities` — normalized amenity records

---

## Table Definitions

---

### `properties`
Source: Breezeway (primary) + Hostaway (identity enrichment)  
Purpose: Single property record that answers every operational question about a unit.

```sql
CREATE TABLE properties (
  -- Identity
  id                        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_id              INTEGER       UNIQUE NOT NULL,
  hostaway_id               INTEGER       UNIQUE,           -- join key to Hostaway
  external_id               TEXT,                           -- Breezeway's reference_property_id field

  -- Naming
  internal_name             TEXT          NOT NULL,         -- "5605 Tchoupitoulas 1/1 (Uptown)"
  public_name               TEXT          NOT NULL,         -- guest-facing channel name
  airbnb_name               TEXT,
  thumbnail_url             TEXT,

  -- Location
  street                    TEXT,
  city                      TEXT,
  state                     TEXT,
  zipcode                   TEXT,
  country_code              TEXT          DEFAULT 'US',
  lat                       NUMERIC(11,8),
  lng                       NUMERIC(11,8),
  timezone                  TEXT          DEFAULT 'America/Chicago',

  -- Configuration
  property_type             TEXT,                           -- Apartment, House, Condo, Townhouse, etc.
  bedrooms                  SMALLINT,
  beds                      SMALLINT,
  bathrooms                 NUMERIC(3,1),
  max_guests                SMALLINT,
  is_long_term              BOOLEAN       DEFAULT FALSE,    -- minNights >= 30

  -- Access & Entry (operational core)
  access_instructions       TEXT,                           -- airbnbAccess — primary entry prose
  door_code                 TEXT,                           -- structured if available, else extracted
  door_code_source          TEXT,                           -- 'structured' | 'extracted' | 'manual'
  additional_checkin        TEXT,                           -- custom field "Additional Check-In Instructions"
  checkin_time_start        SMALLINT,                       -- hour (15 = 3 PM)
  checkin_time_end          SMALLINT,                       -- hour (26 = anytime)
  checkout_time             SMALLINT,                       -- hour (11 = 11 AM)
  special_checkout_notes    TEXT,                           -- custom field "Special Check-Out Instructions"

  -- WiFi
  wifi_network              TEXT,                           -- structured or extracted
  wifi_password             TEXT,                           -- structured or extracted
  wifi_password_source      TEXT,                           -- 'structured' | 'extracted' | 'manual'
  wifi_speed_tier           TEXT,                           -- '25mbps' | '50mbps' | '100mbps'

  -- Parking
  parking_type              TEXT,                           -- 'street' | 'free' | 'paid' | 'garage' | 'none'
  parking_details           TEXT,                           -- custom field "Parking Details"
  has_disabled_parking      BOOLEAN       DEFAULT FALSE,

  -- Policies
  house_rules               TEXT,
  unit_specific_notes       TEXT,                           -- custom field "Unit Specific Notes"
  cancellation_policy       TEXT,                           -- 'moderate' | 'firm' | 'strict'
  min_nights                SMALLINT,
  max_nights                SMALLINT,
  pets_allowed              BOOLEAN       DEFAULT FALSE,
  pet_fee                   INTEGER,                        -- in cents
  instant_bookable          BOOLEAN       DEFAULT FALSE,

  -- Key amenity flags (denormalized for fast querying)
  has_pool                  BOOLEAN       DEFAULT FALSE,
  has_hot_tub               BOOLEAN       DEFAULT FALSE,
  has_ev_charger            BOOLEAN       DEFAULT FALSE,
  has_washer_dryer          BOOLEAN       DEFAULT FALSE,
  has_dishwasher            BOOLEAN       DEFAULT FALSE,
  has_private_entrance      BOOLEAN       DEFAULT FALSE,
  has_contactless_checkin   BOOLEAN       DEFAULT FALSE,

  -- Internal classification (from listingTags)
  license_category          TEXT,                           -- 'STR' | 'Hotel License' | 'Commercial'
  rental_category           TEXT,                           -- 'STR' | 'MTR' | 'Full'
  owner_commission_pct      SMALLINT,                       -- 20 | 22 | 23 | 25
  internal_tags             TEXT[],                         -- raw tag array preserved

  -- STR Compliance
  str_license_number        TEXT,
  str_license_type          TEXT,
  str_license_issued        DATE,
  str_license_expires       DATE,
  str_license_expired       BOOLEAN       GENERATED ALWAYS AS (str_license_expires < CURRENT_DATE) STORED,

  -- Channels
  airbnb_url                TEXT,
  vrbo_url                  TEXT,
  airbnb_active             BOOLEAN       DEFAULT FALSE,
  vrbo_active               BOOLEAN       DEFAULT FALSE,

  -- Financials
  base_price_cents          INTEGER,                        -- base nightly rate in cents
  cleaning_fee_cents        INTEGER,

  -- Performance
  review_rating             NUMERIC(3,1),                   -- out of 10

  -- Contact
  contact_name              TEXT,
  contact_email             TEXT,
  contact_phone             TEXT,

  -- Current operational status
  cleanliness_status        TEXT,                           -- 'clean' | 'dirty' | 'in_progress' | 'unknown'
  cleanliness_updated_at    TIMESTAMPTZ,

  -- Data quality flags
  dq_has_structured_wifi     BOOLEAN      DEFAULT FALSE,
  dq_has_structured_door_code BOOLEAN     DEFAULT FALSE,
  dq_has_parking_details     BOOLEAN      DEFAULT FALSE,
  dq_has_additional_checkin  BOOLEAN      DEFAULT FALSE,
  dq_has_unit_notes          BOOLEAN      DEFAULT FALSE,
  dq_completeness_score      SMALLINT,                      -- 0–100 computed at sync

  -- Sync metadata
  breezeway_synced_at       TIMESTAMPTZ,
  hostaway_synced_at        TIMESTAMPTZ,
  created_at                TIMESTAMPTZ   DEFAULT NOW(),
  updated_at                TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_properties_breezeway_id    ON properties (breezeway_id);
CREATE INDEX idx_properties_hostaway_id     ON properties (hostaway_id);
CREATE INDEX idx_properties_city_zipcode    ON properties (city, zipcode);
CREATE INDEX idx_properties_rental_category ON properties (rental_category);
CREATE INDEX idx_properties_license_expires ON properties (str_license_expires) WHERE str_license_expires IS NOT NULL;
CREATE INDEX idx_properties_pets_allowed    ON properties (pets_allowed) WHERE pets_allowed = TRUE;
```

---

### `property_amenities`
Source: Breezeway / Hostaway `listingAmenities`  
Purpose: Normalized amenity records for flexible querying. Denormalized flags on `properties` cover the most common ops checks; this table handles everything else.

```sql
CREATE TABLE property_amenities (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id       UUID          NOT NULL REFERENCES properties (id) ON DELETE CASCADE,
  amenity_id        INTEGER,                    -- source system amenity ID
  amenity_name      TEXT          NOT NULL,
  category          TEXT,                       -- 'safety' | 'kitchen' | 'parking' | 'wifi' | 'laundry' | 'outdoor' | 'accessibility' | 'other'
  source            TEXT          DEFAULT 'hostaway',
  created_at        TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_amenities_property_id  ON property_amenities (property_id);
CREATE INDEX idx_amenities_name         ON property_amenities (amenity_name);
CREATE INDEX idx_amenities_category     ON property_amenities (property_id, category);
```

---

### `people`
Source: Breezeway People API  
Purpose: Staff members who are assigned to tasks — housekeepers, inspectors, maintenance, ops managers.

```sql
CREATE TABLE people (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_id      INTEGER       UNIQUE NOT NULL,
  full_name         TEXT          NOT NULL,
  email             TEXT,
  phone             TEXT,
  role              TEXT,                       -- 'housekeeper' | 'inspector' | 'maintenance' | 'manager'
  subdepartment_id  INTEGER,
  subdepartment_name TEXT,
  is_active         BOOLEAN       DEFAULT TRUE,
  breezeway_synced_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ   DEFAULT NOW(),
  updated_at        TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_people_breezeway_id ON people (breezeway_id);
CREATE INDEX idx_people_role         ON people (role);
```

---

### `reservations`
Source: Hostaway  
Purpose: Guest stays. The primary trigger for operational risk — every at-risk arrival starts here.

```sql
CREATE TABLE reservations (
  id                        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  hostaway_reservation_id   TEXT          UNIQUE NOT NULL,
  breezeway_reservation_id  INTEGER,              -- Breezeway's copy of this reservation
  property_id               UUID          NOT NULL REFERENCES properties (id) ON DELETE RESTRICT,

  -- Guest
  guest_name                TEXT,
  guest_email               TEXT,
  guest_phone               TEXT,
  guest_count               SMALLINT,

  -- Dates
  checkin_date              DATE          NOT NULL,
  checkout_date             DATE          NOT NULL,
  checkin_datetime          TIMESTAMPTZ,          -- full datetime if available
  checkout_datetime         TIMESTAMPTZ,
  nights                    SMALLINT      GENERATED ALWAYS AS (checkout_date - checkin_date) STORED,

  -- Status
  status                    TEXT          NOT NULL, -- 'confirmed' | 'checked_in' | 'checked_out' | 'cancelled' | 'no_show'
  channel                   TEXT,                   -- 'airbnb' | 'vrbo' | 'booking.com' | 'direct'
  external_reservation_id   TEXT,                   -- channel-side booking ID (Airbnb confirmation #, etc.)

  -- Financials
  total_price_cents         INTEGER,
  cleaning_fee_cents        INTEGER,

  -- Notes
  reservation_notes         TEXT,                   -- synced from Hostaway / PMS guest notes
  special_requests          TEXT,

  -- Access (populated from Breezeway lock manager or PMS)
  guest_access_code         TEXT,
  access_code_expires_at    TIMESTAMPTZ,

  -- Risk snapshot (computed at sync, refreshed on task changes)
  risk_level                TEXT          DEFAULT 'none', -- 'none' | 'low' | 'medium' | 'high' | 'critical'
  risk_computed_at          TIMESTAMPTZ,
  days_until_checkin        SMALLINT,               -- recomputed daily

  -- Sync metadata
  hostaway_synced_at        TIMESTAMPTZ,
  breezeway_synced_at       TIMESTAMPTZ,
  created_at                TIMESTAMPTZ   DEFAULT NOW(),
  updated_at                TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_reservations_property_id     ON reservations (property_id);
CREATE INDEX idx_reservations_checkin_date    ON reservations (checkin_date);
CREATE INDEX idx_reservations_checkout_date   ON reservations (checkout_date);
CREATE INDEX idx_reservations_status          ON reservations (status);
CREATE INDEX idx_reservations_risk_level      ON reservations (risk_level);
-- Partial index: only upcoming confirmed reservations (the ones ops cares about)
CREATE INDEX idx_reservations_upcoming        ON reservations (checkin_date, risk_level)
  WHERE status = 'confirmed' AND checkin_date >= CURRENT_DATE;
CREATE INDEX idx_reservations_channel         ON reservations (channel);
```

---

### `tasks`
Source: Breezeway Tasks API  
Purpose: The operational heartbeat. Every cleaning, inspection, maintenance job, and guest-impacting issue flows through here.

```sql
CREATE TABLE tasks (
  id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_task_id       INTEGER       UNIQUE NOT NULL,
  breezeway_task_series_id INTEGER,               -- recurring task series
  parent_task_id          UUID          REFERENCES tasks (id),
  property_id             UUID          NOT NULL REFERENCES properties (id) ON DELETE RESTRICT,
  reservation_id          UUID          REFERENCES reservations (id),   -- if linked to a stay

  -- Classification
  department              TEXT          NOT NULL, -- 'housekeeping' | 'maintenance' | 'inspection' | 'safety'
  task_name               TEXT          NOT NULL,
  description             TEXT,
  summary_note            TEXT,                   -- TaskNote.note from Breezeway
  priority                TEXT,                   -- 'urgent' | 'high' | 'normal' | 'low' | 'watch'
  requested_by            TEXT,                   -- who/what triggered it (13 Breezeway options)
  template_id             INTEGER,
  template_name           TEXT,
  subdepartment_id        INTEGER,
  tags                    TEXT[],

  -- Status & Lifecycle
  status                  TEXT          NOT NULL, -- 'pending' | 'assigned' | 'started' | 'paused' | 'completed' | 'approved' | 'closed'
  scheduled_date          DATE,
  scheduled_time          TIME,
  end_date                DATE,
  due_date                DATE,                   -- computed deadline (often = checkin_date)
  due_time                TIME,
  started_at              TIMESTAMPTZ,
  finished_at             TIMESTAMPTZ,
  assigned_at             TIMESTAMPTZ,
  created_at              TIMESTAMPTZ   DEFAULT NOW(),
  updated_at              TIMESTAMPTZ   DEFAULT NOW(),
  deleted_at              TIMESTAMPTZ,

  -- Assignment
  created_by_person_id    UUID          REFERENCES people (id),
  started_by_person_id    UUID          REFERENCES people (id),
  finished_by_person_id   UUID          REFERENCES people (id),

  -- Time & Cost
  estimated_hours         NUMERIC(5,2),
  actual_hours            NUMERIC(5,2),
  estimated_rate_cents    INTEGER,
  rate_paid_cents         INTEGER,
  rate_type               TEXT,                   -- 'piece' | 'hourly'
  total_cost_cents        INTEGER,
  bill_to                 TEXT,
  is_billable             BOOLEAN       DEFAULT FALSE,

  -- Evidence
  photos                  TEXT[],                 -- array of photo URLs

  -- Staleness intelligence (computed)
  is_overdue              BOOLEAN       GENERATED ALWAYS AS (
                            due_date < CURRENT_DATE
                            AND status NOT IN ('completed', 'approved', 'closed')
                          ) STORED,
  hours_since_update      NUMERIC(6,1), -- refreshed by sync job
  is_stale                BOOLEAN       DEFAULT FALSE, -- set by risk engine (no activity > threshold)
  stale_since             TIMESTAMPTZ,
  blocks_arrival          BOOLEAN       DEFAULT FALSE, -- set by risk engine

  -- Sync metadata
  breezeway_synced_at     TIMESTAMPTZ,
  task_report_url         TEXT
);
```

**Indexes:**
```sql
CREATE INDEX idx_tasks_property_id        ON tasks (property_id);
CREATE INDEX idx_tasks_reservation_id     ON tasks (reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_tasks_department         ON tasks (department);
CREATE INDEX idx_tasks_status             ON tasks (status);
CREATE INDEX idx_tasks_priority           ON tasks (priority);
CREATE INDEX idx_tasks_scheduled_date     ON tasks (scheduled_date);
CREATE INDEX idx_tasks_due_date           ON tasks (due_date);
CREATE INDEX idx_tasks_is_overdue         ON tasks (is_overdue) WHERE is_overdue = TRUE;
CREATE INDEX idx_tasks_is_stale           ON tasks (is_stale) WHERE is_stale = TRUE;
CREATE INDEX idx_tasks_blocks_arrival     ON tasks (blocks_arrival) WHERE blocks_arrival = TRUE;
-- Compound: open tasks by property (most common ops query)
CREATE INDEX idx_tasks_property_open      ON tasks (property_id, scheduled_date)
  WHERE status NOT IN ('completed', 'approved', 'closed') AND deleted_at IS NULL;
-- Compound: risk engine query — upcoming open tasks needing attention
CREATE INDEX idx_tasks_risk_engine        ON tasks (scheduled_date, priority, status)
  WHERE status NOT IN ('completed', 'approved', 'closed') AND deleted_at IS NULL;
```

---

### `task_assignments`
Source: Breezeway Tasks API (assignments array)  
Purpose: Many-to-many between tasks and people. A task can have multiple assignees.

```sql
CREATE TABLE task_assignments (
  id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id       UUID          NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
  person_id     UUID          NOT NULL REFERENCES people (id),
  assigned_at   TIMESTAMPTZ,
  accepted_at   TIMESTAMPTZ,
  declined_at   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ   DEFAULT NOW(),
  UNIQUE (task_id, person_id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_task_assignments_task_id   ON task_assignments (task_id);
CREATE INDEX idx_task_assignments_person_id ON task_assignments (person_id);
```

---

### `task_comments`
Source: Breezeway Task Comments API  
Purpose: Communication thread on a task. Critical for understanding why something is delayed.

```sql
CREATE TABLE task_comments (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_comment_id INTEGER      UNIQUE NOT NULL,
  task_id             UUID          NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
  person_id           UUID          REFERENCES people (id),
  comment_text        TEXT          NOT NULL,
  photos              TEXT[],                   -- photos attached to this comment
  is_system_generated BOOLEAN       DEFAULT FALSE,
  breezeway_created_at TIMESTAMPTZ  NOT NULL,
  created_at          TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_task_comments_task_id ON task_comments (task_id);
CREATE INDEX idx_task_comments_created ON task_comments (task_id, breezeway_created_at);
```

---

### `task_requirements`
Source: Breezeway `GET /task/{id}/requirements`  
Purpose: Checklist responses — what was verified, what was photographed, what was skipped.

```sql
CREATE TABLE task_requirements (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id               UUID          NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
  requirement_text      TEXT          NOT NULL,
  is_completed          BOOLEAN       DEFAULT FALSE,
  completed_at          TIMESTAMPTZ,
  completed_by_person_id UUID         REFERENCES people (id),
  response_text         TEXT,
  photos                TEXT[],
  sort_order            SMALLINT,
  breezeway_synced_at   TIMESTAMPTZ,
  created_at            TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_requirements_task_id ON task_requirements (task_id);
```

---

### `operational_risks`
Source: Computed by the BEM risk engine  
Purpose: The intelligence layer. One risk record per signal — a reservation can have multiple risks. This drives the "At-Risk Arrivals" and "Stale Tasks" dashboards. Risk records are recomputed on every sync cycle and on webhook events.

```sql
CREATE TABLE operational_risks (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id         UUID          NOT NULL REFERENCES properties (id) ON DELETE CASCADE,
  reservation_id      UUID          REFERENCES reservations (id) ON DELETE CASCADE,
  task_id             UUID          REFERENCES tasks (id) ON DELETE SET NULL,

  -- Risk classification
  risk_type           TEXT          NOT NULL,
  -- Values:
  --   'open_clean_before_arrival'     — no completed housekeeping task before checkin
  --   'open_maintenance_before_arrival' — maintenance task open within 48h of checkin
  --   'no_inspection_before_arrival'  — no inspection task completed before checkin
  --   'stale_task'                    — task not updated in threshold period
  --   'missing_access_instructions'  — no access_instructions or door_code
  --   'missing_wifi_credentials'      — no wifi_network/wifi_password
  --   'missing_parking_details'       — no parking_details for property
  --   'expired_str_license'           — str_license_expires < today
  --   'expiring_str_license'          — str_license_expires within 90 days
  --   'overdue_task'                  — task.due_date passed, not complete
  --   'unassigned_task'               — task exists but no assignee
  --   'same_day_turnover'             — checkout and checkin on same day, no clean scheduled
  --   'guest_count_exceeds_capacity'  — reservation guest count > property max_guests
  --   'access_code_not_set'           — guest access code missing for arriving reservation

  severity            TEXT          NOT NULL,   -- 'low' | 'medium' | 'high' | 'critical'
  title               TEXT          NOT NULL,   -- human-readable: "No clean scheduled — arrives in 6h"
  detail              TEXT,                     -- longer explanation
  recommendation      TEXT,                     -- actionable: "Assign housekeeper immediately"

  -- Timing context
  hours_until_checkin NUMERIC(5,1),             -- negative if past
  checkin_date        DATE,                     -- denormalized for fast queries

  -- State
  is_active           BOOLEAN       DEFAULT TRUE,
  resolved_at         TIMESTAMPTZ,
  resolved_by         UUID          REFERENCES people (id),
  resolution_note     TEXT,
  snoozed_until       TIMESTAMPTZ,
  suppressed          BOOLEAN       DEFAULT FALSE,

  -- Attribution
  detected_by         TEXT          DEFAULT 'risk_engine', -- 'risk_engine' | 'pascal' | 'manual'
  computed_at         TIMESTAMPTZ   DEFAULT NOW(),
  created_at          TIMESTAMPTZ   DEFAULT NOW(),
  updated_at          TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_risks_property_id         ON operational_risks (property_id);
CREATE INDEX idx_risks_reservation_id      ON operational_risks (reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_risks_task_id             ON operational_risks (task_id) WHERE task_id IS NOT NULL;
CREATE INDEX idx_risks_active              ON operational_risks (is_active, severity);
CREATE INDEX idx_risks_checkin_date        ON operational_risks (checkin_date, severity) WHERE is_active = TRUE;
CREATE INDEX idx_risks_type                ON operational_risks (risk_type);
-- Primary dashboard query: active risks ordered by urgency
CREATE INDEX idx_risks_dashboard           ON operational_risks (severity, hours_until_checkin)
  WHERE is_active = TRUE AND suppressed = FALSE;
```

---

### `recurring_issues`
Source: Computed by the BEM pattern engine  
Purpose: Identify properties or people generating the same category of failure repeatedly. This drives the "Recurring Issues" section of the Thursday call.

```sql
CREATE TABLE recurring_issues (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id         UUID          REFERENCES properties (id) ON DELETE CASCADE,
  person_id           UUID          REFERENCES people (id) ON DELETE SET NULL, -- if issue is staff-correlated

  -- Pattern definition
  issue_category      TEXT          NOT NULL,
  -- Values:
  --   'repeated_maintenance'          — same maintenance type at same property 3+ times
  --   'repeated_guest_complaint'      — complaint pattern from task notes/comments
  --   'repeated_late_clean'           — housekeeping task started after scheduled time
  --   'repeated_missed_inspection'    — inspection not completed before arrival
  --   'repeated_access_failure'       — guest cannot access — recurs at same property
  --   'repeated_wifi_complaint'       — WiFi-related task/comment pattern
  --   'repeated_parking_complaint'    — parking-related task/comment pattern
  --   'repeated_hvac_issue'           — HVAC maintenance 2+ times in rolling 60 days
  --   'repeated_plumbing_issue'       — plumbing maintenance 2+ times
  --   'repeated_pest_issue'           — pest-related tasks

  title               TEXT          NOT NULL,   -- "HVAC failures at 3 Tchoupitoulas — 3 times in 45 days"
  description         TEXT,
  evidence_task_ids   UUID[],                   -- task IDs that established this pattern
  occurrence_count    SMALLINT      NOT NULL,
  first_seen_at       TIMESTAMPTZ,
  last_seen_at        TIMESTAMPTZ,
  window_days         SMALLINT      DEFAULT 60,  -- lookback window used for detection

  -- Classification
  severity            TEXT          NOT NULL,   -- 'low' | 'medium' | 'high'
  is_active           BOOLEAN       DEFAULT TRUE,
  resolved_at         TIMESTAMPTZ,
  resolution_note     TEXT,
  flagged_for_thursday_call BOOLEAN DEFAULT FALSE,

  created_at          TIMESTAMPTZ   DEFAULT NOW(),
  updated_at          TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_recurring_property_id    ON recurring_issues (property_id);
CREATE INDEX idx_recurring_active         ON recurring_issues (is_active, severity);
CREATE INDEX idx_recurring_thursday       ON recurring_issues (flagged_for_thursday_call) WHERE flagged_for_thursday_call = TRUE;
CREATE INDEX idx_recurring_category       ON recurring_issues (issue_category);
```

---

### `thursday_call_items`
Source: Auto-generated by risk/pattern engines + manually curated  
Purpose: The weekly leadership briefing. Items are generated automatically but can be edited, reordered, resolved, or carried forward. This is the ops leadership's working document.

```sql
CREATE TABLE thursday_call_items (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  call_date           DATE          NOT NULL,   -- the Thursday this item belongs to

  -- Context links (all optional — item may relate to multiple or none)
  property_id         UUID          REFERENCES properties (id) ON DELETE SET NULL,
  reservation_id      UUID          REFERENCES reservations (id) ON DELETE SET NULL,
  task_id             UUID          REFERENCES tasks (id) ON DELETE SET NULL,
  operational_risk_id UUID          REFERENCES operational_risks (id) ON DELETE SET NULL,
  recurring_issue_id  UUID          REFERENCES recurring_issues (id) ON DELETE SET NULL,

  -- Content
  category            TEXT          NOT NULL,
  -- Values:
  --   'at_risk_arrival'
  --   'recurring_issue'
  --   'stale_task'
  --   'staff_performance'
  --   'data_quality_gap'
  --   'compliance_alert'
  --   'quick_win'
  --   'owner_escalation'
  --   'process_improvement'
  --   'general'

  title               TEXT          NOT NULL,
  summary             TEXT,                     -- auto-generated or manually written
  recommendation      TEXT,
  priority            SMALLINT      DEFAULT 5,  -- 1 (highest) to 10 for ordering on call

  -- Source
  source              TEXT          DEFAULT 'auto', -- 'auto' | 'pascal' | 'manual'
  generated_by        TEXT,                     -- 'risk_engine' | 'pattern_engine' | 'pascal' | user name

  -- Status
  status              TEXT          DEFAULT 'open', -- 'open' | 'discussed' | 'actioned' | 'deferred' | 'closed'
  outcome_notes       TEXT,                     -- what was decided/actioned on the call
  owner               TEXT,                     -- who took ownership of this item
  due_date            DATE,                     -- action due date if assigned
  carried_forward     BOOLEAN       DEFAULT FALSE,
  carried_from_date   DATE,

  created_at          TIMESTAMPTZ   DEFAULT NOW(),
  updated_at          TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_thursday_call_date       ON thursday_call_items (call_date);
CREATE INDEX idx_thursday_property        ON thursday_call_items (property_id) WHERE property_id IS NOT NULL;
CREATE INDEX idx_thursday_status          ON thursday_call_items (call_date, status);
CREATE INDEX idx_thursday_category        ON thursday_call_items (category);
-- Upcoming open items
CREATE INDEX idx_thursday_open            ON thursday_call_items (call_date, priority)
  WHERE status = 'open';
```

---

### `pascal_insights`
Source: Pascal AI Copilot (Claude API)  
Purpose: Store AI-generated summaries, risk explanations, recommended actions, and property briefings. Every AI output is persisted for auditability and to avoid redundant generation.

```sql
CREATE TABLE pascal_insights (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Context (what Pascal was analyzing)
  insight_type        TEXT          NOT NULL,
  -- Values:
  --   'property_briefing'         — full property operational summary
  --   'arrival_risk_summary'      — narrative on why a reservation is at risk
  --   'recurring_issue_analysis'  — pattern explanation and root cause hypothesis
  --   'stale_task_triage'         — why a task is stale and what to do
  --   'thursday_call_brief'       — full call agenda narrative
  --   'quick_win_suggestion'      — identified quick-to-close opportunities
  --   'data_quality_alert'        — missing data that blocks operations
  --   'guest_comms_draft'         — suggested guest message (not sent — for review)

  -- Links to subject matter
  property_id         UUID          REFERENCES properties (id) ON DELETE SET NULL,
  reservation_id      UUID          REFERENCES reservations (id) ON DELETE SET NULL,
  task_id             UUID          REFERENCES tasks (id) ON DELETE SET NULL,
  operational_risk_id UUID          REFERENCES operational_risks (id) ON DELETE SET NULL,
  recurring_issue_id  UUID          REFERENCES recurring_issues (id) ON DELETE SET NULL,
  thursday_call_date  DATE,

  -- Content
  prompt_summary      TEXT,                     -- abbreviated version of prompt used (not full prompt)
  insight_text        TEXT          NOT NULL,   -- the AI output
  confidence_level    TEXT,                     -- 'high' | 'medium' | 'low' — self-reported by model
  recommended_actions TEXT[],                   -- extracted action items from the insight

  -- Model metadata
  model_id            TEXT,                     -- e.g. 'claude-sonnet-4-6'
  input_tokens        INTEGER,
  output_tokens       INTEGER,
  generation_time_ms  INTEGER,

  -- State
  is_reviewed         BOOLEAN       DEFAULT FALSE,
  reviewed_by         TEXT,
  reviewed_at         TIMESTAMPTZ,
  was_actioned        BOOLEAN,
  feedback            TEXT,                     -- thumbs up/down + optional note

  created_at          TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_pascal_property_id       ON pascal_insights (property_id) WHERE property_id IS NOT NULL;
CREATE INDEX idx_pascal_reservation_id    ON pascal_insights (reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_pascal_insight_type      ON pascal_insights (insight_type);
CREATE INDEX idx_pascal_thursday          ON pascal_insights (thursday_call_date) WHERE thursday_call_date IS NOT NULL;
CREATE INDEX idx_pascal_created_at        ON pascal_insights (created_at DESC);
```

---

### `pascal_conversations`
Source: Pascal AI Copilot  
Purpose: Conversation history for interactive Pascal sessions. Enables context continuity across turns, property-specific or portfolio-wide queries.

```sql
CREATE TABLE pascal_conversations (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID          NOT NULL,   -- groups messages in one session
  property_id         UUID          REFERENCES properties (id) ON DELETE SET NULL,
  reservation_id      UUID          REFERENCES reservations (id) ON DELETE SET NULL,
  context_type        TEXT,                     -- 'property' | 'reservation' | 'portfolio' | 'thursday_call'
  role                TEXT          NOT NULL,   -- 'user' | 'assistant' | 'system'
  content             TEXT          NOT NULL,
  turn_number         SMALLINT      NOT NULL,
  model_id            TEXT,
  input_tokens        INTEGER,
  output_tokens       INTEGER,
  created_at          TIMESTAMPTZ   DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_conversations_session    ON pascal_conversations (session_id, turn_number);
CREATE INDEX idx_conversations_property   ON pascal_conversations (property_id) WHERE property_id IS NOT NULL;
CREATE INDEX idx_conversations_created    ON pascal_conversations (created_at DESC);
```

---

### `sync_log`
Source: BEM sync pipeline  
Purpose: Health monitoring for every data pull from Breezeway and Hostaway. If syncs fail silently, the risk engine works on stale data. This table is the canary.

```sql
CREATE TABLE sync_log (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  source              TEXT          NOT NULL,   -- 'breezeway' | 'hostaway'
  entity_type         TEXT          NOT NULL,   -- 'properties' | 'tasks' | 'reservations' | 'task_comments' | 'people'
  sync_type           TEXT          NOT NULL,   -- 'full' | 'incremental' | 'webhook'
  status              TEXT          NOT NULL,   -- 'success' | 'partial' | 'failed'
  records_fetched     INTEGER       DEFAULT 0,
  records_created     INTEGER       DEFAULT 0,
  records_updated     INTEGER       DEFAULT 0,
  records_failed      INTEGER       DEFAULT 0,
  error_message       TEXT,
  api_calls_made      SMALLINT,
  duration_ms         INTEGER,
  started_at          TIMESTAMPTZ   NOT NULL,
  completed_at        TIMESTAMPTZ
);
```

**Indexes:**
```sql
CREATE INDEX idx_sync_log_source   ON sync_log (source, entity_type, started_at DESC);
CREATE INDEX idx_sync_log_status   ON sync_log (status, started_at DESC);
CREATE INDEX idx_sync_log_started  ON sync_log (started_at DESC);
```

---

## Entity Relationship Summary

```
properties (1) ──────────────────────── (many) reservations
properties (1) ──────────────────────── (many) tasks
properties (1) ──────────────────────── (many) property_amenities
properties (1) ──────────────────────── (many) operational_risks
properties (1) ──────────────────────── (many) recurring_issues

reservations (1) ────────────────────── (many) tasks
reservations (1) ────────────────────── (many) operational_risks

tasks (1) ───────────────────────────── (many) task_comments
tasks (1) ───────────────────────────── (many) task_requirements
tasks (1) ───────────────────────────── (many) task_assignments
tasks (many) ────────────────────────── (many) people   [via task_assignments]
tasks (1) ───────────────────────────── (1)    tasks [self-ref: parent_task_id]

people (1) ──────────────────────────── (many) task_assignments
people (1) ──────────────────────────── (many) task_comments

operational_risks (1) ───────────────── (many) thursday_call_items
recurring_issues (1) ────────────────── (many) thursday_call_items

pascal_insights  ──── links to: properties, reservations, tasks, operational_risks, recurring_issues
pascal_conversations ─ links to: properties, reservations
```

---

## MVP vs. Later Phase Fields

### MVP — Build First

These tables and fields are required for the first dashboard to function:

| Table | Required for |
|---|---|
| `properties` | Every view — base of everything |
| `reservations` | At-Risk Arrivals, Thursday Call |
| `tasks` | At-Risk Arrivals, Stale Tasks, Quick Wins |
| `task_assignments` | Stale Tasks (who's responsible), Quick Wins |
| `task_comments` | Stale Tasks (last activity), Recurring Issues |
| `people` | Assignments, accountability |
| `operational_risks` | At-Risk Arrivals, Thursday Call |
| `thursday_call_items` | Thursday Call Intelligence |
| `sync_log` | Pipeline health — non-negotiable from day one |

Fields to include in MVP `properties`:
- All identity, location, and configuration fields
- `access_instructions`, `door_code`, `checkin_time_start/end`, `checkout_time`
- `wifi_network`, `wifi_password`
- `parking_type`, `parking_details`
- `house_rules`, `unit_specific_notes`
- `pets_allowed`, `pet_fee`, `instant_bookable`
- All `dq_*` data quality flags
- `str_license_expires`, `str_license_expired`
- `cleanliness_status`
- All 5 key amenity boolean flags

---

### Phase 2 — Add After MVP is Live

| Table / Field | Why It Waits |
|---|---|
| `recurring_issues` | Requires 30+ days of task history to detect meaningful patterns |
| `pascal_insights` | Requires operational_risks and properties to be stable first |
| `pascal_conversations` | Requires Pascal interface to be built |
| `task_requirements` | Requires Breezeway credential + confirmed checklist usage |
| `property_amenities` (full table) | Denormalized booleans on `properties` cover MVP needs |
| `properties.base_price_cents` | Revenue intelligence — separate concern from ops risk |
| `properties.weekly_discount` / `monthly_discount` | Revenue intelligence |
| `properties.expedia_url` | Low priority channel |
| `properties.dq_completeness_score` | Need 1+ sync cycles to calibrate scoring |
| `reservations.channel` tracking | Nice to have; doesn't change risk logic at MVP |
| `task_assignments.accepted_at/declined_at` | Breezeway webhooks needed; not in first sync |
| `operational_risks.snoozed_until` | UX feature — build the risk first |
| `thursday_call_items.carried_forward` | After the first 2–3 calls |

---

### Phase 3 — Predictive Operations

| Capability | Tables Needed |
|---|---|
| Predict which properties will have a dirty-on-arrival | `tasks` + `reservations` history + ML scoring |
| Forecast maintenance demand by season | `tasks` history + `reservations` calendar |
| Staff workload balancing | `task_assignments` + `people` + `reservations` |
| Owner reporting | New `owner_reports` table |
| Guest sentiment analysis | New `guest_reviews` table (from Hostaway or Airbnb) |

---

## Risk Engine Logic (Reference)

The `operational_risks` table is populated by a rule engine that runs:
1. On every Breezeway webhook event (real-time)
2. On every Hostaway sync (hourly)
3. On a scheduled daily pass at 6 AM local time

Core rules (in order of severity):

```
CRITICAL — acts within 12 hours
  • Reservation arrives in < 12h AND housekeeping task status != completed/approved
  • Reservation arrives in < 6h AND no access_instructions or door_code on property

HIGH — acts within 48 hours
  • Reservation arrives in < 48h AND open maintenance task exists
  • Reservation arrives in < 24h AND no inspection completed
  • Reservation arrives in < 24h AND guest_access_code IS NULL
  • Same-day checkout + checkin with no clean task scheduled

MEDIUM — acts within 7 days
  • Task not updated in > 72 hours (stale)
  • Task overdue (due_date < today) and not complete
  • Task assigned to no one
  • STR license expires within 90 days

LOW — informational
  • WiFi credentials missing from property record
  • Parking details missing from property record
  • STR license expired (>90 days ago already flagged; resurface monthly)
  • Property completeness score < 60
```

---

## Quick Reference — Table Count by Phase

| Phase | Tables | Purpose |
|---|---|---|
| MVP | 9 | Core ops intelligence |
| Phase 2 | +3 | Pattern detection + AI copilot |
| Phase 3 | +3 | Predictive + reporting |
| **Total** | **15** | Full platform |
