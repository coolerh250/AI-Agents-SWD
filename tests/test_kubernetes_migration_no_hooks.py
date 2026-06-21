"""Step 51.2C2 -- batch templates carry NO Helm/ArgoCD hook annotations."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "templates"

BATCH_TEMPLATES = ["migration-job.yaml", "backup-cronjob.yaml", "restore-job.yaml"]
HOOK_TOKENS = ["helm.sh/hook", "argocd.argoproj.io/hook", "argocd.argoproj.io/sync-wave"]


def test_no_hook_annotations_in_batch_templates() -> None:
    for name in BATCH_TEMPLATES:
        raw = (TEMPLATES / name).read_text(encoding="utf-8")
        for tok in HOOK_TOKENS:
            assert tok not in raw, f"{name}: {tok}"


def test_no_hook_annotations_anywhere_in_templates() -> None:
    for p in TEMPLATES.glob("*.yaml"):
        raw = p.read_text(encoding="utf-8")
        for tok in HOOK_TOKENS:
            assert tok not in raw, f"{p.name}: {tok}"
