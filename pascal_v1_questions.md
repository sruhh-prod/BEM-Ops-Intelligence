# Pascal V1 — Operations Questions
## BEM Operations Intelligence Center
**Generated:** 2026-06-18  
**Reference:** `bem_ops_database_schema.md`, `property_intelligence_schema.md`, `listing_field_inventory.md`

---

## Design Principle

Pascal is not a search engine. Pascal answers the question David would have asked a trusted operations manager at 8 AM on a Monday: *"What do I need to know, and what should we do about it?"*

As defined in `bem_ops_database_schema.md`:
> **Purpose:** Surface operational risk before it reaches a guest.

Every question Pascal answers maps to one of four outcomes:
1. **Prevent** a guest impact before it happens
2. **Resolve** a known problem faster
3. **Identify** a pattern no one has noticed yet
4. **Brief** leadership without manual report-pulling

---

## Readiness Key

| Label | Meaning |
|---|---|
| **MVP** | Answerable today — data is in Supabase from Hostaway + mock Breezeway |
| **Requires Breezeway** | Data structure exists; real Breezeway connection needed to populate it |
| **Future** | Requires `recurring_issues`, `task_requirements`, or additional data sources |

---

## The 20 Questions

---

### Q1 — What properties have guests arriving in the next 72 hours that are not ready?

**Readiness:** MVP

**Why David asks it:**  
This is the most important question in operations. A guest arriving to a dirty, inaccessible, or unprepared unit is a 1-star review, a refund request, and a reputation hit. The dashboard surfaces this automatically via `v_at_risk_arrivals`, but Pascal turns it into a briefing David can act on in under 2 minutes.

**Required data sources:**  
`reservations`, `operational_risks`, `properties`, `tasks`, `task_assignments`, `people`

**SQL:**
```sql
SELECT
  p.internal_name,
  r.guest_name,
  r.checkin_date,
  r.guest_count,
  o.severity,
  o.risk_type,
  o.title,
  o.recommendation,
  o.hours_until_checkin,
  ARRAY_AGG(pe.full_name) FILTER (WHERE pe.full_name IS NOT NULL) AS assignees
FROM operational_risks o
JOIN reservations r ON r.id = o.reservation_id
JOIN properties   p ON p.id = o.property_id
LEFT JOIN tasks        t  ON t.id = o.task_id
LEFT JOIN task_assignments ta ON ta.task_id = t.id
LEFT JOIN people       pe ON pe.id = ta.person_id
WHERE o.is_active  = TRUE
  AND o.suppressed = FALSE
  AND r.status     = 'confirmed'
  AND r.checkin_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
GROUP BY p.internal_name, r.guest_name, r.checkin_date, r.guest_count,
         o.severity, o.risk_type, o.title, o.recommendation, o.hours_until_checkin
ORDER BY o.severity DESC, o.hours_until_checkin ASC;
```

**Sample Pascal response:**
> **6 properties need attention before tomorrow's arrivals.**
>
> **Critical (arriving today):**
> - **334 Carondelet** — Seth Cohen arrives at 3 PM. No housekeeping task is completed and no guest access code is set. This needs both a housekeeper assigned *now* and an access code generated before noon.
> - **6622 Urquhart** — Miriam Lawrence arrives at 3 PM. Open maintenance task (burnt-out lightbulbs) assigned to Robert Chen, plus no access code set.
>
> **High (arriving tomorrow):**
> - **1724 Louisiana Ave** — Tiahna Williams. No completed clean. Maria Santos is assigned but the task has no recent activity.
> - **3 additional properties** with no access code set.
>
> **Recommended action:** Page housekeeping supervisors for Carondelet and Urquhart now. Confirm access codes for all 6 properties by end of day.

---

### Q2 — Which properties have no guest access code set for a confirmed reservation?

**Readiness:** MVP

**Why David asks it:**  
A guest who cannot enter the property at 11 PM on a Friday generates an emergency call, a refund, and sometimes a same-night hotel bill. As shown in today's risk engine run, 27 confirmed reservations currently have `guest_access_code = NULL`. This is the single most preventable guest-impact failure.

**Required data sources:**  
`reservations`, `properties`

**SQL:**
```sql
SELECT
  p.internal_name,
  p.street,
  p.door_code,
  p.access_instructions,
  r.guest_name,
  r.checkin_date,
  r.channel,
  (r.checkin_date - CURRENT_DATE) AS days_until_checkin
FROM reservations r
JOIN properties p ON p.id = r.property_id
WHERE r.status          = 'confirmed'
  AND r.checkin_date    >= CURRENT_DATE
  AND r.checkin_date    <= CURRENT_DATE + 14
  AND r.guest_access_code IS NULL
ORDER BY r.checkin_date ASC;
```

**Sample Pascal response:**
> **27 reservations arriving within 14 days have no guest access code on file.**
>
> The most urgent:
> - **334 Carondelet** — Seth Cohen arrives *today*. Property has a structured door code (`1234`) in the system, but it has not been pushed to the guest reservation. Send immediately via Hostaway.
> - **822 Baronne** — Kimberly arriving tomorrow. Door code is embedded in access instructions (not structured), so must be extracted and sent manually.
>
> **Pattern:** 99% of BEM properties store door codes in free-text `access_instructions` rather than structured fields. Until structured codes are populated, these gaps cannot be auto-resolved. Consider a one-time data entry sprint for the top 30 properties by booking frequency.

---

### Q3 — Which housekeeping tasks are not completed for arrivals in the next 48 hours?

