# Supply Chain Inventory (Step 54.1)

Source of truth: [infra/security/supply-chain-inventory.yaml](../../infra/security/supply-chain-inventory.yaml).

Inventories the platform's supply chain: source control posture, dependency package/lock
files, container Dockerfiles and images (compose + Helm), build artifacts, and scanner
configuration — all from the **actual** repo.

## Key facts

- **Source control:** GitHub; write disabled, PR creation disabled, no protected-branch policy.
- **Python:** 21 `requirements.txt` files, **no lockfile** (`unpinned_no_lockfile`).
- **Node:** `apps/admin-console/package.json` + `package-lock.json` (`locked`).
- **Containers:** 20 first-party Dockerfiles (`python:3.12-slim`); 7 third-party compose
  images; 20 first-party + 3 third-party Helm images. `imageDigestPinned: false`,
  `latestTagAllowed: false`.
- **Artifacts:** no SBOM, no attestation, no signing.
- **Scanners:** SAST / dependency / secret / image scanners all `configured: false`. A custom
  repo secret-shape scanner exists (Step 53) but is not a configured CI secret scanner.
- **Image push / registry login / external scanner upload:** all `false`.

Verified by `scripts/verify_supply_chain_inventory.py` (`SUPPLY_CHAIN_INVENTORY_VERIFY`).
