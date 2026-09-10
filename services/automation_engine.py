import re
from dataclasses import dataclass
from datetime import datetime

from services.db import now_iso


@dataclass
class ExecutionResult:
    ok: bool
    status: str
    detail: str
    provider_message_id: str = ""


def normalize_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def validate_sms_message(conn, message):
    """Fail closed. No customer-facing action may run without clear ownership."""
    if message is None:
        return False, "Message does not exist."
    if message["channel"] != "SMS":
        return False, "Only SMS execution is supported right now."
    if message["status"] not in {"Approved", "Failed"}:
        return False, f"Message must be Approved before execution. Current status: {message['status']}."
    if not message["business_id"]:
        return False, "Client ownership is missing. Assign this lead to a client before execution."

    business = conn.execute(
        "SELECT id, name, status FROM businesses WHERE id = ?",
        (message["business_id"],),
    ).fetchone()
    if business is None or business["status"] != "Client":
        return False, "The owning business is not an active Client."

    lead = conn.execute(
        "SELECT id, business_id, phone, status FROM leads WHERE id = ?",
        (message["lead_id"],),
    ).fetchone()
    if lead is None:
        return False, "The linked lead no longer exists."
    if lead["business_id"] != message["business_id"]:
        return False, "Tenant safety check failed: lead and message belong to different businesses."
    if lead["status"] in {"Lost"}:
        return False, "This lead is closed as Lost. Reopen it before customer communication."

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
    return True, f"Ready for {business['name']}"


def _record(conn, message, mode, status, detail, provider="", provider_id=""):
    conn.execute(
        """
        INSERT INTO automation_executions
            (message_id, lead_id, business_id, channel, mode, status, detail,
             provider, provider_message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (message["id"], message["lead_id"], message["business_id"],
         message["channel"], mode, status, detail, provider, provider_id, now_iso()),
    )


def execute_sms(conn, message_id, mode="simulation"):
    message = conn.execute(
        "SELECT * FROM outbound_messages WHERE id = ?", (message_id,)
    ).fetchone()
    valid, reason = validate_sms_message(conn, message)
    timestamp = now_iso()

    if not valid:
        if message is not None:
            _record(conn, message, mode, "Blocked", reason)
            conn.execute(
                "UPDATE outbound_messages SET error = ? WHERE id = ?",
                (reason, message_id),
            )
            conn.commit()
        return ExecutionResult(False, "Blocked", reason)

    if mode != "simulation":
        detail = "Live delivery is locked. A production provider, consent policy, monitoring, and kill switch must be configured first."
        _record(conn, message, mode, "Blocked", detail)
        conn.commit()
        return ExecutionResult(False, "Blocked", detail)

    provider_id = f"sim_{message_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    detail = "Simulation completed. Ownership, recipient, message, and execution checks passed. No customer was contacted."
    conn.execute(
        """
        UPDATE outbound_messages
        SET status = 'Simulated Sent', provider = 'Simulation', provider_message_id = ?,
            send_attempts = COALESCE(send_attempts, 0) + 1,
            last_attempt_at = ?, sent_at = ?, error = ''
        WHERE id = ?
        """,
        (provider_id, timestamp, timestamp, message_id),
    )
    _record(conn, message, "simulation", "Success", detail, "Simulation", provider_id)
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Automation', 'SMS execution simulated', ?, ?)
        """,
        (message["lead_id"], detail, timestamp),
    )
    conn.commit()
    return ExecutionResult(True, "Simulated Sent", detail, provider_id)