**Readiness:** Requires Breezeway

**Why David asks it:**  
The `open_clean_before_arrival` risk is currently triggered when *no completed housekeeping task exists* — not when one is in progress, assigned, or scheduled. This question goes deeper: it tells David not just that a task is missing, but its current status and who is responsible.

**Required data sources:**  
`tasks`, `task_assignments`, `people`, `reservations`, `properties`

**SQL:**
```sql
SELECT
  p.internal_name,
  r.guest_name,
  r.checkin_date,
  t.task_name,
  t.status,
  t.scheduled_date,
  t.priority,
  t.estimated_hours,
  EXTRACT(EPOCH FROM (r.checkin_date::timestamptz - NOW())) / 3600 AS hours_until_checkin,
  ARRAY_AGG(pe.full_name) FILTER (WHERE pe.full_name IS NOT NULL) AS assignees
FROM tasks t
JOIN properties   p  ON p.id = t.property_id
JOIN reservations r  ON r.property_id = p.id
LEFT JOIN task_assignments ta ON ta.task_id = t.id
LEFT JOIN people           pe ON pe.id = ta.person_id
WHERE t.department  = 'housekeeping'
  AND t.status      NOT IN ('completed', 'approved', 'closed')
  AND t.deleted_at  IS NULL
  AND r.status      = 'confirmed'
  AND r.checkin_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 2
GROUP BY p.internal_name, r.guest_name, r.checkin_date, t.task_name,
         t.status, t.scheduled_date, t.priority, t.estimated_hours
ORDER BY r.checkin_date ASC, t.priority ASC;
```

**Sample Pascal response:**
> **8 housekeeping tasks are open for arrivals in the next 48 hours.**
>
> | Property | Guest | Arrives | Task Status | Assignee |
> |---|---|---|---|---|
> | 334 Carondelet | Seth Cohen | Today 3 PM | Assigned | Maria Santos |
> | 6622 Urquhart | Miriam Lawrence | Today 3 PM | Assigned | James Williams |
> | 1724 Louisiana | Tiahna Williams | Tomorrow | Pending | Unassigned |
>
> **Maria Santos** has 2 properties today. If Carondelet is behind schedule, Urquhart will also be at risk.
>
> **1724 Louisiana is unassigned** with a guest arriving tomorrow at 3 PM. Assign immediately.

---

### Q4 — What is the current status of all tasks at a specific property?

**Readiness:** Requires Breezeway

**Why David asks it:**  
When a guest calls with a complaint or a property is flagged at-risk, David needs a single-property snapshot in seconds — not a filtered dashboard. This is Pascal's core property briefing capability, one of the `pascal_insight_type` values defined in the schema (`property_briefing`).

**Required data sources:**  
`properties`, `tasks`, `task_assignments`, `people`, `task_comments`, `reservations`

**SQL:**
```sql
-- Replace :property_name with internal_name fragment
SELECT
  t.task_name,
  t.department,
  t.priority,
  t.status,
  t.scheduled_date,
  t.due_date,
  t.is_overdue,
  t.is_stale,
  t.blocks_arrival,
  t.estimated_hours,
  t.actual_hours,
  ARRAY_AGG(DISTINCT pe.full_name) FILTER (WHERE pe.full_name IS NOT NULL) AS assignees,
  (SELECT tc.comment_text FROM task_comments tc
   WHERE tc.task_id = t.id
   ORDER BY tc.breezeway_created_at DESC LIMIT 1) AS latest_comment
FROM tasks t
JOIN properties p ON p.id = t.property_id
LEFT JOIN task_assignments ta ON ta.task_id = t.id
LEFT JOIN people           pe ON pe.id = ta.person_id
WHERE p.internal_name ILIKE '%:property_name%'
  AND t.deleted_at IS NULL
GROUP BY t.id
ORDER BY
  CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
  t.scheduled_date ASC;
```

**Sample Pascal response:**
> **334 Carondelet St — Property Briefing**
> *3-bed/2-bath Apartment · Uptown · Review rating: 9.6 · Check-in 3 PM*
>
> **Open tasks (3):**
> - 🔴 **Pre-arrival clean** — Assigned to Maria Santos — Due today — No update in 4 hours
> - 🟡 **HVAC filter replacement** — Pending, unassigned — Due this Friday
> - ⚪ **Restock welcome amenities** — Assigned to Maria Santos — Due tomorrow
>
> **Guest arriving today:** Seth Cohen, 2 guests, via Airbnb. No access code on file.
>
> **Access:** Keypad entry, code embedded in access instructions. WiFi: ATTbp23auN / #2#fu?vy#afa
>
> **Parking:** Street parking. Guest should consider removing any items from street-facing windows.

---

### Q5 — Which tasks have not been updated in more than 48 hours and are due within 7 days?

**Readiness:** Requires Breezeway

**Why David asks it:**  
A task that goes silent — no status change, no comment, no photo — is the operational equivalent of a problem that's been dropped. The risk engine flags these as `is_stale`, but Pascal can explain *why* they're stale based on task comments and provide actionable context.

**Required data sources:**  
`tasks`, `task_comments`, `task_assignments`, `people`, `properties`

