-- Migration 016: WCS access control (profiles, note grants, default visibility)

CREATE TABLE wcs_user_profiles (
  user_id       TEXT PRIMARY KEY,
  email         TEXT NOT NULL DEFAULT '',
  display_name  TEXT NOT NULL DEFAULT '',
  is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE wcs_note_grants (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     TEXT NOT NULL REFERENCES wcs_user_profiles(user_id) ON DELETE CASCADE,
  note_id     UUID NOT NULL REFERENCES wcs_notes(id) ON DELETE CASCADE,
  granted_by  TEXT NOT NULL,
  granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, note_id)
);

CREATE INDEX idx_wcs_note_grants_user_id ON wcs_note_grants(user_id);
CREATE INDEX idx_wcs_note_grants_note_id ON wcs_note_grants(note_id);

ALTER TABLE wcs_notes
  ADD COLUMN is_default_visible BOOLEAN NOT NULL DEFAULT FALSE;
