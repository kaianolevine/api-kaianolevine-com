-- Migration 027: the notifier role
--
-- POST /v1/notify sends a message to the ecosystem's Discord channel and does
-- nothing else, so it gets a scope and a role of its own rather than being
-- folded into one of the existing bundles. The alternative — letting, say,
-- catalog-ingest imply "and may also post to Discord" — is how a role stops
-- describing anything and a key ends up able to do more than its name says.
--
-- The role is granted to the declared machine ops-notifier by
-- identity_registry.reconcile at boot. Nothing is granted here.

INSERT INTO identity_roles (name, description) VALUES
  ('notifier', 'May send ad-hoc notifications to the ecosystem Discord channel.')
ON CONFLICT (name) DO NOTHING;

INSERT INTO identity_role_scopes (role_name, scope) VALUES
  ('notifier', 'notify.messages.send')
ON CONFLICT (role_name, scope) DO NOTHING;
