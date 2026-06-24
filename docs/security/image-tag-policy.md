# Image Tag Policy (Step 54.3)

Source: [infra/security/image-tag-policy.yaml](../../infra/security/image-tag-policy.yaml).

`latest` prohibited; floating tags prohibited before runtime smoke; semantic versions preferred;
digest required before cluster smoke; test-local tags allowed for local/dev only; production
placeholder tags not deployable; tag mutation requires approval; no auto tag rewrite.
Current state: no `:latest` detected; first-party images use the non-deployable
`step-51-1-placeholder` tag. `productionReady: false`. Covered by
`tests/test_image_tag_policy.py`.