**SQL:**
```sql
SELECT
  p.internal_name,
  t.task_name,
  t.department,
  t.priority,
  t.status,
  t.scheduled_date,
  t.due_date,
  t.updated_at,
  EXTRACT(EPOCH FROM (NOW() - t.updated_at)) / 3600 AS hours_since_update,
  ARRAY_AGG(DISTINCT pe.full_name) FILTER (WHERE pe.full_name IS NOT NULL) AS assignees,
  (SELECT tc.comment_text FROM task_comments tc
   WHERE tc.task_id = t.id
   ORDER BY tc.breezeway_created_at DESC LIMIT 1) AS last_comment
FROM tasks t
JOIN properties p ON p.id = t.property_id
LEFT JOIN task_assignments ta ON ta.task_id = t.id
LEFT JOIN people           pe ON pe.id = ta.person_id
WHERE t.is_stale    = TRUE
  AND t.deleted_at  IS NULL
  AND t.status      NOT IN ('completed', 'approved', 'closed')
  AND t.due_date    <= CURRENT_DATE + 7
GROUP BY p.internal_name, t.id
ORDER BY hours_since_update DESC, t.priority ASC;
```

**Sample Pascal response:**
> **3 tasks have gone silent and are due this week.**
>
> **6622 Urquhart — Full 3BR/2BA turnover clean**
> Assigned to Maria Santos · Last update: 72 hours ago · Due today
> Last comment: *"Had to leave mid-clean — family emergency. Will return tomorrow morning."*
> → No follow-up since. Guest arrives tonight. **Call Maria now.**
>
> **[Property X] — Pre-arrival inspection**
> Assigned to Diana Torres · Last update: 96 hours ago · Due yesterday
> Last comment: *"Arrived to inspect. Garbage disposal not working."*
> → Issue noted but task not updated or escalated. Overdue.
>
> **[Property Y] — HVAC maintenance**
> Unassigned · Last update: 4 days ago
> No comments. Part ordered but arrival ETA not logged.

---

### Q6 — Which properties have expired or soon-expiring STR licenses?

**Readiness:** MVP

**Why David asks it:**  
Operating a property with an expired STR license in New Orleans exposes BEM to fines, forced listing removal, and owner liability. The risk engine flags 5 expired licenses today. Pascal turns this into an actionable compliance briefing.

**Required data sources:**  
`properties`

**SQL:**
```sql
SELECT
  internal_name,
  street,
  str_license_number,
  str_license_type,
  str_license_expires,
  str_license_expired,
  (str_license_expires - CURRENT_DATE) AS days_until_expiry,
  license_category,
  airbnb_active,
  vrbo_active,
  contact_name,
  contact_email
FROM properties
WHERE str_license_expires IS NOT NULL
  AND str_license_expires <= CURRENT_DATE + 90
ORDER BY str_license_expires ASC;
```

**Sample Pascal response:**
> **5 STR licenses are expired. 3 more expire within 90 days.**
>
> **Expired (immediate action required):**
> | Property | License # | Expired |
> |---|---|---|
> | 1039 Louisa St | STR-2021-00412 | 14 days ago |
> | 910 Jefferson | STR-2020-00891 | 31 days ago |
> | 303 Morgan St | STR-2022-00156 | 3 days ago |
>
> All 5 are currently active on Airbnb and VRBO. If the City of New Orleans audits active listings, these properties are exposed.
>
> **Expiring within 90 days:**
> - 5605 Tchoupitoulas — expires in 42 days
> - 2821 Palmyra — expires in 67 days
> - 822 Baronne — expires in 89 days
>
> **Recommended action:** Assign renewal to your compliance contact for the 5 expired licenses this week. Set calendar reminders for the remaining 3.

---

### Q7 — Which properties have no WiFi credentials on record?

**Readiness:** MVP

**Why David asks it:**  
WiFi is the #1 guest amenity complaint category across short-term rentals. As identified in `listing_field_inventory.md`, 91% of BEM properties have no structured WiFi record — the credentials are buried in free-text `access_instructions`. Until those are extracted, Communications cannot answer a guest WiFi question without opening the full listing.

**Required data sources:**  
`properties`

**SQL:**
```sql
SELECT
  internal_name,
  street,
  bedrooms,
  access_instructions,
  wifi_network,
  wifi_password,
  dq_has_structured_wifi,
  dq_completeness_score,
  review_rating
FROM properties
WHERE dq_has_structured_wifi = FALSE
ORDER BY review_rating DESC NULLS LAST;
```

**Sample Pascal response:**
> **91 of 100 properties have no structured WiFi record.**
>
> WiFi credentials exist — they're embedded in the `access_instructions` field (the Airbnb access prose) for most properties. They have never been extracted into structured fields.
>
> **Impact:** Communications cannot answer a guest WiFi question in under 30 seconds. Ops cannot verify WiFi at turnover without reading the full access block.
>
> **Top-rated properties missing structured WiFi (start here):**
> 1. 5605 Tchoupitoulas — 9.8 ⭐ — WiFi in access instructions, needs extraction
> 2. 334 Carondelet — 9.7 ⭐
> 3. 6622 Urquhart — 9.6 ⭐
>
> **Recommended action:** A 2-hour data entry sprint with the top 30 properties by rating would resolve the most guest-facing risk first. I can generate a prioritized extraction list.

---

### Q8 — Which staff members have the most open or overdue tasks right now?

**Readiness:** Requires Breezeway

**Why David asks it:**  
When tasks go stale or overdue, the first question is always: is this a scheduling problem, a communication problem, or a capacity problem? Pascal can answer it without David having to cross-reference Breezeway manually.

**Required data sources:**  
`people`, `task_assignments`, `tasks`

