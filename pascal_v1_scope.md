# Pascal V1 — Scope Definition
**BEM Operations Intelligence Center**  
**Date:** 2026-06-18  
**Status:** Approved for build

---

## What Pascal V1 Is

Pascal V1 is a CLI-invoked AI briefing tool that answers 5 specific operational questions using data already in Supabase. It calls Claude, stores every response in `pascal_insights`, and prints the result. There is no chat interface, no follow-up turns, no property search, and no guest-facing output in V1.

**The demo standard:** David opens his laptop at 8 AM, runs one command, and in under 30 seconds has the operational brief he would otherwise spend 20 minutes assembling from Hostaway and Breezeway.

---

## The 5 Questions Pascal V1 Will Answer

These are selected from `pascal_v1_questions.md` based on three criteria:
1. Data is available today (no Breezeway required)
2. Directly surfaces guest-impacting risk
3. Would change what David does in the next 4 hours

---

### Q1 — What arrivals in the next 72 hours are at risk, and what needs to happen?

**Source question:** Q1 (At-Risk Arrivals) + Q13 (Daily Arrival Sheet)  
**Command:** `python main.py pascal arrivals`  
**Insight type:** `arrival_risk_summary`

**User experience:**
```
$ python main.py pascal arrivals

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASCAL — Arrival Risk Brief
  Generated: 2026-06-18 08:04
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Pascal narrative text here — 150–250 words]

Recommended actions:
  1. [Action]
  2. [Action]
  3. [Action]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Insight saved · 312 tokens · 4.2s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**What Pascal tells David:**
- How many arrivals in the next 72 hours have active risks
- Which are critical (arriving today with open cleans or no access code)
- Who is assigned and whether anything is stale
- The 3 highest-priority actions, in order

**What Pascal does not do:**
- Does not list every arriving guest — only the ones with risk
- Does not show resolved risks
- Does not suggest reassigning staff (no real Breezeway data yet)

**Context assembled before calling Claude:**
```sql
SELECT
  p.internal_name, r.guest_name, r.checkin_date, r.guest_count,
  r.guest_access_code,
  o.severity, o.risk_type, o.title, o.recommendation, o.hours_until_checkin
FROM operational_risks o
JOIN reservations r ON r.id = o.reservation_id
JOIN properties   p ON p.id = o.property_id
WHERE o.is_active = TRUE AND o.suppressed = FALSE
  AND r.status = 'confirmed'
  AND r.checkin_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
ORDER BY o.severity DESC, o.hours_until_checkin ASC;
```

---

### Q2 — Which properties have no guest access code for an upcoming arrival?

**Source question:** Q2 (Missing Access Codes)  
**Command:** `python main.py pascal access`  
**Insight type:** `data_quality_alert`

**User experience:**
```
$ python main.py pascal access

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASCAL — Access Code Gap Report
  Generated: 2026-06-18 08:05
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Pascal narrative — 100–150 words]

Properties requiring access code before arrival:
  TODAY      334 Carondelet      Seth Cohen      3 PM
  TODAY      6622 Urquhart       Miriam Lawrence 3 PM
  TOMORROW   910 Jefferson       Luke Cree       3 PM
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**What Pascal tells David:**
- Total count of reservations arriving within 14 days with no `guest_access_code`
- Sorted by urgency (arriving soonest first)
- Whether the property has a structured door code that can be sent immediately vs. requires manual lookup from `access_instructions`
- One recommended process fix (the root cause is a process gap, not a data gap)

**What Pascal does not do:**
- Does not send the access code — that stays in Hostaway
- Does not attempt to extract codes from free-text `access_instructions`

**Context assembled before calling Claude:**
```sql
SELECT
  p.internal_name, p.street, p.door_code, p.door_code_source,
  p.access_instructions,
  r.guest_name, r.checkin_date, r.channel,
  (r.checkin_date - CURRENT_DATE) AS days_until_checkin
FROM reservations r
JOIN properties p ON p.id = r.property_id
WHERE r.status = 'confirmed'
  AND r.checkin_date >= CURRENT_DATE
  AND r.checkin_date <= CURRENT_DATE + 14
  AND r.guest_access_code IS NULL
ORDER BY r.checkin_date ASC;
```

