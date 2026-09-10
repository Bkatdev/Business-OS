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


def validate_sms_message(message):
    if message is None:
        return False, "Message does not exist."
    if message["channel"] != "SMS":
        return False, "Only SMS execution is supported right now."
    if message["status"] not in {"Approved", "Failed"}:
        return False, f"Message must be Approved before execution. Current status: {message['status']}."
    if not normalize_phone(message["recipient"]):
        return False, "Recipient does not have a usable phone number."
    if not str(message["body"] or "").strip():
        return False, "Message body is empty."
    if len(str(message["body"])) > 1200:
        return False, "Message is too long for the current SMS safety policy."
    return True, "Ready"


def execute_sms(conn, message_id, mode="simulation"):
    message = conn.execute(
        "SELECT * FROM outbound_messages WHERE id = ?", (message_id,)
    ).fetchone()
    valid, reason = validate_sms_message(message)
    timestamp = now_iso()

    if not valid:
        if message is not None:
            conn.execute(
                """
                INSERT INTO automation_executions
                    (message_id, lead_id, business_id, channel, mode, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?, 'Blocked', ?, ?)
                """,
                (message_id, message["lead_id"], message["business_id"],
                 message["channel"], mode, reason, timestamp),
            )
            conn.commit()
        return ExecutionResult(False, "Blocked", reason)

    if mode != "simulation":
        detail = "Live provider execution is locked until a provider is configured and explicitly enabled."
        conn.execute(
            """
            INSERT INTO automation_executions
                (message_id, lead_id, business_id, channel, mode, status, detail, created_at)
            VALUES (?, ?, ?, 'SMS', ?, 'Blocked', ?, ?)
            """,
            (message_id, message["lead_id"], message["business_id"], mode, detail, timestamp),
        )
        conn.commit()
        return ExecutionResult(False, "Blocked", detail)

    # Simulation exercises the complete execution lifecycle without contacting anyone.
    provider_id = f"sim_{message_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    detail = "Simulation completed. No customer was contacted."
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
    conn.execute(
        """
        INSERT INTO automation_executions
            (message_id, lead_id, business_id, channel, mode, status, detail,
             provider, provider_message_id, created_at)
        VALUES (?, ?, ?, 'SMS', 'simulation', 'Success', ?, 'Simulation', ?, ?)
        """,
        (message_id, message["lead_id"], message["business_id"], detail, provider_id, timestamp),
    )
    conn.execute(
        """
        INSERT INTO lead_activities (lead_id, activity_type, title, details, created_at)
        VALUES (?, 'Automation', 'SMS execution simulated', ?, ?)
        """,
        (message["lead_id"], "No customer was contacted. Execution pipeline passed in simulation mode.", timestamp),
    )
    conn.commit()
    return ExecutionResult(True, "Simulated Sent", detail, provider_id)