**SQL:**
```sql
SELECT
  pe.full_name,
  pe.role,
  COUNT(t.id)                                                        AS open_tasks,
  COUNT(t.id) FILTER (WHERE t.is_overdue = TRUE)                    AS overdue_tasks,
  COUNT(t.id) FILTER (WHERE t.is_stale   = TRUE)                    AS stale_tasks,
  COUNT(t.id) FILTER (WHERE t.blocks_arrival = TRUE)                AS blocking_arrival,
  COUNT(t.id) FILTER (WHERE t.priority IN ('urgent', 'high'))       AS high_priority_open,
  MIN(t.due_date)                                                    AS earliest_due
FROM people pe
JOIN task_assignments ta ON ta.person_id = pe.id
JOIN tasks t             ON t.id = ta.task_id
WHERE t.status   NOT IN ('completed', 'approved', 'closed')
  AND t.deleted_at IS NULL
  AND pe.is_active = TRUE
GROUP BY pe.full_name, pe.role
ORDER BY overdue_tasks DESC, blocking_arrival DESC, open_tasks DESC;
```

**Sample Pascal response:**
> **Staff workload snapshot — open tasks only:**
>
> | Staff Member | Role | Open | Overdue | Stale | Blocking Arrival |
> |---|---|---|---|---|---|
> | Maria Santos | Housekeeper | 4 | 1 | 1 | 2 |
> | James Williams | Housekeeper | 3 | 0 | 0 | 1 |
> | Robert Chen | Maintenance | 3 | 1 | 0 | 0 |
> | Diana Torres | Inspector | 2 | 1 | 1 | 0 |
>
> **Maria Santos has the heaviest load** and 2 arrival-blocking tasks. Her stale task (6622 Urquhart 3BR) had a family emergency — no follow-up since.
>
> **Diana Torres has an overdue inspection** that's gone 96 hours without an update.
>
> **Recommended action:** Check in with Maria directly on Urquhart. Reassign Diana's overdue inspection if she can't complete it today.

---

### Q9 — Are there any same-day turnovers with no clean scheduled?

**Readiness:** Requires Breezeway

**Why David asks it:**  
A same-day turnover is the highest-risk scheduling scenario in short-term rentals — the outgoing guest checks out at 11 AM and the incoming guest arrives at 3 PM, with 4 hours to turn the entire unit. If no housekeeping task is scheduled, it's guaranteed to be a failure.

**Required data sources:**  
`reservations`, `tasks`, `properties`

**SQL:**
```sql
SELECT
  p.internal_name,
  p.bedrooms,
  p.max_guests,
  r_out.guest_name  AS outgoing_guest,
  r_out.checkout_date,
  r_in.guest_name   AS incoming_guest,
  r_in.checkin_date,
  r_in.guest_count,
  p.checkout_time,
  p.checkin_time_start,
  EXISTS (
    SELECT 1 FROM tasks t
    WHERE t.property_id = p.id
      AND t.department  = 'housekeeping'
      AND t.scheduled_date = r_out.checkout_date
      AND t.status NOT IN ('completed', 'approved', 'closed')
      AND t.deleted_at IS NULL
  ) AS has_open_clean_task,
  EXISTS (
    SELECT 1 FROM tasks t
    WHERE t.property_id = p.id
      AND t.department  = 'housekeeping'
      AND t.scheduled_date = r_out.checkout_date
      AND t.status IN ('completed', 'approved')
  ) AS has_completed_clean
FROM reservations r_out
JOIN reservations r_in ON r_in.property_id = r_out.property_id
                       AND r_in.checkin_date = r_out.checkout_date
JOIN properties   p    ON p.id = r_out.property_id
WHERE r_out.status = 'confirmed'
  AND r_in.status  = 'confirmed'
  AND r_out.checkout_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
ORDER BY r_out.checkout_date ASC;
```

**Sample Pascal response:**
> **3 same-day turnovers found this week. 1 has no clean task scheduled.**
>
> **⚠️ Risk — Tuesday June 23:**
> **1039 Louisa St (5BR)** — Previous guest Kenneth Franklin checks out at 11 AM. New guest arrives at 3 PM (2 guests). No housekeeping task exists for Tuesday. 4-hour window for a 5-bedroom property.
>
> **✓ Covered:**
> - 5605 Tchoupitoulas — Maria Santos assigned, 3-hour task scheduled for checkout day
> - 910 Jefferson — James Williams assigned
>
> **Recommended action:** Create a housekeeping task for 1039 Louisa immediately and assign before end of day.

---

### Q10 — What is the data quality score for each property, and which properties are most incomplete?

**Readiness:** MVP

**Why David asks it:**  
Operational failures often trace back to missing data — no door code, no WiFi, no parking instructions. The `dq_completeness_score` computed at sync (0–100 across 10 critical fields, as defined in `listing_field_inventory.md`) tells David where the knowledge base has gaps before those gaps cause guest calls.

**Required data sources:**  
`properties`

**SQL:**
```sql
SELECT
  internal_name,
  street,
  bedrooms,
  dq_completeness_score,
  dq_has_structured_wifi,
  dq_has_structured_door_code,
  dq_has_parking_details,
  dq_has_additional_checkin,
  dq_has_unit_notes,
  str_license_expired,
  review_rating,
  (
    CASE WHEN NOT dq_has_structured_wifi       THEN 'wifi ' ELSE '' END ||
    CASE WHEN NOT dq_has_structured_door_code  THEN 'door_code ' ELSE '' END ||
    CASE WHEN NOT dq_has_parking_details       THEN 'parking ' ELSE '' END ||
    CASE WHEN NOT dq_has_additional_checkin    THEN 'checkin_notes ' ELSE '' END ||
    CASE WHEN NOT dq_has_unit_notes            THEN 'unit_notes ' ELSE '' END
  ) AS missing_fields
FROM properties
ORDER BY dq_completeness_score ASC, review_rating DESC;
```

