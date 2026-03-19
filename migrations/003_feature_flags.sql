CREATE TABLE IF NOT EXISTS feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id TEXT NOT NULL,
  name TEXT NOT NULL UNIQUE,
  enabled BOOLEAN NOT NULL DEFAULT false,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO feature_flags (owner_id, name, enabled, description)
VALUES
  ('dev-owner', 'flags.deejay_api.ai_evaluation_enabled', true,
   'Enable AI pipeline evaluation findings storage'),
  ('dev-owner', 'flags.deejay_api.public_catalog_enabled', true,
   'Enable public catalog endpoints'),
  ('dev-owner', 'flags.deejay_api.ingest_enabled', true,
   'Enable the ingest endpoint for pipeline writes')
ON CONFLICT (name) DO NOTHING;

