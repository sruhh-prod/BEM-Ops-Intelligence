-- =============================================================================
-- Migration 001: Alter schema for MVP adapter pattern
-- Run this in Supabase SQL Editor BEFORE running the sync pipeline.
-- =============================================================================
-- Why: properties synced from Hostaway do not yet have a breezeway_id.
-- The column was defined NOT NULL for the future state (Breezeway primary).
-- This migration makes it nullable so Hostaway-only data can be loaded now.
-- When the real Breezeway adapter ships, breezeway_id is populated via update.
-- =============================================================================

ALTER TABLE properties ALTER COLUMN breezeway_id DROP NOT NULL;

-- Allow the risk engine to upsert tasks.is_stale and tasks.blocks_arrival
-- without touching Breezeway-owned fields.
-- (No structural change needed — these columns already exist.)

-- Confirm
DO $$
BEGIN
  RAISE NOTICE 'Migration 001 complete: breezeway_id is now nullable on properties.';
END;
$$;