**Sample Pascal response:**
> **Portfolio data quality: average score 52/100.**
>
> The most common gaps across all 100 properties:
> - **WiFi not structured:** 91 properties
> - **Door code not structured:** 99 properties
> - **Parking details missing:** 98 properties
>
> **Lowest-scoring properties (most likely to cause guest calls):**
> | Property | Score | Missing |
> |---|---|---|
> | [Property A] | 20/100 | WiFi, door code, parking, checkin notes, unit notes |
> | [Property B] | 30/100 | WiFi, door code, parking, checkin notes |
>
> **Note:** No property scored below 50 despite these gaps — because `access_instructions` (100% populated) and other fields carry the score. The structured field gap is a data entry problem, not a missing-data emergency. But it does mean guest comms requires manual lookup for 91% of properties.

---

### Q11 — Which properties have open maintenance tasks that are unassigned?

**Readiness:** Requires Breezeway

**Why David asks it:**  
An unassigned maintenance task is a task that no one is responsible for. If it's near an arrival, it becomes critical. If it's a safety issue (handrails, HVAC, plumbing), it's a liability regardless of timing.

**Required data sources:**  
`tasks`, `task_assignments`, `properties`

**SQL:**
```sql
SELECT
  p.internal_name,
  p.street,
  t.task_name,
  t.priority,
  t.scheduled_date,
  t.due_date,
  t.description,
  t.is_overdue,
  (SELECT r.checkin_date FROM reservations r
   WHERE r.property_id = p.id
     AND r.status = 'confirmed'
     AND r.checkin_date >= CURRENT_DATE
   ORDER BY r.checkin_date ASC
   LIMIT 1) AS next_arrival
FROM tasks t
JOIN properties p ON p.id = t.property_id
WHERE t.department  = 'maintenance'
  AND t.status      NOT IN ('completed', 'approved', 'closed')
  AND t.deleted_at  IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM task_assignments ta WHERE ta.task_id = t.id
  )
ORDER BY t.priority ASC, t.scheduled_date ASC;
```

**Sample Pascal response:**
> **2 unassigned maintenance tasks found.**
>
> **🔴 Loose handrail on front steps — [Property X]**
> Priority: Urgent · Scheduled: Tomorrow · Unassigned
> Comment: *"Three screws stripped. Needs full replacement not patch."* — Kevin Park, 30 min ago
> Next guest arrival: Tomorrow. This is a safety liability. Assign Robert Chen immediately.
>
> **🟡 HVAC not cooling — [Property Y]**
> Priority: Urgent · Overdue by 1 day · Unassigned
> Comment: *"Compressor dead. Part CR-4400B ordered, ETA 3 business days."* — Robert Chen
> Next guest arrival: 5 days. Monitor part delivery; if delayed, consider temporary unit reassignment.

---

### Q12 — What recurring maintenance issues exist across the portfolio?

**Readiness:** Future (requires `recurring_issues` table + 30+ days of task history)

**Why David asks it:**  
One HVAC failure is a maintenance event. Three HVAC failures at the same property in 60 days is a capital investment decision. The `recurring_issues` table (defined in `bem_ops_database_schema.md` Phase 2) is designed to surface exactly this pattern. This is the "Recurring Issues" section of the Thursday call.

**Required data sources:**  
`recurring_issues`, `properties`, `tasks`

**SQL:**
```sql
SELECT
  p.internal_name,
  ri.issue_category,
  ri.title,
  ri.occurrence_count,
  ri.first_seen_at,
  ri.last_seen_at,
  ri.severity,
  ri.window_days,
  ri.description
FROM recurring_issues ri
JOIN properties p ON p.id = ri.property_id
WHERE ri.is_active = TRUE
ORDER BY ri.severity DESC, ri.occurrence_count DESC, ri.last_seen_at DESC;
```

**Sample Pascal response:**
> *(Available after 30 days of Breezeway task history)*
>
> **3 recurring issues identified this month:**
>
> **HVAC failures at 1039 Louisa St — 3 occurrences in 45 days**
> The unit's 2nd-floor HVAC has failed three times since May. Each repair is temporary. This suggests the compressor is at end-of-life. Estimated replacement cost: $3,200. Continued repair cost at current rate: ~$900/month. Recommend owner conversation about replacement before summer peak.
>
> **Late cleans at 6622 Urquhart — 4 occurrences in 30 days**
> Housekeeping tasks at this property consistently start 1–2 hours after scheduled time. All 4 were assigned to Maria Santos. Either the schedule is unrealistic for this property's size, or there's a recurring conflict with her other assignments.

---

### Q13 — Which guests are arriving today and what do we know about each property's readiness?

**Readiness:** Requires Breezeway

**Why David asks it:**  
David needs a daily arrival sheet that goes beyond a guest list — it includes the operational readiness of each property: clean status, access code, open tasks, and any active risks. This is the morning briefing Pascal was built for.

**Required data sources:**  
`reservations`, `properties`, `tasks`, `operational_risks`

