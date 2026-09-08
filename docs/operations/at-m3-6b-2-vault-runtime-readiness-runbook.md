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

**Check out the readiness branch on the test host first.** The persistent Vault service exists only
in that branch's compose file. A checkout on any earlier branch still runs `vault server -dev`, and
every step below would then be addressing an in-memory Vault that discards its contents on restart.

```bash
cd ~/AI-Agents-SWD
git fetch origin
git checkout at-m3.6b.2-runtime-secret-readiness-1

cd infra/docker-compose
docker compose up -d --force-recreate vault
docker compose exec vault vault status || true
```

Expect `Initialized false`, `Sealed true`, **`Storage Type file`**. `vault status` exits non-zero
while sealed — hence the `|| true`.

**Confirm the posture before going further.** Each of these catches "you are addressing the wrong
Vault", which is the mistake this step exists to prevent:

```bash
docker inspect aiagents-test-vault-1 --format 'args={{.Args}}'   # expect [server], NOT [server -dev]
docker compose exec vault vault status -format=json | jq -r .storage_type   # expect file, NOT inmem
docker volume ls | grep aiagents-test_vault-data                 # expect one row
```

A dev-mode Vault reports `Initialized true`, `Sealed false`, `Storage Type inmem`. Read as "already
initialized, skip ahead", that leads to writing the placeholder into memory, where it verifies green
and then vanishes on the next restart. **`Initialized true` here means the wrong container, not a
completed step.**

### If step 1 fails with an HTTPS/TLS error

```text
Error checking seal status: Get "https://127.0.0.1:8200/v1/sys/seal-status":
http: server gave HTTP response to HTTPS client
```

The Vault CLI defaults `VAULT_ADDR` to `https://127.0.0.1:8200`, and this listener runs
`tls_disable = 1`, so it answers plain HTTP. The readiness compose sets
`VAULT_ADDR: http://127.0.0.1:8200` on the vault service, so a container created from *it* never
sees this: the error means the running container predates that change — recreate it as above. To
confirm the diagnosis without recreating anything:

```bash
docker compose exec -e VAULT_ADDR=http://127.0.0.1:8200 vault vault status
```

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

## Step 4 — enable KV v2, load the policy, mint the runtime token (produces a secret — operator only)

```bash
export VAULT_TOKEN=<your root token>     # this shell only; step 6 clears it

# Enable the KV v2 secrets engine at `secret/`.
#
# NOT OPTIONAL, and easy to miss: `vault server -dev` auto-mounted this, and a real server does
# not. Skipping it makes every later `kv put`/`kv patch` fail with "no handler for route", and the
# runtime's own read 404s. This step was added after a disposable verification Vault, built from
# the committed config, failed here -- reading the config would not have found it.
docker compose exec -e VAULT_TOKEN vault vault secrets enable -path=secret -version=2 kv
docker compose exec -e VAULT_TOKEN vault vault secrets list -format=json   | jq -r '."secret/".options.version'                                 # expect: 2

# The policy file is already mounted into the container, read-only.
docker compose exec -e VAULT_TOKEN vault \
  vault policy write aiagents-runtime-read /vault/policies/aiagents-runtime-read.hcl

docker compose exec -e VAULT_TOKEN vault vault policy read aiagents-runtime-read

# The RUNTIME token. Read-only, scoped to one secret, renewable, no default policy.
docker compose exec -e VAULT_TOKEN vault \
  vault token create -policy=aiagents-runtime-read -no-default-policy -period=768h -field=token
```

The last command prints **one value: the runtime token**. Treat it as a secret:

- put it in `infra/docker-compose/.env` as `VAULT_TOKEN=…` (gitignored; `chmod 600`),
- never commit it, never paste it into chat, never echo it in a log,
- note that it is *not* the root token — the root token is never given to a service,
- and recreate the consumer rather than restarting it: `VAULT_TOKEN` is an **environment** change,
  so `docker compose up -d --force-recreate orchestrator`. See "Restart or recreate?" below for
  why a plain `restart` would report success and change nothing.

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

## Restart or recreate? The two are not interchangeable

This distinction has already cost one round of "the token is in the file, why is the runtime still
using the old one", so it is written down rather than left to be rediscovered.