---

### Q3 — What should be on the Thursday call agenda this week?

**Source question:** Q14 (Thursday Call Synthesis)  
**Command:** `python main.py pascal thursday`  
**Insight type:** `thursday_call_brief`

**User experience:**
```
$ python main.py pascal thursday

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASCAL — Thursday Call Brief
  Call date: June 19, 2026
  Generated: 2026-06-18 08:06
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Pascal narrative — 300–400 words structured as an agenda]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  46 items synthesized · Insight saved
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**What Pascal tells David:**
- A structured agenda in 4 sections: Open Before Friday / Discuss Thursday / Assign or Carry / Watch List
- Item count per section
- The 2–3 highest-urgency items called out explicitly with recommended owner
- Items that can be closed in <5 minutes on the call vs. items that need decisions

**What Pascal does not do:**
- Does not allow editing of thursday_call_items through Pascal (the dashboard handles that)
- Does not pull in items that aren't already in the `thursday_call_items` table
- Does not send the agenda to Slack or email

**Context assembled before calling Claude:**
```sql
SELECT tc.category, tc.priority, tc.title, tc.summary, tc.recommendation,
       tc.status, tc.source,
       p.internal_name AS property_name,
       r.checkin_date, r.guest_name
FROM thursday_call_items tc
LEFT JOIN properties   p ON p.id = tc.property_id
LEFT JOIN reservations r ON r.id = tc.reservation_id
WHERE tc.call_date = CURRENT_DATE + ((4 - EXTRACT(DOW FROM CURRENT_DATE)::INTEGER + 7) % 7)
ORDER BY tc.priority ASC, tc.category ASC;
```

---

### Q4 — What is the current operational status of a specific property?

**Source question:** Q4 (Single-Property Briefing) + Q19 (Check-In Brief)  
**Command:** `python main.py pascal property "carondelet"`  
**Insight type:** `property_briefing`

**User experience:**
```
$ python main.py pascal property "carondelet"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASCAL — Property Brief: 334 Carondelet St
  Generated: 2026-06-18 08:07
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Pascal narrative — 150–250 words]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**What Pascal tells David:**
- Property basics: bedrooms, rating, next guest arrival
- Access: check-in time, door code status, WiFi status (structured vs. embedded in text)
- Active risks at this property, most urgent first
- Open tasks (count + highest priority task)
- STR license status
- Missing data flags (no structured WiFi, no structured door code)

**What Pascal does not do:**
- Does not list all historical tasks — only open ones
- Does not require an exact property name match — uses `ILIKE '%query%'` and returns the closest match; if ambiguous, lists the candidates and exits
- Does not show past guest information

**Context assembled before calling Claude:**
```sql
-- Two queries: property + active risks
SELECT p.*, 
  (SELECT r.guest_name FROM reservations r
   WHERE r.property_id = p.id AND r.status = 'confirmed'
     AND r.checkin_date >= CURRENT_DATE ORDER BY r.checkin_date ASC LIMIT 1) AS next_guest,
  (SELECT r.checkin_date FROM reservations r
   WHERE r.property_id = p.id AND r.status = 'confirmed'
     AND r.checkin_date >= CURRENT_DATE ORDER BY r.checkin_date ASC LIMIT 1) AS next_arrival
FROM properties p
WHERE p.internal_name ILIKE '%:query%' OR p.street ILIKE '%:query%'
LIMIT 1;

SELECT o.severity, o.risk_type, o.title, o.recommendation
FROM operational_risks o
WHERE o.property_id = :property_id AND o.is_active = TRUE
ORDER BY o.severity DESC;
```

---

### Q5 — What is the overall portfolio health right now?

