# Image Digest Policy (Step 54.3)

Source: [infra/security/image-digest-policy.yaml](../../infra/security/image-digest-policy.yaml).

Digest pinning is **required** before non-production cluster smoke / ArgoCD manual sync /
deployment request. `latestTagAllowed: false`; `registryLoginConfigured: false`; digest
resolution is manual / future registry query (no registry is contacted this stage).
`currentState.anyDigestPinned: false` and the missing-digest gaps are recorded as blockers — not
marked production-safe. `productionReady: false`. Verified by
`scripts/verify_image_digest_policy.py` (`IMAGE_DIGEST_POLICY_VERIFY`).
