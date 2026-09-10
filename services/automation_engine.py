import re
from dataclasses import dataclass

from services.db import now_iso
from services.execution_core import ActionIntent, execute_action
from services.governance import production_automation_policy, simulation_policy


@dataclass
class ExecutionResult:
    ok: bool
    status: str
    detail: str
    provider_message_id: str = ""
    action_id: int | None = None
    deduplicated: bool = False


def normalize_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def validate_sms_message(conn, message):
    """Validate an SMS draft without granting permission for live delivery."""
    if message is None:
        return False, "Message does not exist."
    if message["channel"] != "SMS":
        return False, "Only SMS execution is supported right now."
    if message["status"] not in {"Approved", "Failed", "Simulated Sent"}:
        return False, f"Message must be Approved before execution. Current status: {message['status']}."
    if not message["business_id"]:
        return False, "Client ownership is missing. Unowned records remain quarantined."
    if (message["quarantine_status"] or "") == "Open":
        return False, "Message is quarantined and cannot be executed."

    business = conn.execute(
        "SELECT id, name, status, lifecycle_stage FROM businesses WHERE id = ?",
        (message["business_id"],),
    ).fetchone()
    if business is None:
        return False, "The owning business does not exist."
    if (business["lifecycle_stage"] or "").upper() in {"CANCELLED", "PAUSED"}:
        return False, f"The owning business is {business['lifecycle_stage']}; automation is locked."

    lead = conn.execute(
        """
        SELECT id, business_id, phone, status, data_classification,
               quarantine_status
        FROM leads WHERE id = ?
        """,
        (message["lead_id"],),
    ).fetchone()
    if lead is None:
        return False, "The linked lead no longer exists."
    if lead["business_id"] != message["business_id"]:
        return False, "Tenant safety check failed: lead and message belong to different businesses."
    if (lead["quarantine_status"] or "") == "Open":
        return False, "The linked lead is quarantined."
    if lead["status"] == "Lost":
        return False, "This lead is closed as Lost. Reopen it before customer communication."

    lead_class = (lead["data_classification"] or "LEGACY").upper()
    message_class = (message["data_classification"] or "LEGACY").upper()
    if lead_class not in {"TEST", "DEMO", "PRODUCTION"}:
        return False, f"Lead classification {lead_class} is not automation-eligible."
    if message_class != lead_class:
        return False, "Message classification must match the linked lead."

    recipient = normalize_phone(message["recipient"])
    lead_phone = normalize_phone(lead["phone"])
    if len(recipient) != 10:
        return False, "Recipient must contain a valid 10-digit US phone number."
    if recipient != lead_phone:
        return False, "Recipient safety check failed: message phone does not match the current lead phone."
    if not str(message["body"] or "").strip():
        return False, "Message body is empty."
    if len(str(message["body"])) > 1200:
        return False, "Message is too long for the current SMS safety policy."
    return True, f"SMS validation passed for {business['name']}."