**Source question:** Q10 (Data Quality) + Q6 (STR Compliance) + synthesized from `operational_risks`  
**Command:** `python main.py pascal health`  
**Insight type:** `arrival_risk_summary` (portfolio scope — no `reservation_id`)

**User experience:**
```
$ python main.py pascal health

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASCAL — Portfolio Health Brief
  Generated: 2026-06-18 08:08
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Pascal narrative — 200–300 words]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**What Pascal tells David:**
- Active risk count by severity across the portfolio
- The dominant risk type (what's causing the most exposure)
- Properties with expired STR licenses: count and names
- Data quality gaps that operationally matter (access codes, WiFi)
- One systemic recommendation — the highest-leverage action available today

**What Pascal does not do:**
- Does not produce a per-property table (that's the dashboard)
- Does not compare to prior weeks (no history yet)
- Does not grade individual staff performance

**Context assembled before calling Claude:**
```sql
-- Risk summary
SELECT risk_type, severity, COUNT(*) AS count
FROM operational_risks
WHERE is_active = TRUE
GROUP BY risk_type, severity
ORDER BY severity DESC, count DESC;

-- Compliance
SELECT COUNT(*) FILTER (WHERE str_license_expired = TRUE)          AS expired_licenses,
       COUNT(*) FILTER (WHERE str_license_expiring_soon = TRUE)    AS expiring_soon,
       COUNT(*) FILTER (WHERE dq_has_structured_wifi = FALSE)      AS no_structured_wifi,
       COUNT(*) FILTER (WHERE dq_has_structured_door_code = FALSE) AS no_structured_door_code,
       COUNT(*)                                                     AS total
FROM properties;
```

---

## Required Tables and Views

### Read (Pascal assembles context from these)

| Table / View | Used by | Notes |
|---|---|---|
| `operational_risks` | Q1, Q5 | Core risk data — all 140 active records available |
| `reservations` | Q1, Q2, Q4 | Guest name, checkin_date, guest_access_code |
| `properties` | Q1, Q2, Q4, Q5 | Internal name, door_code, WiFi, STR license fields, DQ flags |
| `thursday_call_items` | Q3 | Auto-generated by risk engine; 46 items available |
| `v_at_risk_arrivals` | Q1 (supplemental) | Pre-joined view for arrivals with risks |
| `v_thursday_call` | Q3 (supplemental) | Pre-filtered to upcoming Thursday |
| `v_property_data_quality` | Q5 (supplemental) | Aggregated DQ flags per property |

### Write (Pascal writes output here)

| Table | Written by | Notes |
|---|---|---|
| `pascal_insights` | All 5 questions | Every response persisted — `insight_type`, `insight_text`, `recommended_actions[]`, token counts |

### Not used in V1

`tasks`, `task_assignments`, `people`, `task_comments`, `task_requirements`, `recurring_issues`, `amenities`, `pascal_conversations`

---

## Required API Endpoints

### Claude API (Anthropic)
- **Model:** `claude-sonnet-4-6` (current session model — use this for consistency)
- **Call type:** Single-turn, non-streaming for V1
- **Max output tokens:** 800 per call (sufficient for 250-word brief + action list)
- **Temperature:** 0 — Pascal answers ops questions; creativity is not the goal
- **System prompt:** Shared across all 5 questions (see System Prompt section below)
- **Auth:** `ANTHROPIC_API_KEY` in `.env`

### Supabase (already connected)
- **Client:** `app/db/client.py` — `db.select()`, `db.select_view()`, existing methods
- **No new Supabase endpoints needed** — all reads use existing client methods

### Not required in V1
No Hostaway API calls during Pascal execution. No Breezeway API calls. Pascal is read-only against Supabase.

---

## System Prompt (shared across all 5 questions)

```
You are Pascal, an operations AI assistant for Big Easy Management (BEM), a short-term 
rental company operating ~100 properties in New Orleans.

Your only job is to surface operational risk before it reaches a guest.

