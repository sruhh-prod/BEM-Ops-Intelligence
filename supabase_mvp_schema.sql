-- =============================================================================
-- BEM Operations Intelligence Center — MVP Schema
-- Platform: Supabase (PostgreSQL 15+)
-- Generated: 2026-06-17
-- =============================================================================
-- Execution order matters. Run this file top to bottom.
-- Enable pgcrypto for gen_random_uuid() if not already active.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUMS
-- Defined once, referenced by column constraints.
-- =============================================================================

CREATE TYPE risk_severity      AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE risk_status        AS ENUM ('active', 'resolved', 'snoozed', 'suppressed');
CREATE TYPE task_department    AS ENUM ('housekeeping', 'maintenance', 'inspection', 'safety');
CREATE TYPE task_priority      AS ENUM ('urgent', 'high', 'normal', 'low', 'watch');
CREATE TYPE task_status        AS ENUM ('pending', 'assigned', 'started', 'paused', 'completed', 'approved', 'closed');
CREATE TYPE task_rate_type     AS ENUM ('piece', 'hourly');
CREATE TYPE reservation_status AS ENUM ('confirmed', 'checked_in', 'checked_out', 'cancelled', 'no_show');
CREATE TYPE sync_source        AS ENUM ('breezeway', 'hostaway');
CREATE TYPE sync_entity        AS ENUM ('properties', 'tasks', 'task_comments', 'reservations', 'people', 'risks');
CREATE TYPE sync_type          AS ENUM ('full', 'incremental', 'webhook');
CREATE TYPE sync_status        AS ENUM ('success', 'partial', 'failed');
CREATE TYPE pascal_insight_type AS ENUM (
  'property_briefing',
  'arrival_risk_summary',
  'recurring_issue_analysis',
  'stale_task_triage',
  'thursday_call_brief',
  'quick_win_suggestion',
  'data_quality_alert',
  'guest_comms_draft'
);
CREATE TYPE pascal_context_type AS ENUM ('property', 'reservation', 'portfolio', 'thursday_call');
CREATE TYPE pascal_role         AS ENUM ('user', 'assistant', 'system');
CREATE TYPE thursday_category   AS ENUM (
  'at_risk_arrival',
  'recurring_issue',
  'stale_task',
  'staff_performance',
  'data_quality_gap',
  'compliance_alert',
  'quick_win',
  'owner_escalation',
  'process_improvement',
  'general'
);
CREATE TYPE thursday_status AS ENUM ('open', 'discussed', 'actioned', 'deferred', 'closed');
CREATE TYPE door_code_source    AS ENUM ('structured', 'extracted', 'manual');
CREATE TYPE wifi_password_source AS ENUM ('structured', 'extracted', 'manual');
CREATE TYPE parking_type        AS ENUM ('street', 'free', 'paid', 'garage', 'none');
CREATE TYPE cleanliness_status  AS ENUM ('clean', 'dirty', 'in_progress', 'unknown');
CREATE TYPE confidence_level    AS ENUM ('high', 'medium', 'low');
CREATE TYPE detected_by         AS ENUM ('risk_engine', 'pascal', 'manual');

-- =============================================================================
-- TABLE: people
-- Source: Breezeway People API
-- Must exist before tasks (foreign key dependency).
-- =============================================================================