def _record_legacy_execution(conn, message, mode, status, detail, provider="", provider_id=""):
    """Keep the v10.x execution ledger populated during the v11 transition."""
    classification = (message["data_classification"] or "LEGACY").upper()
    quarantine_status = message["quarantine_status"] or "Not Required"
    quarantine_reason = message["quarantine_reason"] or ""
    conn.execute(
        """
        INSERT INTO automation_executions
            (message_id, lead_id, business_id, channel, mode, status, detail,
             provider, provider_message_id, created_at, data_classification,
             quarantine_status, quarantine_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (message["id"], message["lead_id"], message["business_id"],
         message["channel"], mode, status, detail, provider, provider_id,
         now_iso(), classification, quarantine_status, quarantine_reason),
    )


def execute_sms(conn, message_id, mode="simulation"):
    """Execute SMS through the v11 governed action spine.

    v11 keeps the public behavior simulation-only. A live caller can request
    mode='live', but the global gate and provider registry fail closed.
    """
    message = conn.execute(
        "SELECT * FROM outbound_messages WHERE id = ?", (message_id,)
    ).fetchone()
    if message is None:
        return ExecutionResult(False, "Blocked", "Message does not exist.")

    valid, validation_reason = validate_sms_message(conn, message)
    if not valid:
        # Keep invalid requests observable without creating a provider attempt.
        intent = ActionIntent(
            action_type="SEND_SMS",
            business_id=message["business_id"] or 0,
            lead_id=message["lead_id"],
            source_entity_type="outbound_message",
            source_entity_id=message["id"],
            mode=mode,
            approval_required=True,
            approval_reference=f"outbound_message:{message['id']}",
            data_classification=(message["data_classification"] or "UNVERIFIED").upper(),
            quarantine_status=message["quarantine_status"] or "Not Required",
        )
        # If ownership itself is missing, do not insert an action with invalid FK.
        if not message["business_id"]:
            conn.execute("UPDATE outbound_messages SET error = ? WHERE id = ?", (validation_reason, message_id))
            conn.commit()
            return ExecutionResult(False, "Blocked", validation_reason)
        result = execute_action(
            conn,
            intent,
            {"recipient": normalize_phone(message["recipient"]), "body": message["body"], "channel": "SMS"},
            policy_allowed=False,
            policy_reason=validation_reason,
            policy_context={"message_id": message_id, "validation": "failed"},
        )
        conn.execute("UPDATE outbound_messages SET error = ? WHERE id = ?", (validation_reason, message_id))
        if not result.deduplicated:
            _record_legacy_execution(conn, message, mode, "Blocked", validation_reason)
        conn.commit()
        return ExecutionResult(False, "Blocked", validation_reason, action_id=result.action_id, deduplicated=result.deduplicated)

    if mode == "simulation":
        decision = simulation_policy(conn, message)
    else:
        decision = production_automation_policy(conn, message)

    payload = {
        "channel": "SMS",
        "recipient": normalize_phone(message["recipient"]),
        "body": str(message["body"] or ""),
    }
    intent = ActionIntent(
        action_type="SEND_SMS",
        business_id=message["business_id"],
        lead_id=message["lead_id"],
        source_entity_type="outbound_message",
        source_entity_id=message["id"],
        mode=mode,
        approval_required=True,
        approval_reference=f"outbound_message:{message['id']}",
        data_classification=(message["data_classification"] or "UNVERIFIED").upper(),
        quarantine_status=message["quarantine_status"] or "Not Required",
    )
    result = execute_action(
        conn,
        intent,
        payload,
        policy_allowed=decision.allowed,
        policy_reason=decision.reason,
        policy_context={"message_id": message_id, "governance_classification": decision.classification},
    )

    if result.ok and mode == "simulation":
        timestamp = now_iso()
        conn.execute(
            """
            UPDATE outbound_messages
            SET status = 'Simulated Sent', provider = ?, provider_message_id = ?,
                send_attempts = CASE WHEN ? THEN COALESCE(send_attempts, 0) ELSE COALESCE(send_attempts, 0) + 1 END,
                last_attempt_at = ?, sent_at = ?, error = ''
            WHERE id = ?
            """,
            (result.provider, result.provider_external_id, 1 if result.deduplicated else 0,
             timestamp, timestamp, message_id),
        )
        if not result.deduplicated:
            detail = (
                "Simulation completed through the v11 governed execution spine. "
                "Policy, ownership, idempotency, provider boundary, outcome, and audit checks passed. "
                "No customer was contacted."
            )
            _record_legacy_execution(
                conn, message, mode, "Success", detail, result.provider, result.provider_external_id
            )
            conn.execute(
                """
                INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
                VALUES (?, 'Automation', 'SMS execution simulated through v11', ?, ?)
                """,
                (message["lead_id"], detail, timestamp),
            )
        conn.commit()
        detail = result.detail if not result.deduplicated else "Duplicate execution request safely reused the existing completed action. No customer was contacted."
        return ExecutionResult(True, "Simulated Sent", detail, result.provider_external_id, result.action_id, result.deduplicated)

    # Live remains fail-closed until a real provider is deliberately introduced.
    if not result.deduplicated:
        _record_legacy_execution(conn, message, mode, "Blocked" if result.status == "BLOCKED" else result.status, result.detail, result.provider, result.provider_external_id)
    conn.execute("UPDATE outbound_messages SET error = ? WHERE id = ?", (result.detail, message_id))
    conn.commit()
    return ExecutionResult(False, result.status, result.detail, result.provider_external_id, result.action_id, result.deduplicated)
