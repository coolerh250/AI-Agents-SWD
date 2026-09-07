# AT-M3.6B.2 readiness -- the ONLY policy the application runtime is given.
#
# The runtime reads one secret and does nothing else to Vault. This policy says exactly that, so
# the restriction is enforced by Vault rather than by the application remembering to behave.
#
# WHAT THE RUNTIME ACTUALLY DOES. `VaultKvSecretProvider._load_kv()` issues ONE request:
#
#     GET ${VAULT_ADDR}/v1/${VAULT_KV_MOUNT}/data/${VAULT_KV_PATH}
#       -> GET http://vault:8200/v1/secret/data/aiagents/test-runtime
#
# and pulls `ANTHROPIC_API_KEY` out of `data.data`. It never writes, never lists, never reads
# metadata and never touches a second path. One capability on one path is therefore the whole
# requirement, and anything more would be privilege the runtime has no use for.

# The one secret. `read` only -- not `create`, `update`, `patch`, `delete`, `list` or `sudo`.
path "secret/data/aiagents/test-runtime" {
  capabilities = ["read"]
}

# NOT GRANTED, and each omission is deliberate rather than accidental:
#
#   secret/metadata/aiagents/test-runtime
#       The provider never requests metadata. The operator's names-only verification does use
#       `vault kv metadata get`, but that is an OPERATOR action run with the OPERATOR's own
#       credential -- see section 9 of the authorization record. Granting it here would widen the
#       runtime token to make a human's command convenient, which is how least privilege erodes.
#
#   secret/destroy/*, secret/undelete/*, secret/delete/*
#       A read-only consumer cannot destroy the credential it reads, even by accident, and cannot
#       be used to destroy anyone else's.
#
#   sys/*, auth/*, identity/*
#       No policy management, no auth-method management, no token creation. A leaked runtime token
#       cannot mint another token, cannot widen itself, and cannot read what it was scoped away
#       from.
#
#   secret/data/* (any wildcard)
#       The path is exact. A wildcard would silently grant every future secret written under the
#       mount to a token that exists to read exactly one.
#
# A note for whoever runs `vault kv get` with this token and finds it fails: that is expected and
# is not a defect. The KV v2 CLI helper first calls `sys/internal/ui/mounts/secret` to discover the
# mount version, which this policy does not allow. The PROVIDER does not use the CLI -- it calls
# the v2 data path directly -- so the scope is drawn around what the runtime needs, not around what
# a human's convenience command needs. Verify with `vault read secret/data/aiagents/test-runtime`,
# which is the same request the runtime makes.
