# SBOM Capability Inventory (Step 54.3)

Source: [infra/security/sbom-capability-inventory.yaml](../../infra/security/sbom-capability-inventory.yaml).

Static catalog of SBOM tools. Bundled (`installed: true`): `custom_manifest_sbom`,
`custom_container_image_inventory_sbom` — local-only, token-free. External
(`installed: false`, runtime-detected): syft, cyclonedx-py, cyclonedx-npm, npm-sbom. No tool is
installed, no version checked over the network, no SBOM uploaded; no tool claims
`productionReady`. Verified by `scripts/verify_sbom_capability_inventory.py`
(`SBOM_CAPABILITY_INVENTORY_VERIFY`).
