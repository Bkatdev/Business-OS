"""Persistent execution-spine schema for Business OS v11.

The schema is provider-neutral. Business OS owns action identity, policy state,
attempt history, outcome state, tenant ownership, and reconciliation metadata.
Provider-specific identifiers are references, never canonical identity.
"""

ACTION_FINAL_STATES = {
    "SUCCEEDED",
    "BLOCKED",
    "FAILED_PERMANENT",
    "CANCELLED",
}

ACTION_ATTENTION_STATES = {"UNKNOWN", "FAILED_PERMANENT"}


def ensure_execution_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_key TEXT NOT NULL UNIQUE,
            action_type TEXT NOT NULL,
            business_id INTEGER NOT NULL,
            lead_id INTEGER,
            source_entity_type TEXT NOT NULL DEFAULT '',
            source_entity_id INTEGER,
            mode TEXT NOT NULL DEFAULT 'simulation',
            status TEXT NOT NULL,
            policy_decision TEXT NOT NULL DEFAULT '',
            policy_reason TEXT NOT NULL DEFAULT '',
            approval_required INTEGER NOT NULL DEFAULT 0,
            approval_reference TEXT NOT NULL DEFAULT '',
            idempotency_key TEXT NOT NULL UNIQUE,
            request_fingerprint TEXT NOT NULL DEFAULT '',
            provider TEXT NOT NULL DEFAULT '',
            provider_external_id TEXT NOT NULL DEFAULT '',
            requested_at TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT '',
            accepted_at TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            next_retry_at TEXT NOT NULL DEFAULT '',
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            last_error_class TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            outcome_detail TEXT NOT NULL DEFAULT '',
            data_classification TEXT NOT NULL DEFAULT 'UNVERIFIED',
            quarantine_status TEXT NOT NULL DEFAULT 'Not Required',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );

        CREATE INDEX IF NOT EXISTS idx_actions_business_created
            ON actions(business_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_actions_lead_created
            ON actions(lead_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_actions_status_retry
            ON actions(status, next_retry_at);
        CREATE INDEX IF NOT EXISTS idx_actions_provider_external
            ON actions(provider, provider_external_id);
        CREATE INDEX IF NOT EXISTS idx_actions_source
            ON actions(source_entity_type, source_entity_id, mode);

        CREATE TABLE IF NOT EXISTS action_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER NOT NULL,
            attempt_number INTEGER NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL DEFAULT '',
            provider_external_id TEXT NOT NULL DEFAULT '',
            error_class TEXT NOT NULL DEFAULT '',
            error_detail TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE,
            UNIQUE(action_id, attempt_number)
        );

        CREATE INDEX IF NOT EXISTS idx_action_attempts_action
            ON action_attempts(action_id, attempt_number);
        CREATE INDEX IF NOT EXISTS idx_action_attempts_provider_external
            ON action_attempts(provider, provider_external_id);

        CREATE TABLE IF NOT EXISTS provider_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT '',
            provider_external_id TEXT NOT NULL DEFAULT '',
            action_id INTEGER,
            payload_hash TEXT NOT NULL DEFAULT '',
            processing_status TEXT NOT NULL DEFAULT 'Received',
            detail TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (action_id) REFERENCES actions(id),
            UNIQUE(provider, event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_provider_events_external
            ON provider_events(provider, provider_external_id);
        CREATE INDEX IF NOT EXISTS idx_provider_events_action
            ON provider_events(action_id, received_at DESC);
        """
    )
