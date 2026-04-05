-- Migration 011: Add structured metadata columns to wcs_notes
ALTER TABLE wcs_notes ADD COLUMN instructors  TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE wcs_notes ADD COLUMN students     TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE wcs_notes ADD COLUMN organization TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_wcs_notes_instructors ON wcs_notes USING GIN (instructors);