**SQL:**
```sql
SELECT
  p.internal_name,
  r.guest_name,
  r.guest_count,
  r.channel,
  r.checkin_date,
  p.checkin_time_start,
  r.guest_access_code,
  p.cleanliness_status,
  p.wifi_network,
  p.wifi_password,
  p.door_code,
  (SELECT COUNT(*) FROM tasks t
   WHERE t.property_id = p.id
     AND t.department  = 'housekeeping'
     AND t.scheduled_date = CURRENT_DATE
     AND t.status IN ('completed', 'approved')) AS completed_cleans,
  (SELECT COUNT(*) FROM tasks t
   WHERE t.property_id = p.id
     AND t.status NOT IN ('completed', 'approved', 'closed')
     AND t.deleted_at IS NULL)                 AS open_tasks,
  (SELECT MAX(o.severity) FROM operational_risks o
   WHERE o.reservation_id = r.id
     AND o.is_active = TRUE)                   AS risk_level
FROM reservations r
JOIN properties p ON p.id = r.property_id
WHERE r.checkin_date = CURRENT_DATE
  AND r.status       = 'confirmed'
ORDER BY p.checkin_time_start ASC, p.internal_name ASC;
```

**Sample Pascal response:**
> **Today's arrivals — Thursday June 18 — 6 check-ins**
>
> | Property | Guest | Guests | Channel | Check-in | Clean ✓ | Code ✓ | Risk |
> |---|---|---|---|---|---|---|---|
> | 334 Carondelet | Seth Cohen | 2 | Airbnb | 3 PM | ❌ | ❌ | 🔴 Critical |
> | 6622 Urquhart | Miriam Lawrence | 3 | Airbnb | 3 PM | ❌ | ❌ | 🔴 Critical |
> | 5605 Tchoupitoulas | Anna M. | 2 | Direct | 4 PM | ✅ | ✅ | ✅ Clear |
> | 910 Jefferson | Luke Cree | 4 | VRBO | 3 PM | ✅ | ❌ | 🟡 High |
>
> **2 properties require immediate action.** Carondelet and Urquhart both have open cleans and no access code. All other arrivals are clear or need access code only.

---

### Q14 — What should be on the Thursday call agenda this week?

**Readiness:** MVP

**Why David asks it:**  
The Thursday call is the ops team's weekly leadership review. The `thursday_call_items` table auto-generates this agenda from the risk engine, but Pascal can synthesize it into a structured narrative — turning 46 data rows into a 5-minute briefing David can open the call with.

**Required data sources:**  
`thursday_call_items`, `properties`, `reservations`, `operational_risks`

**SQL:**
```sql
SELECT
  tc.category,
  tc.priority,
  tc.title,
  tc.summary,
  tc.recommendation,
  tc.status,
  tc.source,
  p.internal_name AS property_name,
  r.checkin_date,
  r.guest_name
FROM thursday_call_items tc
LEFT JOIN properties   p ON p.id = tc.property_id
LEFT JOIN reservations r ON r.id = tc.reservation_id
WHERE tc.call_date = CURRENT_DATE + ((4 - EXTRACT(DOW FROM CURRENT_DATE)::INTEGER + 7) % 7)
ORDER BY tc.priority ASC, tc.category ASC;
```

**Sample Pascal response:**
> **Thursday Call Agenda — June 19, 2026**
> *46 items auto-generated. Recommended focus: 8 items.*
>
> **🔴 Open Before Friday (Critical)**
> 1. 15 properties have arrivals this week with no completed clean — housekeeping coverage gaps
> 2. 27 reservations have no guest access code — send codes today for all arrivals within 72 hours
>
> **🟡 Discuss Thursday (High)**
> 3. 5 expired STR licenses — Louisa and Jefferson are the most overdue; owner notification needed
> 4. Loose handrail safety hazard (unassigned) — assign Robert Chen before next arrival
> 5. HVAC at [Property Y] — part delayed, guest arrives in 5 days
>
> **🔵 Carry or Assign**
> 6. WiFi data entry sprint — 91 properties need structured credentials
> 7. Maria Santos workload — 2 arrival-blocking tasks, check capacity
> 8. Recurring maintenance at 1039 Louisa — owner conversation needed

---

### Q15 — Which properties have guests arriving with special requests or notes?

**Readiness:** MVP

**Why David asks it:**  
Guest notes in Hostaway often contain information that changes what Operations needs to prepare: late arrivals, early check-outs, pets, accessibility needs, or direct requests. Communications and Ops both need this surface before the guest arrives.

**Required data sources:**  
`reservations`, `properties`

**SQL:**
```sql
SELECT
  p.internal_name,
  r.guest_name,
  r.guest_count,
  r.checkin_date,
  r.channel,
  r.reservation_notes,
  r.special_requests,
  p.pets_allowed,
  p.checkin_time_start,
  p.checkin_time_end,
  p.max_guests
FROM reservations r
JOIN properties p ON p.id = r.property_id
WHERE r.checkin_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
  AND r.status        = 'confirmed'
  AND (
    r.reservation_notes IS NOT NULL
    OR r.special_requests IS NOT NULL
    OR r.guest_count > p.max_guests
  )
ORDER BY r.checkin_date ASC;
```

**Sample Pascal response:**
> **4 upcoming reservations have notes that require ops review:**
>
> **334 Carondelet — Seth Cohen (arriving today)**
> Guest note: *"We'll be arriving around midnight — is that okay?"*
> → Standard check-in is 3 PM–anytime. Confirm access code is set. No action needed beyond ensuring the code is sent.
>
> **2821 Palmyra — Melissa Bundy (tomorrow, 3 guests)**
> Special request: *"We're celebrating an anniversary. Any chance of a welcome note?"*
> → Forward to Communications for a handwritten note or welcome message. Low effort, high impact.
>
> **1039 Louisa — Kenneth Franklin (4 guests, 5BR)**
> Guest count 4 in a 5BR property — within max capacity, but high turnover complexity.

