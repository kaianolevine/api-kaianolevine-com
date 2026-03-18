-- Reference SQL schema for the initial release.
-- This repository uses SQLAlchemy async ORM (no automatic runtime migrations included).

-- Enable UUID generation.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id TEXT NOT NULL,
  set_date DATE NOT NULL,
  venue TEXT NOT NULL,
  source_file TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS track_catalog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id TEXT NOT NULL,

  title TEXT NOT NULL,
  title_normalized TEXT NOT NULL,
  artist TEXT NOT NULL,
  artist_normalized TEXT NOT NULL,

  source TEXT NOT NULL,
  confidence TEXT NOT NULL,

  genre TEXT,
  bpm DOUBLE PRECISION,
  release_year INTEGER,

  play_count INTEGER NOT NULL DEFAULT 1,
  first_played DATE,
  last_played DATE,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_track_catalog_owner_norm_title_artist UNIQUE (owner_id, title_normalized, artist_normalized)
);

CREATE TABLE IF NOT EXISTS tracks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id TEXT NOT NULL,

  set_id UUID NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
  catalog_id UUID REFERENCES track_catalog(id) ON DELETE SET NULL,

  play_order INTEGER,
  play_time TIME,

  title TEXT NOT NULL,
  artist TEXT NOT NULL,

  genre TEXT,
  bpm DOUBLE PRECISION,
  release_year INTEGER,
  length_secs INTEGER,

  data_quality TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tracks_set_id ON tracks(set_id);
CREATE INDEX IF NOT EXISTS ix_tracks_catalog_id ON tracks(catalog_id);

CREATE TABLE IF NOT EXISTS pipeline_evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id TEXT NOT NULL,

  repo TEXT NOT NULL,
  dimension TEXT NOT NULL,
  severity TEXT NOT NULL,
  details TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pipeline_evaluations_repo ON pipeline_evaluations(repo);
CREATE INDEX IF NOT EXISTS ix_pipeline_evaluations_dimension ON pipeline_evaluations(dimension);
CREATE INDEX IF NOT EXISTS ix_pipeline_evaluations_severity ON pipeline_evaluations(severity);

