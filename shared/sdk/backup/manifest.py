"""Stage 36 -- BackupManifest dataclass + load/write helpers.

The manifest is the source of truth for every backup artifact. It is
deterministic JSON (sorted keys, separators=(",", ":")) so any future
verifier can compare two manifests byte-for-byte.

Manifest is safe to commit to the audit chain. It MUST NOT carry:

  * DB password
  * encryption key
  * storage credential

The dataclass refuses to serialize a field whose name matches a
known-sensitive pattern.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = "1.0"

_FORBIDDEN_FIELDS = frozenset(
    {
        "encryption_key",
        "encryption_key_value",
        "db_password",
        "password",
        "storage_access_key",
        "storage_secret_access_key",
        "secret",
        "token",
    }
)


@dataclass
class BackupManifest:
    backup_id: str
    created_at: str
    environment: str
    source_database: str
    source_host: str
    pg_version: str
    backup_format: str
    backup_file: str
    backup_size_bytes: int
    checksum_sha256: str
    encrypted: bool
    encryption_mode: str
    encryption_key_id: str | None
    compression: str
    off_host_uploaded: bool
    off_host_uri: str | None
    schema_version: str = MANIFEST_SCHEMA_VERSION
    included_tables: list[str] = field(default_factory=list)
    row_count_summary: dict[str, int] = field(default_factory=dict)
    audit_chain_latest_hash: str | None = None
    created_by: str = "scripts/backup_postgres_encrypted.sh"
    production_executed: bool = False

    def __post_init__(self) -> None:
        # Hard-fail if a forbidden key sneaks in via metadata.
        for forbidden in _FORBIDDEN_FIELDS:
            if forbidden in self.row_count_summary:
                raise ValueError(
                    f"manifest row_count_summary cannot contain forbidden key: {forbidden}"
                )
            if forbidden in self.included_tables:
                raise ValueError(
                    f"manifest included_tables cannot contain forbidden key: {forbidden}"
                )
        if not self.backup_id:
            raise ValueError("backup_id is required")
        if not self.checksum_sha256:
            raise ValueError("checksum_sha256 is required")
        # production_executed is pinned False -- Stage 36 forbids
        # production-mode backups going through this path.
        self.production_executed = False

    def to_canonical_json(self) -> str:
        """Deterministic JSON (sorted keys, no whitespace)."""

        payload = asdict(self)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    def to_pretty_json(self) -> str:
        """Indented JSON for human-readable on-disk persistence."""

        payload = asdict(self)
        return json.dumps(payload, sort_keys=True, indent=2, default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BackupManifest:
        return cls(
            backup_id=str(payload["backup_id"]),
            created_at=str(payload["created_at"]),
            environment=str(payload.get("environment", "local")),
            source_database=str(payload.get("source_database", "aiagents")),
            source_host=str(payload.get("source_host", "")),
            pg_version=str(payload.get("pg_version", "")),
            backup_format=str(payload.get("backup_format", "pg_dump-custom")),
            backup_file=str(payload.get("backup_file", "")),
            backup_size_bytes=int(payload.get("backup_size_bytes", 0)),
            checksum_sha256=str(payload.get("checksum_sha256", "")),
            encrypted=bool(payload.get("encrypted", False)),
            encryption_mode=str(payload.get("encryption_mode", "none")),
            encryption_key_id=payload.get("encryption_key_id"),
            compression=str(payload.get("compression", "pg_dump-custom-zlib")),
            off_host_uploaded=bool(payload.get("off_host_uploaded", False)),
            off_host_uri=payload.get("off_host_uri"),
            schema_version=str(payload.get("schema_version", MANIFEST_SCHEMA_VERSION)),
            included_tables=list(payload.get("included_tables", [])),
            row_count_summary=dict(payload.get("row_count_summary", {})),
            audit_chain_latest_hash=payload.get("audit_chain_latest_hash"),
            created_by=str(payload.get("created_by", "")),
            production_executed=bool(payload.get("production_executed", False)),
        )

    def manifest_filename(self) -> str:
        return f"backup_manifest_{self.backup_id}.json"


def write_manifest(manifest: BackupManifest, directory: str | Path) -> Path:
    """Persist the manifest beside the backup artifact."""

    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / manifest.manifest_filename()
    out_path.write_text(manifest.to_pretty_json(), encoding="utf-8")
    return out_path


def load_manifest(path: str | Path) -> BackupManifest:
    target = Path(path)
    raw = json.loads(target.read_text(encoding="utf-8"))
    return BackupManifest.from_dict(raw)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
