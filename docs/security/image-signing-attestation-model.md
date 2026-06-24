# Image Signing / Attestation Model (Step 54.3)

Source: [infra/security/image-signing-attestation-model.yaml](../../infra/security/image-signing-attestation-model.yaml).

Model only. Signing required before production but **not configured**: `signingConfigured`,
`attestationConfigured`, `privateKeyCommitted`, `signingPerformed`, `attestationGenerated`,
`attestationUploaded`, `productionReady` all false; `status: model_only`. Allowed tools (future):
cosign, sigstore, notation (keyless preferred). No key is generated or committed, nothing is
signed or uploaded. Depends on Step 54.4 + future production key management. Verified by
`scripts/verify_image_signing_attestation_model.py` (`IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY`),
which also guards against any committed signing key.
