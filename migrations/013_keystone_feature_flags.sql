-- Migration 013: Project Keystone auth transition flags
--
-- These flags gate the dual-auth bridge for the Clerk M2M JWT upgrade (Project Keystone).
-- Both default to FALSE — legacy X-Owner-Id auth remains active until explicitly enabled.
--
-- flags.keystone.legacy_auth_enabled
--   TRUE  → X-Owner-Id header auth is accepted (current behaviour)
--   FALSE → X-Owner-Id is rejected; only Clerk JWT is accepted
--   During transition: keep TRUE. Flip to FALSE once all cogs are migrated.
--
-- flags.keystone.clerk_auth_enabled
--   TRUE  → Clerk JWT verification is active (validates RS256 token, extracts sub as owner_id)
--   FALSE → Clerk JWT is not checked (current behaviour)
--   During transition: flip to TRUE first, verify cogs work, then disable legacy.

INSERT INTO feature_flags (id, owner_id, name, enabled, description)
VALUES
  (
    gen_random_uuid(),
    'kaiano',
    'flags.keystone.legacy_auth_enabled',
    TRUE,
    'Keystone: legacy mode'
  ),
  (
    gen_random_uuid(),
    'kaiano',
    'flags.keystone.clerk_auth_enabled',
    FALSE,
    'Keystone: v1 mode'
  );