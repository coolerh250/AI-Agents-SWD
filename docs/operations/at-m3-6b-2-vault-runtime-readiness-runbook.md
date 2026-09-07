# AT-M3.6B.2 — Vault runtime readiness runbook (operator)

> **Non-production only. No production action. This runbook contains NO secret and produces no
> output that should be pasted anywhere. Every command below is run by a human operator in their
> own SSH session, never by an AI assistant and never by CI.**

## Why this is a manual runbook

Initializing a Vault server produces two things that must never enter a repository, a chat
transcript, a log or a test fixture: the **unseal/recovery key shares** and the **initial root
token**. An assistant that ran `vault operator init` would render both into its own conversation,
and no amount of care afterwards un-renders them. So the boundary is drawn before initialization:
everything that can be prepared as configuration has been prepared and committed, and the three
steps that mint secrets are yours.

This is a checkpoint, not a failure. It is the expected shape of a secure bootstrap.

## What is already done for you

| Prepared | Where |
| --- | --- |
| Persistent, non-dev Vault server config (file storage, no TLS, internal only) | `infra/vault/vault.hcl` |
| Least-privilege read-only runtime policy | `infra/vault/policies/aiagents-runtime-read.hcl` |
| Compose service with a persistent volume and a loopback-only port | `infra/docker-compose/docker-compose.yml` |
| Runtime wiring — provider, mount, path, model, gate | same compose file, `orchestrator` service |
| Env template | `infra/runtime/env.test-runtime.example` |
| Readiness assertions | `python scripts/validate_runtime_config.py --mode test-runtime` |

## The canonical coordinates

```text
mount   secret
path    aiagents/test-runtime          (NOT aiagents/staging)
field   ANTHROPIC_API_KEY
policy  aiagents-runtime-read
```

`ANTHROPIC_API_KEY` is **one field inside** the KV v2 secret at that path — not a path of its own.
That single fact drives step 5 and the later real-key procedure: `vault kv put` replaces the whole
secret and would delete every other field stored there, so writes use `patch`.

---

## Step 1 — start the persistent Vault

```bash
cd ~/AI-Agents-SWD/infra/docker-compose
docker compose up -d vault
docker compose exec vault vault status || true
```

Expect `Initialized false`, `Sealed true`. That is correct for a Vault that has never been
initialized, and `vault status` exits non-zero when sealed — hence the `|| true`.

## Step 2 — initialize (produces secrets — operator only)

```bash
docker compose exec vault vault operator init -key-shares=1 -key-threshold=1
```

The output contains one **unseal key** and one **initial root token**.

- Write them into your own password manager or an encrypted file **outside** this repository and
  outside any AI conversation.
- Do not paste them into chat, a ticket, a commit, a comment or a report.
- Do not store them on the Vault volume — a backup of the volume would then contain its own key.

`-key-shares=1` is chosen deliberately for a non-production single-operator runtime: Shamir
splitting across five shares protects against a single custodian, which is not the threat model
here, and it would make every restart a five-part ceremony. A production deployment would not use
these numbers.

## Step 3 — unseal

```bash
docker compose exec vault vault operator unseal          # prompts; input is not echoed
docker compose exec vault vault status
```

Expect `Initialized true`, `Sealed false`.

**Vault re-seals on every restart.** There is no auto-unseal in this project — it needs a cloud KMS
or a transit seal, and inventing one is a bigger change than a readiness slice should make. So
after any `docker compose restart vault`, host reboot or container recreation, repeat this step.
Until you do, `VaultKvSecretProvider` reports every secret as absent and the reasoning adapter fails
closed. Nothing crashes; nothing silently degrades to a different secret source either.

## Step 4 — load the policy and mint the runtime token (produces a secret — operator only)

```bash
export VAULT_TOKEN=<your root token>     # this shell only; step 6 clears it

# The policy file is already mounted into the container, read-only.
docker compose exec -e VAULT_TOKEN vault \
  vault policy write aiagents-runtime-read /vault/policies/aiagents-runtime-read.hcl

docker compose exec -e VAULT_TOKEN vault vault policy read aiagents-runtime-read

# The RUNTIME token. Read-only, scoped to one secret, renewable, no default policy.
docker compose exec -e VAULT_TOKEN vault \
  vault token create -policy=aiagents-runtime-read -no-default-policy -period=768h -field=token
```