---

### Q16 — Which housekeepers have the fastest average clean times, and which properties take the longest?

**Readiness:** Requires Breezeway

**Why David asks it:**  
When same-day turnovers are at risk or a housekeeper calls out, David needs to know who to call first and how long each assignment will realistically take. This also surfaces which properties are consistently underestimated on cleaning time — a scheduling fix, not a staff fix.

**Required data sources:**  
`tasks`, `task_assignments`, `people`, `properties`

**SQL:**
```sql
-- By housekeeper
SELECT
  pe.full_name,
  COUNT(t.id)                        AS completed_cleans,
  ROUND(AVG(t.actual_hours), 2)      AS avg_actual_hours,
  ROUND(AVG(t.estimated_hours), 2)   AS avg_estimated_hours,
  ROUND(AVG(t.actual_hours - t.estimated_hours), 2) AS avg_over_under
FROM tasks t
JOIN task_assignments ta ON ta.task_id = t.id
JOIN people pe           ON pe.id = ta.person_id
WHERE t.department    = 'housekeeping'
  AND t.status        IN ('completed', 'approved')
  AND t.actual_hours  IS NOT NULL
  AND t.deleted_at    IS NULL
GROUP BY pe.full_name
ORDER BY avg_actual_hours ASC;
```

**Sample Pascal response:**
> *(Available after Breezeway connection with completed task history)*
>
> **Housekeeper performance — last 30 days:**
>
> | Housekeeper | Cleans | Avg Time | Est. vs Actual |
> |---|---|---|---|
> | Maria Santos | 24 | 2.1h | −0.2h (faster) |
> | James Williams | 19 | 2.4h | +0.1h (accurate) |
>
> **Properties consistently running over estimate:**
> - 1039 Louisa (5BR) — estimated 4h, actual avg 5.2h — adjust schedule to 5.5h buffer
> - 3042 St Claude — estimated 2h, actual avg 2.8h — add 1 hour to all future estimates

---

### Q17 — What is the inspection pass rate before guest arrivals?

**Readiness:** Future (requires `task_requirements` + Breezeway checklist data)

**Why David asks it:**  
An inspection that passes on the first attempt is an efficient operation. An inspection that fails (items rejected, photos required, re-inspection needed) signals a housekeeper or a property that consistently underdelivers. This question requires Breezeway checklist data via `task_requirements`.

**Required data sources:**  
`tasks`, `task_requirements`, `task_assignments`, `people`, `properties`

**SQL:**
```sql
-- Requires task_requirements table (Phase 2)
SELECT
  pe.full_name                                        AS inspector,
  COUNT(DISTINCT t.id)                                AS total_inspections,
  COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'approved') AS passed,
  COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'closed')   AS rejected,
  ROUND(
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'approved')::NUMERIC /
    NULLIF(COUNT(DISTINCT t.id), 0) * 100, 1
  )                                                   AS pass_rate_pct
FROM tasks t
JOIN task_assignments ta ON ta.task_id = t.id
JOIN people pe           ON pe.id = ta.person_id
WHERE t.department = 'inspection'
  AND t.deleted_at IS NULL
GROUP BY pe.full_name
ORDER BY pass_rate_pct ASC;
```

**Sample Pascal response:**
> *(Available after Breezeway connection with inspection checklist data)*
>
> **Inspection pass rate — last 30 days:**
> Diana Torres: 87% pass rate across 31 inspections.
> 4 rejections — all at 3-bedroom properties. Common failure items: refrigerator interior, bathroom grout.
>
> **Recommended action:** Add refrigerator interior to Maria Santos's cleaning checklist for 3BR properties. The failure pattern suggests a scope gap, not a performance issue.

---

### Q18 — Which properties have the lowest review ratings and active operational risks?

**Readiness:** MVP

**Why David asks it:**  
Low-rated properties with active risks are the most likely to generate the next bad review. This cross-reference tells David where a proactive intervention is most likely to change a trajectory — not just fix today's problem, but prevent next week's review.

**Required data sources:**  
`properties`, `operational_risks`, `reservations`

**SQL:**
```sql
SELECT
  p.internal_name,
  p.street,
  p.bedrooms,
  p.review_rating,
  COUNT(o.id) FILTER (WHERE o.is_active = TRUE)         AS active_risks,
  MAX(o.severity)                                        AS highest_severity,
  STRING_AGG(DISTINCT o.risk_type, ', ')                 AS risk_types,
  (SELECT r.checkin_date FROM reservations r
   WHERE r.property_id = p.id
     AND r.status = 'confirmed'
     AND r.checkin_date >= CURRENT_DATE
   ORDER BY r.checkin_date ASC LIMIT 1)                  AS next_arrival
FROM properties p
LEFT JOIN operational_risks o ON o.property_id = p.id
WHERE p.review_rating < 9.0
   OR EXISTS (
     SELECT 1 FROM operational_risks o2
     WHERE o2.property_id = p.id AND o2.is_active = TRUE
   )
GROUP BY p.internal_name, p.street, p.bedrooms, p.review_rating
ORDER BY active_risks DESC, p.review_rating ASC NULLS LAST;
```

