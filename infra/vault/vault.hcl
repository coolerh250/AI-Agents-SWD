# AT-M3.6B.2 readiness -- non-production Vault server config for the internal test runtime.
#
# WHY THIS FILE EXISTS. The test runtime ran `vault server -dev`, whose storage is in memory: every
# restart discarded every secret and minted a new root token. That is fine for exercising a code
# path and useless for holding a credential an operator provisioned by hand, which is exactly what
# AT-M3.6B.2 will need. This is the minimum persistent replacement -- one server, one file storage
# backend, one listener -- and nothing else. No auto-unseal, no HA, no Raft cluster, no secret
# management platform: those are production architecture and this is a non-production readiness
# slice.
#
# NON-PRODUCTION LIMITATIONS, STATED RATHER THAN IMPLIED:
#
#   * TLS is disabled. The listener is reachable only from inside the compose network and from the
#     host's own loopback interface; it is never published publicly. A real deployment terminates
#     TLS here, and this file would be wrong for one.
#   * `file` storage is single-node and unreplicated. Losing the volume loses the contents. That is
#     acceptable for a non-production runtime holding one non-production credential, and it is the
#     reason the operator keeps the bootstrap material outside the volume.
#   * Unsealing is MANUAL. Vault starts sealed after every restart and stays sealed until an
#     operator unseals it. Auto-unseal needs a cloud KMS or a transit seal, neither of which exists
#     in this project, and inventing one would be a bigger change than this slice is for. See
#     docs/operations/at-m3-6b-2-vault-runtime-readiness-runbook.md.

ui = false

# Persistent, and deliberately on a mounted volume rather than the container filesystem: a
# container is recreated on every `docker compose up`, and storage that dies with it would be dev
# mode wearing a different name.
storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

# Advertised to clients inside the compose network. The service name, never a host address.
api_addr = "http://vault:8200"

# mlock keeps Vault's memory out of swap. The compose service grants IPC_LOCK so this works; it is
# left ENABLED on purpose -- disabling it is the usual shortcut and it puts unsealed key material
# on disk the moment the host swaps.
disable_mlock = false
