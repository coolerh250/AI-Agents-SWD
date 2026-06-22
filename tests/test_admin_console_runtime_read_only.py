"""Step 51.4 -- Admin Console runtime view exposes no deploy/sync/apply action."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "RuntimeBaseline.tsx"
CLIENT = ADMIN / "src" / "api" / "client.ts"

FORBIDDEN_BUTTON = re.compile(
    r"<button[^>]*>[^<]*(deploy|sync|apply|install|upgrade)[^<]*</button>", re.IGNORECASE
)


def test_runtime_views_have_no_action_buttons() -> None:
    for f in (STATIC, PAGE):
        assert not FORBIDDEN_BUTTON.search(f.read_text(encoding="utf-8")), f.name


def test_no_credential_or_kubeconfig_input() -> None:
    # the runtime views are read-only displays: no form input / file upload at all
    page = PAGE.read_text(encoding="utf-8")
    static_runtime = STATIC.read_text(encoding="utf-8")
    static_runtime = static_runtime[
        static_runtime.find("renderRuntime") : static_runtime.find("refreshSafetyPill")
    ]
    for t in (page, static_runtime):
        assert "<input" not in t
        assert 'type="password"' not in t
        assert "<form" not in t


def test_client_get_only() -> None:
    src = CLIENT.read_text(encoding="utf-8")
    assert not re.search(r"method:\s*[\"'](POST|PUT|PATCH|DELETE)", src)


def test_runtime_page_uses_async_read_only_loader() -> None:
    t = PAGE.read_text(encoding="utf-8")
    assert "AsyncView" in t
    assert "getRuntimeReport" in t
    assert ".post(" not in t and ".put(" not in t and ".delete(" not in t
