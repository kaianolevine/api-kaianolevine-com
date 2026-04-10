ALTER TABLE pipeline_evaluations
  ADD COLUMN IF NOT EXISTS violation_id TEXT;
