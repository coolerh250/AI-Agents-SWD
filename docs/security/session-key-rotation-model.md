# Session Key Rotation Model (Step 52.3)

Status: **model only.** Source:
[session-key-rotation-model.yaml](../../infra/identity/session-key-rotation-model.yaml).

The session signing secret today comes from a runtime key file or an ephemeral
in-memory secret (`shared/sdk/operator_actions/session.py`). That source is
**not production-ready** and the key file is **never committed**.

## Required before production (Step 53 dependency)

* A production secret store (Step 53) for the signing key.
* Key IDs (`kid`) on issued sessions.
* Multiple active verification keys (rolling window) so rotation does not force a
  mass logout.
* Emergency (out-of-band) rotation.

Rotation-without-mass-logout and emergency rotation are **required but not
implemented** here; they depend on the production secret store. This step only
records the model and the dependency.