**Sample Pascal response:**
> **Properties combining low ratings with active risks — highest intervention priority:**
>
> | Property | Rating | Active Risks | Next Arrival | Focus |
> |---|---|---|---|---|
> | [Property A] | 8.4 | 3 | Tomorrow | Clean + access code + WiFi |
> | [Property B] | 8.7 | 2 | This weekend | Access code + expired license |
>
> These properties are on a trajectory toward further rating decline. Recommend a full property walkthrough before the next arrival, not just task completion.

---

### Q19 — What does a guest need to know to check in successfully at [property]?

**Readiness:** MVP

**Why David asks it:**  
This is the most common question Communications asks Operations. Currently it requires opening Hostaway, finding the listing, reading the `airbnbAccess` field, and interpreting free-text prose. Pascal can assemble a structured check-in brief from the properties table in seconds — and flag if anything critical is missing.

**Required data sources:**  
`properties`, `reservations`

**SQL:**
```sql
SELECT
  p.internal_name,
  p.street,
  p.city,
  p.checkin_time_start,
  p.checkin_time_end,
  p.checkout_time,
  p.access_instructions,
  p.door_code,
  p.door_code_source,
  p.additional_checkin,
  p.wifi_network,
  p.wifi_password,
  p.wifi_password_source,
  p.parking_type,
  p.parking_details,
  p.house_rules,
  p.unit_specific_notes,
  p.contact_phone
FROM properties p
WHERE p.internal_name ILIKE '%:property_name%'
   OR p.street        ILIKE '%:property_name%';
```

**Sample Pascal response:**
> **Check-in brief — 334 Carondelet St (Carondelet 3/2)**
>
> **Check-in:** 3 PM (flexible end time)  **Check-out:** 11 AM
>
> **Entry:** Keypad lock on front door. Code is embedded in access instructions — not in a structured field. Extracted: likely `1234*` (confirm before sending to guest).
>
> **WiFi:** Not in structured record. Retrieve from access instructions before guest message.
>
> **Parking:** Street parking available. Guest advisory in access instructions re: window visibility.
>
> **House rules:** No parties, no smoking, no shoes indoors. Quiet hours after 10 PM.
>
> **⚠️ Missing:** No structured door code. No structured WiFi. Guest must receive both from Communications before 3 PM today.

---

### Q20 — What operational improvements would have the biggest impact on guest satisfaction across the portfolio?

**Readiness:** Future (requires recurring_issues + review history + task pattern analysis)

**Why David asks it:**  
This is the Thursday call's strategic question — not "what's wrong today" but "what systemic changes would prevent the most failures over the next 90 days." It's Pascal's highest-value insight type: synthesizing patterns across properties, staff, tasks, and reviews into prioritized recommendations.

**Required data sources:**  
`properties`, `tasks`, `operational_risks`, `recurring_issues` (Phase 2), `reservations`

**SQL:**
```sql
-- Proxy query available today using operational_risks patterns
SELECT
  risk_type,
  COUNT(*)                  AS total_occurrences,
  COUNT(DISTINCT property_id) AS properties_affected,
  AVG(hours_until_checkin)  AS avg_hours_until_checkin,
  MODE() WITHIN GROUP (ORDER BY severity) AS typical_severity
FROM operational_risks
WHERE is_active = TRUE
GROUP BY risk_type
ORDER BY total_occurrences DESC;
```

**Sample Pascal response:**
> *(Full version available after 60+ days of pattern history)*
>
> **Top 3 systemic improvements — estimated guest impact:**
>
> **1. Structured WiFi and door code data entry**
> 91 properties have no structured WiFi. Each gap is a potential guest call or negative review mention. A 4-hour data entry sprint by one ops coordinator would eliminate the risk for the top 30 properties by booking frequency. Cost: ~4 staff hours. Impact: eliminates the most common guest communication failure.
>
> **2. Access code send process**
> 27 reservations currently have no access code set, including arrivals today. This is a process gap, not a data gap. Recommend a daily automated check: any confirmed reservation arriving within 48 hours with no `guest_access_code` triggers a task in Hostaway for Communications.
>
> **3. Same-day turnover scheduling buffer**
> Properties with same-day turnovers consistently show higher clean failure rates. Adding a 30-minute buffer to estimated clean time on turnover days, and flagging them for inspection priority, would reduce arrival failures without adding headcount.

---

## Implementation Notes

### Pascal V1 activation checklist
- [ ] `pascal_insights` table is ready (schema deployed)
- [ ] `pascal_conversations` table is ready (schema deployed)
- [ ] Claude API key configured in environment
- [ ] Prompt templates written for each `pascal_insight_type`
- [ ] Context assembly functions written for each question category
- [ ] Output stored in `pascal_insights` after every generation
- [ ] Feedback mechanism (thumbs up/down) wired to `pascal_insights.feedback`

### MVP questions (available today without Breezeway)
Q1, Q2, Q6, Q7, Q10, Q13 (partial), Q14, Q15, Q18, Q19

### Requires real Breezeway connection
Q3, Q4, Q5, Q8, Q9, Q11, Q13 (full), Q16

### Requires Phase 2 tables (`recurring_issues`, `task_requirements`)
Q12, Q17, Q20

### Context assembly approach
Each Pascal question should assemble its context by running the SQL above, formatting the results as structured text, and prepending a system prompt that includes:
1. BEM company context (New Orleans STR operator, 100 properties, Breezeway + Hostaway)
2. The specific operational question being answered
3. The time-sensitive data (today's date, upcoming arrivals, open risks)
4. An instruction to be direct, specific, and action-oriented — not generic

Pascal does not ask clarifying questions. It gives the best answer possible with available data and flags what's missing.
