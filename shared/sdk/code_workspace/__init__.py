"""Stage 28 — controlled code generation workspace SDK.

Public surface:

* :class:`CodeWorkspace`, :class:`CodeChangeArtifact`,
  :class:`PRDraftArtifact` — dataclass snapshots of the three Stage 28
  tables.
* :class:`CodeWorkspaceStore` — async asyncpg store for all three.
* :data:`DEFAULT_ALLOWED_PATHS` / :data:`DEFAULT_DENIED_PATHS` —
  the deterministic generator's safe-by-default policy.
* :func:`validate_allowed_path`, :func:`validate_change_type`,
  :func:`validate_no_secret_content`,
  :func:`validate_no_destructive_change`, :func:`classify_change_risk` —
  pure path / content / diff policy checks (no LLM).
* :func:`compute_unified_diff`, :func:`summarize_diff`,
  :func:`hash_content` — diff helpers.
* :func:`validate_generated_files_exist`, :func:`validate_allowlist`,
  :func:`validate_no_secrets`, :func:`validate_python_syntax_if_py`,
  :func:`validate_tests_syntax_if_py`, :func:`validate_diff_not_empty`,
  :func:`validate_no_denied_paths` — workspace-level validators.
"""

from shared.sdk.code_workspace.diff import (
    compute_unified_diff,
    hash_content,
    summarize_diff,
)
from shared.sdk.code_workspace.models import (
    CodeChangeArtifact,
    CodeWorkspace,
    PRDraftArtifact,
)
from shared.sdk.code_workspace.policy import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    classify_change_risk,
    validate_allowed_path,
    validate_change_type,
    validate_no_destructive_change,
    validate_no_secret_content,
)
from shared.sdk.code_workspace.store import CodeWorkspaceStore
from shared.sdk.code_workspace.validator import (
    validate_allowlist,
    validate_diff_not_empty,
    validate_generated_files_exist,
    validate_no_denied_paths,
    validate_no_secrets,
    validate_python_syntax_if_py,
    validate_tests_syntax_if_py,
)

__all__ = [
    "CodeChangeArtifact",
    "CodeWorkspace",
    "CodeWorkspaceStore",
    "DEFAULT_ALLOWED_PATHS",
    "DEFAULT_DENIED_PATHS",
    "PRDraftArtifact",
    "classify_change_risk",
    "compute_unified_diff",
    "hash_content",
    "summarize_diff",
    "validate_allowed_path",
    "validate_allowlist",
    "validate_change_type",
    "validate_diff_not_empty",
    "validate_generated_files_exist",
    "validate_no_denied_paths",
    "validate_no_destructive_change",
    "validate_no_secret_content",
    "validate_no_secrets",
    "validate_python_syntax_if_py",
    "validate_tests_syntax_if_py",
]