Answer factually, based only on the data provided. Do not speculate. Do not add caveats 
or disclaimers. Do not suggest checking a system the user can check themselves — tell them 
what the data says.

Be direct. Use plain language. Use specific property names, guest names, and dates from 
the data — never generalize when specifics are available.

Formatting rules:
- Lead with the most urgent fact
- Use short paragraphs, not bullet soup
- End with a numbered list of recommended actions (max 4)
- Do not use headings inside your response
- No more than 300 words total

Today's date: {today}
```

---

## CLI Interface (additions to `main.py`)

New subcommand: `pascal`  
Pattern: `python main.py pascal <question> [arg]`

| Command | Question |
|---|---|
| `python main.py pascal arrivals` | Q1 — At-risk arrivals brief |
| `python main.py pascal access` | Q2 — Missing access codes |
| `python main.py pascal thursday` | Q3 — Thursday call agenda |
| `python main.py pascal property "<query>"` | Q4 — Single property brief |
| `python main.py pascal health` | Q5 — Portfolio health |

Additional env var required: `ANTHROPIC_API_KEY`

---

## What Is Deferred to Phase 2

### Deferred features

| Feature | Why deferred |
|---|---|
| **Interactive chat** (`pascal_conversations` table) | Multi-turn adds context management complexity with no additional risk coverage for V1 |
| **Q3 — Housekeeping task status** | Requires real Breezeway data; mock data is not reliable enough for a brief David would act on |
| **Q4 — Stale task investigation** | Same — actionable only with real task comment history |
| **Q5 — Staff workload snapshot** | Same — requires real Breezeway people + assignment data |
| **Q9 — Same-day turnover gaps** | Requires real task records to be meaningful |
| **Q12 — Recurring issue analysis** | Requires `recurring_issues` table (Phase 2) and 30+ days of task history |
| **Q16 — Housekeeper performance** | Requires actual vs. estimated hours from Breezeway |
| **Q17 — Inspection pass rates** | Requires `task_requirements` checklist data |
| **Q20 — Portfolio improvement recommendations** | Requires recurring_issues + review history |
| **Slack / email delivery** | Integration complexity; CLI output sufficient for demo |
| **Feedback loop** (`is_reviewed`, `was_actioned`) | Valuable for V2 quality improvement; no UI to collect it in V1 |
| **Caching / deduplication** | Regenerating is cheap at this scale; dedup adds complexity |
| **Web UI** | CLI is sufficient for David's workflow and for demo |
| **Guest-facing output** | Out of scope for operations tool |

### Deferred questions from `pascal_v1_questions.md`

Q3, Q5, Q7 (WiFi), Q8, Q9, Q11, Q12, Q15, Q16, Q17, Q18, Q20 are all deferred.  
Q7 (WiFi data gap) and Q18 (low-rated properties) are candidates for V1.1 — they require only property data but add limited urgency information vs. Q1–Q5.

---

## Definition of Done for Pascal V1

- [ ] `python main.py pascal arrivals` produces a narrative brief and saves to `pascal_insights`
- [ ] `python main.py pascal access` produces a prioritized access-code list with narrative
- [ ] `python main.py pascal thursday` produces a structured call agenda narrative
- [ ] `python main.py pascal property "carondelet"` returns a property brief with fuzzy name match
- [ ] `python main.py pascal health` returns a portfolio risk summary
- [ ] All 5 commands complete in under 15 seconds
- [ ] Every response is written to `pascal_insights` with `insight_type`, `model_id`, token counts
- [ ] Missing `ANTHROPIC_API_KEY` produces a clear error before any API call
- [ ] No Breezeway or Hostaway API calls during Pascal execution

---

## What the Demo Looks Like

David opens a terminal on Thursday morning before the ops call.

```bash
python main.py pascal arrivals
python main.py pascal thursday
```

Two commands. Under 30 seconds total. He has the morning brief and the call agenda.

If a specific property comes up on the call:

```bash
python main.py pascal property "urquhart"
```

That is Pascal V1.