CREATE TABLE people (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_id          INTEGER       NOT NULL UNIQUE,
  full_name             TEXT          NOT NULL,
  email                 TEXT,
  phone                 TEXT,
  role                  TEXT,
  subdepartment_id      INTEGER,
  subdepartment_name    TEXT,
  is_active             BOOLEAN       NOT NULL DEFAULT TRUE,
  breezeway_synced_at   TIMESTAMPTZ,
  created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_people_breezeway_id ON people (breezeway_id);
CREATE INDEX idx_people_role         ON people (role) WHERE is_active = TRUE;

-- =============================================================================
-- TABLE: properties
-- Source: Breezeway (primary) + Hostaway (identity enrichment)
-- Central table. Every other table references this.
-- =============================================================================

CREATE TABLE properties (
  id                          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),

  -- External identifiers
  breezeway_id                INTEGER       NOT NULL UNIQUE,
  hostaway_id                 INTEGER       UNIQUE,
  breezeway_external_id       TEXT,

  -- Naming
  internal_name               TEXT          NOT NULL,
  public_name                 TEXT          NOT NULL,
  airbnb_name                 TEXT,
  thumbnail_url               TEXT,

  -- Location
  street                      TEXT,
  city                        TEXT,
  state                       TEXT,
  zipcode                     TEXT,
  country_code                TEXT          NOT NULL DEFAULT 'US',
  lat                         NUMERIC(11,8),
  lng                         NUMERIC(11,8),
  timezone                    TEXT          NOT NULL DEFAULT 'America/Chicago',

  -- Configuration
  property_type               TEXT,
  bedrooms                    SMALLINT,
  beds                        SMALLINT,
  bathrooms                   NUMERIC(3,1),
  max_guests                  SMALLINT,
  is_long_term                BOOLEAN       NOT NULL DEFAULT FALSE,

  -- Access & entry
  access_instructions         TEXT,
  door_code                   TEXT,
  door_code_source            door_code_source,
  additional_checkin          TEXT,
  checkin_time_start          SMALLINT,
  checkin_time_end            SMALLINT,
  checkout_time               SMALLINT,
  special_checkout_notes      TEXT,

  -- WiFi
  wifi_network                TEXT,
  wifi_password               TEXT,
  wifi_password_source        wifi_password_source,
  wifi_speed_tier             TEXT,

  -- Parking
  parking_type                parking_type,
  parking_details             TEXT,
  has_disabled_parking        BOOLEAN       NOT NULL DEFAULT FALSE,

  -- Policies
  house_rules                 TEXT,
  unit_specific_notes         TEXT,
  cancellation_policy         TEXT,
  min_nights                  SMALLINT,
  max_nights                  SMALLINT,
  pets_allowed                BOOLEAN       NOT NULL DEFAULT FALSE,
  pet_fee_cents               INTEGER,
  instant_bookable            BOOLEAN       NOT NULL DEFAULT FALSE,

  -- Key amenity flags (denormalized for fast querying)
  has_pool                    BOOLEAN       NOT NULL DEFAULT FALSE,
  has_hot_tub                 BOOLEAN       NOT NULL DEFAULT FALSE,
  has_ev_charger              BOOLEAN       NOT NULL DEFAULT FALSE,
  has_washer_dryer            BOOLEAN       NOT NULL DEFAULT FALSE,
  has_dishwasher              BOOLEAN       NOT NULL DEFAULT FALSE,
  has_private_entrance        BOOLEAN       NOT NULL DEFAULT FALSE,
  has_contactless_checkin     BOOLEAN       NOT NULL DEFAULT FALSE,

  -- Internal classification
  license_category            TEXT,
  rental_category             TEXT,
  owner_commission_pct        SMALLINT,
  internal_tags               TEXT[],

  -- STR compliance
  str_license_number          TEXT,
  str_license_type            TEXT,
  str_license_issued          DATE,
  str_license_expires         DATE,
  str_license_expired         BOOLEAN       NOT NULL DEFAULT FALSE,

  -- Channels
  airbnb_url                  TEXT,
  vrbo_url                    TEXT,
  airbnb_active               BOOLEAN       NOT NULL DEFAULT FALSE,
  vrbo_active                 BOOLEAN       NOT NULL DEFAULT FALSE,

  -- Financials
  base_price_cents            INTEGER,
  cleaning_fee_cents          INTEGER,

  -- Performance
  review_rating               NUMERIC(3,1)  CHECK (review_rating BETWEEN 0 AND 10),

  -- Contact
  contact_name                TEXT,
  contact_email               TEXT,
  contact_phone               TEXT,

  -- Operational status
  cleanliness_status          cleanliness_status NOT NULL DEFAULT 'unknown',
  cleanliness_updated_at      TIMESTAMPTZ,

  -- Data quality flags
  dq_has_structured_wifi      BOOLEAN       NOT NULL DEFAULT FALSE,
  dq_has_structured_door_code BOOLEAN       NOT NULL DEFAULT FALSE,
  dq_has_parking_details      BOOLEAN       NOT NULL DEFAULT FALSE,
  dq_has_additional_checkin   BOOLEAN       NOT NULL DEFAULT FALSE,
  dq_has_unit_notes           BOOLEAN       NOT NULL DEFAULT FALSE,
  dq_completeness_score       SMALLINT      CHECK (dq_completeness_score BETWEEN 0 AND 100),

  -- Sync metadata
  breezeway_synced_at         TIMESTAMPTZ,
  hostaway_synced_at          TIMESTAMPTZ,
  created_at                  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_properties_breezeway_id     ON properties (breezeway_id);
CREATE INDEX idx_properties_hostaway_id      ON properties (hostaway_id) WHERE hostaway_id IS NOT NULL;
CREATE INDEX idx_properties_city_zip         ON properties (city, zipcode);
CREATE INDEX idx_properties_rental_category  ON properties (rental_category);
CREATE INDEX idx_properties_license_expires  ON properties (str_license_expires)
  WHERE str_license_expires IS NOT NULL;
CREATE INDEX idx_properties_pets             ON properties (pets_allowed)
  WHERE pets_allowed = TRUE;
CREATE INDEX idx_properties_cleanliness      ON properties (cleanliness_status);

-- =============================================================================
-- TABLE: reservations
-- Source: Hostaway
-- Every at-risk arrival starts here.
-- =============================================================================

CREATE TABLE reservations (
  id                        UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
  hostaway_reservation_id   TEXT              NOT NULL UNIQUE,
  breezeway_reservation_id  INTEGER           UNIQUE,
  property_id               UUID              NOT NULL REFERENCES properties (id) ON DELETE RESTRICT,

  -- Guest
  guest_name                TEXT,
  guest_email               TEXT,
  guest_phone               TEXT,
  guest_count               SMALLINT,

  -- Dates
  checkin_date              DATE              NOT NULL,
  checkout_date             DATE              NOT NULL,
  checkin_datetime          TIMESTAMPTZ,
  checkout_datetime         TIMESTAMPTZ,
  nights                    SMALLINT          GENERATED ALWAYS AS (
                              (checkout_date - checkin_date)::SMALLINT
                            ) STORED,

  -- Status & channel
  status                    reservation_status NOT NULL DEFAULT 'confirmed',
  channel                   TEXT,
  external_reservation_id   TEXT,

  -- Financials
  total_price_cents         INTEGER,
  cleaning_fee_cents        INTEGER,

  -- Notes
  reservation_notes         TEXT,
  special_requests          TEXT,

  -- Access
  guest_access_code         TEXT,
  access_code_expires_at    TIMESTAMPTZ,

  -- Risk snapshot (written by risk engine, refreshed on every sync)
  risk_level                risk_severity,
  risk_computed_at          TIMESTAMPTZ,

  -- Sync metadata
  hostaway_synced_at        TIMESTAMPTZ,
  breezeway_synced_at       TIMESTAMPTZ,
  created_at                TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  updated_at                TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_dates CHECK (checkout_date > checkin_date)
);

CREATE INDEX idx_reservations_property_id  ON reservations (property_id);
CREATE INDEX idx_reservations_checkin      ON reservations (checkin_date);
CREATE INDEX idx_reservations_checkout     ON reservations (checkout_date);
CREATE INDEX idx_reservations_status       ON reservations (status);
CREATE INDEX idx_reservations_risk_level   ON reservations (risk_level) WHERE risk_level IS NOT NULL;
-- Primary ops query: upcoming confirmed stays (no CURRENT_DATE in predicate — not immutable)
CREATE INDEX idx_reservations_upcoming     ON reservations (status, checkin_date, risk_level);

-- =============================================================================
-- TABLE: tasks
-- Source: Breezeway Tasks API
-- The operational heartbeat of the platform.
-- =============================================================================

CREATE TABLE tasks (
  id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_task_id       INTEGER         NOT NULL UNIQUE,
  breezeway_task_series_id INTEGER,
  parent_task_id          UUID            REFERENCES tasks (id) ON DELETE SET NULL,
  property_id             UUID            NOT NULL REFERENCES properties (id) ON DELETE RESTRICT,
  reservation_id          UUID            REFERENCES reservations (id) ON DELETE SET NULL,

  -- Classification
  department              task_department NOT NULL,
  task_name               TEXT            NOT NULL,
  description             TEXT,
  summary_note            TEXT,
  priority                task_priority   NOT NULL DEFAULT 'normal',
  requested_by            TEXT,
  template_id             INTEGER,
  template_name           TEXT,
  subdepartment_id        INTEGER,
  tags                    TEXT[],

  -- Status & lifecycle
  status                  task_status     NOT NULL DEFAULT 'pending',
  scheduled_date          DATE,
  scheduled_time          TIME,
  end_date                DATE,
  due_date                DATE,
  due_time                TIME,
  started_at              TIMESTAMPTZ,
  finished_at             TIMESTAMPTZ,
  assigned_at             TIMESTAMPTZ,
  deleted_at              TIMESTAMPTZ,

  -- Assignment (denormalized from task_assignments for fast queries)
  created_by_person_id    UUID            REFERENCES people (id) ON DELETE SET NULL,
  started_by_person_id    UUID            REFERENCES people (id) ON DELETE SET NULL,
  finished_by_person_id   UUID            REFERENCES people (id) ON DELETE SET NULL,

  -- Time & cost
  estimated_hours         NUMERIC(5,2),
  actual_hours            NUMERIC(5,2),
  estimated_rate_cents    INTEGER,
  rate_paid_cents         INTEGER,
  rate_type               task_rate_type,
  total_cost_cents        INTEGER,
  bill_to                 TEXT,
  is_billable             BOOLEAN         NOT NULL DEFAULT FALSE,

  -- Evidence
  photos                  TEXT[],
  task_report_url         TEXT,

  -- Intelligence flags (computed by risk engine; not from Breezeway)
  is_stale                BOOLEAN         NOT NULL DEFAULT FALSE,
  stale_since             TIMESTAMPTZ,
  blocks_arrival          BOOLEAN         NOT NULL DEFAULT FALSE,

  -- Set by the risk engine: past due and not complete
  is_overdue              BOOLEAN         NOT NULL DEFAULT FALSE,

  -- Sync metadata
  breezeway_synced_at     TIMESTAMPTZ,
  created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_property_id        ON tasks (property_id);
CREATE INDEX idx_tasks_reservation_id     ON tasks (reservation_id)      WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_tasks_department         ON tasks (department);
CREATE INDEX idx_tasks_status             ON tasks (status);
CREATE INDEX idx_tasks_priority           ON tasks (priority);
CREATE INDEX idx_tasks_scheduled_date     ON tasks (scheduled_date);
CREATE INDEX idx_tasks_due_date           ON tasks (due_date);
CREATE INDEX idx_tasks_is_overdue         ON tasks (is_overdue)           WHERE is_overdue = TRUE;
CREATE INDEX idx_tasks_is_stale           ON tasks (is_stale)             WHERE is_stale = TRUE;
CREATE INDEX idx_tasks_blocks_arrival     ON tasks (blocks_arrival)       WHERE blocks_arrival = TRUE;
-- Open tasks by property — the most common ops query
CREATE INDEX idx_tasks_property_open      ON tasks (property_id, scheduled_date)
  WHERE status NOT IN ('completed', 'approved', 'closed') AND deleted_at IS NULL;
-- Risk engine query: upcoming open tasks needing triage
CREATE INDEX idx_tasks_risk_triage        ON tasks (scheduled_date, priority, status)
  WHERE status NOT IN ('completed', 'approved', 'closed') AND deleted_at IS NULL;

-- =============================================================================
-- TABLE: task_assignments
-- Source: Breezeway Tasks API (assignments array)
-- Many-to-many between tasks and people.
-- =============================================================================

CREATE TABLE task_assignments (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id      UUID        NOT NULL REFERENCES tasks (id)  ON DELETE CASCADE,
  person_id    UUID        NOT NULL REFERENCES people (id) ON DELETE CASCADE,
  assigned_at  TIMESTAMPTZ,
  accepted_at  TIMESTAMPTZ,
  declined_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (task_id, person_id)
);

CREATE INDEX idx_task_assignments_task_id   ON task_assignments (task_id);
CREATE INDEX idx_task_assignments_person_id ON task_assignments (person_id);

-- =============================================================================
-- TABLE: task_comments
-- Source: Breezeway Task Comments API
-- Communication thread on a task. Key signal for staleness and delay context.
-- =============================================================================

CREATE TABLE task_comments (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  breezeway_comment_id  INTEGER     NOT NULL UNIQUE,
  task_id               UUID        NOT NULL REFERENCES tasks (id)   ON DELETE CASCADE,
  person_id             UUID        REFERENCES people (id)           ON DELETE SET NULL,
  comment_text          TEXT        NOT NULL,
  photos                TEXT[],
  is_system_generated   BOOLEAN     NOT NULL DEFAULT FALSE,
  breezeway_created_at  TIMESTAMPTZ NOT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_comments_task_id ON task_comments (task_id);
CREATE INDEX idx_task_comments_created ON task_comments (task_id, breezeway_created_at DESC);

-- =============================================================================
-- TABLE: operational_risks
-- Source: BEM risk engine (computed — not synced from any external API)
-- One risk record per signal. A reservation can have multiple active risks.
-- Recomputed on every Breezeway webhook and every Hostaway sync cycle.
-- =============================================================================

CREATE TABLE operational_risks (
  id                    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id           UUID            NOT NULL REFERENCES properties   (id) ON DELETE CASCADE,
  reservation_id        UUID            REFERENCES reservations (id)         ON DELETE CASCADE,
  task_id               UUID            REFERENCES tasks        (id)         ON DELETE SET NULL,

  -- Risk classification
  risk_type             TEXT            NOT NULL,
  -- Enumerated values (stored as TEXT for extensibility without enum migrations):
  --   'open_clean_before_arrival'        no completed housekeeping before checkin
  --   'open_maintenance_before_arrival'  open maintenance task within 48h of checkin
  --   'no_inspection_before_arrival'     no inspection completed before checkin
  --   'stale_task'                       task not updated past threshold
  --   'missing_access_instructions'      no access_instructions or door_code on property
  --   'missing_wifi_credentials'         no wifi_network or wifi_password
  --   'missing_parking_details'          no parking_details, parking_type = 'none'
  --   'expired_str_license'              str_license_expires < today
  --   'expiring_str_license'             str_license_expires within 90 days
  --   'overdue_task'                     task.due_date passed, status not terminal
  --   'unassigned_task'                  task exists with no assignee within 24h of schedule
  --   'same_day_turnover'                checkout and checkin on same day, no clean scheduled
  --   'guest_count_exceeds_capacity'     reservation.guest_count > property.max_guests
  --   'access_code_not_set'             guest_access_code null for arriving reservation

  severity              risk_severity   NOT NULL,
  title                 TEXT            NOT NULL,
  detail                TEXT,
  recommendation        TEXT,

  -- Timing context (denormalized for fast sorting)
  hours_until_checkin   NUMERIC(6,1),
  checkin_date          DATE,

  -- State
  is_active             BOOLEAN         NOT NULL DEFAULT TRUE,
  resolved_at           TIMESTAMPTZ,
  resolved_by           UUID            REFERENCES people (id) ON DELETE SET NULL,
  resolution_note       TEXT,
  snoozed_until         TIMESTAMPTZ,
  suppressed            BOOLEAN         NOT NULL DEFAULT FALSE,

  -- Attribution
  detected_by           detected_by     NOT NULL DEFAULT 'risk_engine',
  computed_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  created_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risks_property_id    ON operational_risks (property_id);
CREATE INDEX idx_risks_reservation_id ON operational_risks (reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_risks_task_id        ON operational_risks (task_id)        WHERE task_id IS NOT NULL;
CREATE INDEX idx_risks_type           ON operational_risks (risk_type);
CREATE INDEX idx_risks_active         ON operational_risks (is_active, severity);
CREATE INDEX idx_risks_checkin_date   ON operational_risks (checkin_date, severity)  WHERE is_active = TRUE;
-- Primary dashboard query: active risks by urgency
CREATE INDEX idx_risks_dashboard      ON operational_risks (severity, hours_until_checkin)
  WHERE is_active = TRUE AND suppressed = FALSE;

-- =============================================================================
-- TABLE: thursday_call_items
-- Source: Auto-generated by risk engine + pattern engine + manual curation
-- The weekly leadership briefing. A working document, not just a report.
-- =============================================================================

CREATE TABLE thursday_call_items (
  id                    UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
  call_date             DATE              NOT NULL,

  -- Context links (all nullable — item may relate to multiple entities)
  property_id           UUID              REFERENCES properties       (id) ON DELETE SET NULL,
  reservation_id        UUID              REFERENCES reservations     (id) ON DELETE SET NULL,
  task_id               UUID              REFERENCES tasks            (id) ON DELETE SET NULL,
  operational_risk_id   UUID              REFERENCES operational_risks(id) ON DELETE SET NULL,

  -- Content
  category              thursday_category NOT NULL DEFAULT 'general',
  title                 TEXT              NOT NULL,
  summary               TEXT,
  recommendation        TEXT,
  priority              SMALLINT          NOT NULL DEFAULT 5
                          CHECK (priority BETWEEN 1 AND 10),

  -- Source & attribution
  source                TEXT              NOT NULL DEFAULT 'auto',
  generated_by          TEXT,

  -- Status
  status                thursday_status   NOT NULL DEFAULT 'open',
  outcome_notes         TEXT,
  owner                 TEXT,
  due_date              DATE,
  carried_forward       BOOLEAN           NOT NULL DEFAULT FALSE,
  carried_from_date     DATE,

  created_at            TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_thursday_call_date   ON thursday_call_items (call_date);
CREATE INDEX idx_thursday_property_id ON thursday_call_items (property_id)  WHERE property_id IS NOT NULL;
CREATE INDEX idx_thursday_status      ON thursday_call_items (call_date, status);
CREATE INDEX idx_thursday_category    ON thursday_call_items (category);
CREATE INDEX idx_thursday_open        ON thursday_call_items (call_date, priority)
  WHERE status = 'open';

-- =============================================================================
-- TABLE: pascal_insights
-- Source: Pascal AI Copilot (Claude API)
-- Every AI output is persisted for auditability. Reuse before regenerating.
-- Week-one: schema ready. Pascal activation happens in a later phase.
-- =============================================================================

CREATE TABLE pascal_insights (
  id                    UUID                PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Insight type
  insight_type          pascal_insight_type NOT NULL,

  -- Subject context
  property_id           UUID                REFERENCES properties       (id) ON DELETE SET NULL,
  reservation_id        UUID                REFERENCES reservations     (id) ON DELETE SET NULL,
  task_id               UUID                REFERENCES tasks            (id) ON DELETE SET NULL,
  operational_risk_id   UUID                REFERENCES operational_risks(id) ON DELETE SET NULL,
  thursday_call_date    DATE,

  -- Content
  prompt_summary        TEXT,
  insight_text          TEXT                NOT NULL,
  confidence_level      confidence_level,
  recommended_actions   TEXT[],

  -- Model metadata
  model_id              TEXT,
  input_tokens          INTEGER,
  output_tokens         INTEGER,
  generation_time_ms    INTEGER,

  -- Review state
  is_reviewed           BOOLEAN             NOT NULL DEFAULT FALSE,
  reviewed_by           TEXT,
  reviewed_at           TIMESTAMPTZ,
  was_actioned          BOOLEAN,
  feedback              TEXT,

  created_at            TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pascal_property_id     ON pascal_insights (property_id)         WHERE property_id IS NOT NULL;
CREATE INDEX idx_pascal_reservation_id  ON pascal_insights (reservation_id)      WHERE reservation_id IS NOT NULL;
CREATE INDEX idx_pascal_insight_type    ON pascal_insights (insight_type);
CREATE INDEX idx_pascal_thursday        ON pascal_insights (thursday_call_date)  WHERE thursday_call_date IS NOT NULL;
CREATE INDEX idx_pascal_created_at      ON pascal_insights (created_at DESC);

-- =============================================================================
-- TABLE: pascal_conversations
-- Source: Pascal AI Copilot
-- Session history for multi-turn Pascal interactions.
-- Week-one: schema ready. UI activation happens in a later phase.
-- =============================================================================

CREATE TABLE pascal_conversations (
  id              UUID                  PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      UUID                  NOT NULL,
  property_id     UUID                  REFERENCES properties   (id) ON DELETE SET NULL,
  reservation_id  UUID                  REFERENCES reservations (id) ON DELETE SET NULL,
  context_type    pascal_context_type,
  role            pascal_role           NOT NULL,
  content         TEXT                  NOT NULL,
  turn_number     SMALLINT              NOT NULL,
  model_id        TEXT,
  input_tokens    INTEGER,
  output_tokens   INTEGER,
  created_at      TIMESTAMPTZ           NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_session    ON pascal_conversations (session_id, turn_number);
CREATE INDEX idx_conversations_property   ON pascal_conversations (property_id) WHERE property_id IS NOT NULL;
CREATE INDEX idx_conversations_created    ON pascal_conversations (created_at DESC);

-- =============================================================================
-- TABLE: sync_log
-- Source: BEM sync pipeline
-- Non-negotiable from day one. If syncs fail silently, the risk engine
-- operates on stale data. This table is the canary.
-- =============================================================================

CREATE TABLE sync_log (
  id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  source           sync_source  NOT NULL,
  entity_type      sync_entity  NOT NULL,
  sync_type        sync_type    NOT NULL,
  status           sync_status  NOT NULL,
  records_fetched  INTEGER      NOT NULL DEFAULT 0,
  records_created  INTEGER      NOT NULL DEFAULT 0,
  records_updated  INTEGER      NOT NULL DEFAULT 0,
  records_failed   INTEGER      NOT NULL DEFAULT 0,
  error_message    TEXT,
  api_calls_made   SMALLINT,
  duration_ms      INTEGER,
  started_at       TIMESTAMPTZ  NOT NULL,
  completed_at     TIMESTAMPTZ
);

CREATE INDEX idx_sync_log_source    ON sync_log (source, entity_type, started_at DESC);
CREATE INDEX idx_sync_log_status    ON sync_log (status, started_at DESC);
CREATE INDEX idx_sync_log_started   ON sync_log (started_at DESC);

-- =============================================================================
-- UPDATED_AT TRIGGERS
-- Keeps updated_at current on any row modification.
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_people_updated_at
  BEFORE UPDATE ON people
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_properties_updated_at
  BEFORE UPDATE ON properties
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_reservations_updated_at
  BEFORE UPDATE ON reservations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tasks_updated_at
  BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_risks_updated_at
  BEFORE UPDATE ON operational_risks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_thursday_updated_at
  BEFORE UPDATE ON thursday_call_items
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- VIEWS
-- Pre-built queries for the Operations Dashboard.
-- No application logic required for the common reads.
-- =============================================================================

-- ----------------------------------------------------------------------------
-- VIEW: v_at_risk_arrivals
-- At-Risk Arrivals dashboard panel.
-- Active risks on confirmed reservations arriving within 72 hours.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_at_risk_arrivals AS
SELECT
  r.id                          AS reservation_id,
  r.checkin_date,
  r.guest_name,
  r.guest_count,
  r.channel,
  r.status                      AS reservation_status,
  p.id                          AS property_id,
  p.internal_name               AS property_name,
  p.street,
  p.city,
  p.bedrooms,
  p.cleanliness_status,
  p.access_instructions,
  p.door_code,
  p.wifi_network,
  p.wifi_password,
  o.id                          AS risk_id,
  o.risk_type,
  o.severity,
  o.title                       AS risk_title,
  o.recommendation,
  o.hours_until_checkin
FROM operational_risks o
JOIN reservations r ON r.id = o.reservation_id
JOIN properties   p ON p.id = o.property_id
WHERE o.is_active   = TRUE
  AND o.suppressed  = FALSE
  AND r.status      = 'confirmed'
  AND r.checkin_date >= CURRENT_DATE
  AND r.checkin_date <= CURRENT_DATE + INTERVAL '3 days'
ORDER BY o.severity DESC, o.hours_until_checkin ASC NULLS LAST;

-- ----------------------------------------------------------------------------
-- VIEW: v_stale_tasks
-- Stale Tasks dashboard panel.
-- Open tasks that are overdue, stale, or blocking an arrival.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_stale_tasks AS
SELECT
  t.id                          AS task_id,
  t.breezeway_task_id,
  t.department,
  t.task_name,
  t.priority,
  t.status,
  t.scheduled_date,
  t.due_date,
  t.is_overdue,
  t.is_stale,
  t.stale_since,
  t.blocks_arrival,
  t.updated_at,
  p.id                          AS property_id,
  p.internal_name               AS property_name,
  p.street,
  p.city,
  r.checkin_date,
  r.guest_name,
  -- Assignee names aggregated
  ARRAY_AGG(pe.full_name) FILTER (WHERE pe.full_name IS NOT NULL) AS assignees
FROM tasks t
JOIN properties  p  ON p.id = t.property_id
LEFT JOIN reservations r  ON r.id = t.reservation_id
LEFT JOIN task_assignments ta ON ta.task_id = t.id
LEFT JOIN people           pe ON pe.id = ta.person_id
WHERE t.deleted_at IS NULL
  AND t.status NOT IN ('completed', 'approved', 'closed')
  AND (t.is_overdue = TRUE OR t.is_stale = TRUE OR t.blocks_arrival = TRUE)
GROUP BY t.id, p.id, r.id
ORDER BY t.blocks_arrival DESC, t.priority ASC, t.due_date ASC NULLS LAST;

-- ----------------------------------------------------------------------------
-- VIEW: v_quick_wins
-- Quick Wins dashboard panel.
-- Unblocked open tasks that are low-complexity and unassigned or near-due.
-- A "quick win" = normal/low priority + assigned + not yet started + due soon.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_quick_wins AS
SELECT
  t.id                          AS task_id,
  t.breezeway_task_id,
  t.department,
  t.task_name,
  t.priority,
  t.status,
  t.scheduled_date,
  t.due_date,
  t.estimated_hours,
  p.id                          AS property_id,
  p.internal_name               AS property_name,
  p.street,
  p.city,
  ARRAY_AGG(pe.full_name) FILTER (WHERE pe.full_name IS NOT NULL) AS assignees
FROM tasks t
JOIN properties  p  ON p.id = t.property_id
LEFT JOIN task_assignments ta ON ta.task_id = t.id
LEFT JOIN people           pe ON pe.id = ta.person_id
WHERE t.deleted_at IS NULL
  AND t.status     IN ('pending', 'assigned')
  AND t.priority   IN ('normal', 'low')
  AND t.is_stale   = FALSE
  AND t.is_overdue = FALSE
  AND (t.estimated_hours IS NULL OR t.estimated_hours <= 2)
  AND t.scheduled_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
GROUP BY t.id, p.id
ORDER BY t.scheduled_date ASC, t.priority ASC;

-- ----------------------------------------------------------------------------
-- VIEW: v_thursday_call
-- Thursday Call Intelligence panel.
-- Current week's call items, open and carried-forward, priority ordered.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_thursday_call AS
SELECT
  tc.id,
  tc.call_date,
  tc.category,
  tc.priority,
  tc.title,
  tc.summary,
  tc.recommendation,
  tc.status,
  tc.source,
  tc.generated_by,
  tc.owner,
  tc.due_date,
  tc.outcome_notes,
  tc.carried_forward,
  tc.carried_from_date,
  p.internal_name   AS property_name,
  p.street          AS property_street,
  r.checkin_date    AS reservation_checkin,
  r.guest_name      AS reservation_guest
FROM thursday_call_items tc
LEFT JOIN properties   p ON p.id = tc.property_id
LEFT JOIN reservations r ON r.id = tc.reservation_id
WHERE tc.call_date = (
  -- Upcoming Thursday: today if Thursday, otherwise next Thursday
  -- PostgreSQL DOW: Sun=0 Mon=1 Tue=2 Wed=3 Thu=4 Fri=5 Sat=6
  CURRENT_DATE + ((4 - EXTRACT(DOW FROM CURRENT_DATE)::INTEGER + 7) % 7) * INTERVAL '1 day'
)
ORDER BY tc.priority ASC, tc.status ASC;

-- ----------------------------------------------------------------------------
-- VIEW: v_property_data_quality
-- Data quality gaps across the portfolio.
-- Drives the "Data Quality Alert" category in thursday_call_items.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_property_data_quality AS
SELECT
  id                            AS property_id,
  internal_name                 AS property_name,
  street,
  city,
  bedrooms,
  dq_completeness_score,
  dq_has_structured_wifi,
  dq_has_structured_door_code,
  dq_has_parking_details,
  dq_has_additional_checkin,
  dq_has_unit_notes,
  str_license_expired,
  str_license_expires,
  -- Flag properties expiring within 90 days
  CASE
    WHEN str_license_expires IS NOT NULL
     AND str_license_expires <= CURRENT_DATE + INTERVAL '90 days'
     AND str_license_expires > CURRENT_DATE
    THEN TRUE ELSE FALSE
  END                           AS str_license_expiring_soon,
  -- Count missing critical fields
  (
    CASE WHEN access_instructions IS NULL THEN 1 ELSE 0 END +
    CASE WHEN wifi_network IS NULL OR wifi_password IS NULL THEN 1 ELSE 0 END +
    CASE WHEN parking_type IS NULL THEN 1 ELSE 0 END +
    CASE WHEN house_rules IS NULL THEN 1 ELSE 0 END +
    CASE WHEN contact_phone IS NULL THEN 1 ELSE 0 END
  )                             AS missing_critical_field_count
FROM properties
ORDER BY dq_completeness_score ASC NULLS FIRST, missing_critical_field_count DESC;

-- =============================================================================
-- ROW LEVEL SECURITY
-- Enable RLS on all tables. Policies to be configured per Supabase auth setup.
-- Tables are locked down by default; no data is accessible without a policy.
-- =============================================================================

ALTER TABLE people                ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties            ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations          ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_assignments      ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_comments         ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_risks     ENABLE ROW LEVEL SECURITY;
ALTER TABLE thursday_call_items   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pascal_insights       ENABLE ROW LEVEL SECURITY;
ALTER TABLE pascal_conversations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log              ENABLE ROW LEVEL SECURITY;

-- Service role bypass (used by the sync pipeline and risk engine).
-- Application-level user policies are added separately after auth is configured.
CREATE POLICY "service_role_all_people"               ON people               FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_properties"           ON properties           FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_reservations"         ON reservations         FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_tasks"                ON tasks                FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_task_assignments"     ON task_assignments      FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_task_comments"        ON task_comments         FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_operational_risks"    ON operational_risks     FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_thursday_call_items"  ON thursday_call_items   FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_pascal_insights"      ON pascal_insights       FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_pascal_conversations" ON pascal_conversations  FOR ALL TO service_role USING (TRUE);
CREATE POLICY "service_role_all_sync_log"             ON sync_log              FOR ALL TO service_role USING (TRUE);

-- =============================================================================
-- COMMENTS
-- Inline documentation for every table. Visible in Supabase Studio.
-- =============================================================================

COMMENT ON TABLE people               IS 'Staff roster synced from Breezeway People API.';
COMMENT ON TABLE properties           IS 'Property master record. Source: Breezeway (primary) + Hostaway (identity enrichment). Central table — every other table references this.';
COMMENT ON TABLE reservations         IS 'Guest stays synced from Hostaway. Every at-risk arrival originates here.';
COMMENT ON TABLE tasks                IS 'Operational tasks synced from Breezeway. The platform heartbeat — cleaning, maintenance, inspection, safety.';
COMMENT ON TABLE task_assignments     IS 'Many-to-many: which people are assigned to which tasks.';
COMMENT ON TABLE task_comments        IS 'Comment threads on tasks from Breezeway. Key signal for staleness and delay context.';
COMMENT ON TABLE operational_risks    IS 'Computed risk signals. Written by the risk engine, not synced from any external API. One row per risk signal — a reservation can have multiple active risks.';
COMMENT ON TABLE thursday_call_items  IS 'Weekly leadership briefing agenda. Auto-generated from risk and pattern engines, manually curated. Working document — outcome_notes captured on the call.';
COMMENT ON TABLE pascal_insights      IS 'Persisted AI outputs from Pascal (Claude API). Every generation is stored for audit and reuse. Week-one: schema ready. Pascal activation is Phase 2.';
COMMENT ON TABLE pascal_conversations IS 'Session history for multi-turn Pascal interactions. Week-one: schema ready. UI activation is Phase 2.';
COMMENT ON TABLE sync_log             IS 'Pipeline health record. Every sync from Breezeway or Hostaway writes a row. If syncs fail silently, the risk engine operates on stale data — this table is the canary.';

COMMENT ON COLUMN properties.str_license_expired         IS 'Set by the risk engine on each sync. TRUE when str_license_expires < today. Cannot be a generated column (CURRENT_DATE is not immutable).';
COMMENT ON COLUMN reservations.nights                    IS 'Generated column. checkout_date - checkin_date.';
COMMENT ON COLUMN tasks.is_overdue                       IS 'Set by the risk engine on each sync. TRUE when due_date < today and status is not terminal. Cannot be a generated column (CURRENT_DATE is not immutable).';
COMMENT ON COLUMN tasks.is_stale                         IS 'Set by the risk engine, not generated. Requires activity-window logic beyond a simple date comparison.';
COMMENT ON COLUMN tasks.blocks_arrival                   IS 'Set by the risk engine. TRUE when an open task is linked to a reservation arriving within the alert window.';
COMMENT ON COLUMN operational_risks.risk_type            IS 'See schema doc for full enumeration of 14 risk types. Stored as TEXT (not ENUM) to allow new types without a schema migration.';
COMMENT ON COLUMN pascal_insights.insight_type           IS 'Category of AI output. Determines which context is assembled and which tables are queried before generation.';