| What changed | What is required | Why |
| --- | --- | --- |
| **Environment** — a variable in `.env` or in the compose file changed. `VAULT_TOKEN=…` is the case that matters here. | `docker compose up -d --force-recreate orchestrator` | A container's environment is fixed **when the container is created**. `.env` is read by the Compose *client* at create time to interpolate `${VAULT_TOKEN}`; the value is then baked into the container. |
| **Secret value only** — the environment is unchanged, and a field inside the Vault secret was rewritten (e.g. a key rotated at the canonical path). | `docker compose restart orchestrator` — a process/container restart is sufficient | `VaultKvSecretProvider` caches the KV document for the life of the process. A restart drops the cache and the next `get_secret` re-fetches. Nothing about the environment needs to change. |

**`docker compose restart` does not re-read `.env`.** It stops and starts the *existing* container
with the environment it was created with. Run it after a token change and it will report success,
the container will come up healthy, and it will still be presenting the old token to Vault. That is
the failure mode this table exists to prevent — a green restart that changed nothing.

`docker compose up -d` on its own is also not enough: with no configuration change Compose
considers the container up to date and leaves it alone. `.env` interpolation *is* part of the
config hash, so an edited token usually does trigger a replacement — but `--force-recreate` makes
it unconditional, which is what an operator following a runbook needs.

## Verification (value-free — safe to run and safe to paste)

```bash
# With the runtime token in the environment:
VAULT_TOKEN=<scoped runtime token> scripts/verify_vault_runtime_readiness.sh

# Or, reading it from the compose env file that the runtime itself uses:
scripts/verify_vault_runtime_readiness.sh --from-compose-env
```

It checks seal state, the mount, the path, the presence of the field **name**, that the runtime
token can read the one secret, and that it is refused a write, a delete, an unrelated path,
the metadata path and `sys/policy`. It prints booleans, names and diagnostic categories. It never
prints a secret value, a prefix or a length.

**Two orderings in it are load-bearing**, and both exist because the first version could report
PASS while proving nothing:

- **No token is a hard FAIL**, evaluated before anything else. Every denial check is "Vault refused
  this". With no token Vault refuses all of them, for the wrong reason, and counting those
  refusals as passes would certify an unconfigured runtime as ready.
- **The canonical read must succeed before any denial counts.** The same failure one step further
  in: an expired, revoked or wrongly-scoped token is refused everywhere, including where refusal is
  the desired answer. So `secret/data/aiagents/test-runtime` — the exact request the provider makes
  — is the gate. If it fails the script prints one of

  ```text
  READINESS_DIAGNOSTIC: TOKEN_MISSING_OR_DENIED   the token is expired, revoked, or wrongly scoped
  READINESS_DIAGNOSTIC: NO_HANDLER_FOR_ROUTE      no KV v2 engine at secret/ — step 4 was skipped
  READINESS_DIAGNOSTIC: NO_VALUE_FOUND            the mount exists, nothing is written — step 5
  READINESS_DIAGNOSTIC: OTHER_READ_FAILURE        none of the above; check the container logs
  ```

  and stops. The category is derived from Vault's error text and printed instead of it, because a
  Vault error can quote the request path and there is no reason to widen what the script emits.

## Completing readiness without handing over the root token

The steps above are the manual path. There is also a bounded helper that performs the whole
operator half — verify the policy, confirm the mount, revoke a superseded runtime token, mint a new
one, prove it can read before testing that it cannot write, inject it, recreate the orchestrator,
and run the verification — **while the token exists only as a file path to whoever invokes it**:

```bash
# Operator, in their own shell. `set +o history` first; the value is typed, not echoed.
set +o history
install -m 600 /dev/null /dev/shm/vault-operator-token.$$
read -rs -p "Vault operator token: " T; printf '%s' "$T" > /dev/shm/vault-operator-token.$$
unset T; set -o history
echo /dev/shm/vault-operator-token.$$     # hand over THIS PATH, never the value

scripts/complete_vault_runtime_readiness.sh \
  --operator-token-file /dev/shm/vault-operator-token.$$
```

The helper refuses a path that is a symlink, is not a regular file, is not mode `600`, is not owned
by the caller, or lives inside the repository working tree — each of those being a way the file
could be something other than what the operator intended. It reads the value into one shell
variable, passes it to Vault through a child process's environment (never argv, so it is absent
from `ps`), writes it nowhere, and deletes the file when the procedure succeeds. On failure it
keeps the file — operator authority may still be needed — and says so as
`operator_token_file_removed=no`.

`/dev/shm` is preferred because it is tmpfs: the value never reaches a disk.

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

# SECRET VALUE ONLY -- the environment did not change, so a restart is sufficient and correct here.
# The provider caches the KV document for the life of the process, so a key written after startup
# is not seen until the process restarts; a restart drops the cache. This is NOT the case where
# --force-recreate is needed -- that one is a VAULT_TOKEN change. See "Restart or recreate?" above.
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