The last command prints **one value: the runtime token**. Treat it as a secret:

- put it in your gitignored env file as `VAULT_TOKEN=…`,
- never commit it, never paste it into chat, never echo it in a log,
- and note that it is *not* the root token — the root token is never given to a service.

`-no-default-policy` matters: Vault's `default` policy grants a token the ability to look itself up,
renew itself and — depending on version — reach a handful of `sys/` and `cubbyhole` paths. The
runtime needs none of that, and omitting it keeps the grant to exactly the one line in the policy
file.

## Step 5 — create the secret with the readiness placeholder

The real Anthropic key is **not** provisioned in this slice. Create the path with the repository's
non-secret sentinel so the field name exists and the rail can be verified end to end:

```bash
docker compose exec -e VAULT_TOKEN vault \
  vault kv put -mount=secret aiagents/test-runtime \
  ANTHROPIC_API_KEY=PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE
```

`SecretProvider.get_secret()` treats that exact string as **absent**, so the field name is visible
to a names-only listing while the credential remains not present and the adapter stays
non-callable. `put` is correct *here* and only here, because the secret does not exist yet and has
no other fields to destroy.

Do **not** invent a realistic-looking `sk-ant-…` value. A fake that looks real is a fake that gets
treated as real by the next person to read it.

## Step 6 — clear the shell

```bash
unset VAULT_TOKEN
```

---

## Verification (value-free — safe to run and safe to paste)

```bash
scripts/verify_vault_runtime_readiness.sh
```

It checks seal state, the mount, the path, the presence of the field **name**, that the runtime
token can read the one secret, and that it is refused a write and an unrelated path. It prints
booleans and names. It never prints a secret value, a prefix or a length.

## Later — provisioning the real key (NOT part of this slice)

Only after this readiness slice passes Independent Validation **and** the Product Owner separately
authorizes AT-M3.6B.2:

```bash
set +o history                              # bash; zsh: unset HISTFILE

read -rs -p "Anthropic non-production API key: " ANTHROPIC_KEY; echo

# PATCH, never PUT: ANTHROPIC_API_KEY is one field of a shared secret, and `put` would delete
# every other field at this path. The value is piped on stdin, so it never appears in argv or
# in `ps` output.
printf '%s' "$ANTHROPIC_KEY" | docker compose exec -T -e VAULT_TOKEN vault \
  vault kv patch -mount=secret aiagents/test-runtime ANTHROPIC_API_KEY=-

unset ANTHROPIC_KEY
set -o history

# The provider caches the KV document for the life of the process, so a key written after startup
# is not seen until the process restarts. Restart the consumer, deliberately:
docker compose restart orchestrator

# Names-only confirmation. Never prints the value.
scripts/verify_vault_runtime_readiness.sh
```

The cache is not a defect and this slice does not add a hot-reload subsystem for it: a reasoning
runtime that could silently change which credential it bills to, mid-process, is a worse property
than one that requires a restart you can point at in a deployment log.

---

## Non-production limitations, stated plainly

| Limitation | Consequence | Why it is not fixed here |
| --- | --- | --- |
| No TLS on the Vault listener | Traffic inside the compose network is plaintext | Internal-only, loopback-published; TLS termination is production architecture |
| Manual unseal after every restart | Secrets unreadable until an operator unseals | Auto-unseal needs a KMS/transit seal that does not exist in this project |
| `file` storage, single node | Losing the volume loses the store | Non-production runtime holding one non-production credential |
| Runtime token delivered via env var | Visible to `docker inspect` on the host | It is the only distribution mechanism this repository has; inventing a second one is out of scope |
| One operator holds the unseal key and root token | No custodian separation | Single-operator non-production runtime |

None of these is acceptable for production, and none of them is claimed to be.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
