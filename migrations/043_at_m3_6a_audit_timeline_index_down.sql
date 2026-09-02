-- Reverses 043_at_m3_6a_audit_timeline_index.sql.
--
-- Unconditional, and unlike 042's DOWN it has nothing to refuse. 042 fails closed once
-- materialization evidence exists because the tables it would drop are the ONLY record of which
-- work item is which plan step -- dropping them destroys information. This migration created one
-- index. An index holds no information that is not already in `audit_logs`, nothing references it,
-- no read depends on its existence for correctness, and rebuilding it is a single statement.
--
-- Dropping it costs exactly one thing: the Goal timeline goes back to scanning `audit_logs`. It
-- still returns the same rows, in the same order, with the same content.
--
-- SAFETY: index only. Drops no table, alters no column, deletes no row, and touches no audit,
-- approval or execution data.

BEGIN;

DROP INDEX IF EXISTS idx_audit_logs_artifact_refs_gin;

COMMIT;
