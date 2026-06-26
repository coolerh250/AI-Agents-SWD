# Non-production Kubernetes tooling (Step 55.1)

Tools required to run the Step 55 non-production runtime smoke, how they were
installed, and the versions used. **No production / cloud / registry credential is
required by any of them; none logs into a registry or pushes an image.**

- Inventory: [`infra/kubernetes/nonproduction-tooling-inventory.yaml`](../../infra/kubernetes/nonproduction-tooling-inventory.yaml)
- Verifier: `scripts/verify_nonproduction_kubernetes_tooling.py` → `NONPROD_KUBERNETES_TOOLING_VERIFY`

| Tool | Version | Source | Production credential |
|------|---------|--------|-----------------------|
| kubectl | v1.36.2 | https://dl.k8s.io/release (official stable binary) | none |
| helm | v3.16.4 | https://get.helm.sh (official release tarball) | none |
| kind | v0.25.0 | https://kind.sigs.k8s.io/dl (official release binary) | none |
| docker | 29.5.2 | pre-existing host runtime | none |

kind node image: `kindest/node:v1.31.2`.

## Install (official sources only, no piped unknown scripts)

```bash
# kubectl
KVER=$(curl -L -s https://dl.k8s.io/release/stable.txt)
curl -sSLO "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
# helm
curl -sSLO https://get.helm.sh/helm-v3.16.4-linux-amd64.tar.gz
tar -xzf helm-v3.16.4-linux-amd64.tar.gz && sudo install -m 0755 linux-amd64/helm /usr/local/bin/helm
# kind
curl -sSLo kind https://kind.sigs.k8s.io/dl/v0.25.0/kind-linux-amd64
sudo install -m 0755 kind /usr/local/bin/kind
```

## Deliberately NOT installed

`argocd-cli` (Step 56 concern), any cloud provider CLI (no cloud credential in
scope), and registry credential helpers. The smoke never logs into a registry.
