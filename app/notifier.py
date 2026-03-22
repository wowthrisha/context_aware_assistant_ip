"""
notifier.py

Dispatches reminder alerts to WhatsApp (Twilio) and Email (Resend).
Called when a reminder fires. Never raises — all errors are caught
and logged so SSE always fires regardless of notification outcome.
"""

import logging

logger = logging.getLogger(__name__)


def send_whatsapp(to_number: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    try:
        from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, WHATSAPP_ENABLED
        if not WHATSAPP_ENABLED:
            logger.warning("WhatsApp skipped — TWILIO credentials not configured")
            return False

        from twilio.rest import Client
        from twilio.http.http_client import TwilioHttpClient
        http_client = TwilioHttpClient(timeout=90)
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, http_client=http_client)

        to = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number

        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to,
            body=message
        )
        logger.info(f"WhatsApp sent OK — to={to_number} sid={msg.sid}")
        return True

    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return False


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send an email via Resend API. Returns True on success."""
    try:
        from app.config import RESEND_API_KEY, EMAIL_ENABLED
        if not EMAIL_ENABLED:
            logger.warning("Email skipped — RESEND_API_KEY not configured")
            return False

        import resend
        resend.api_key = RESEND_API_KEY

        params = {
            "from": "Context Assistant <onboarding@resend.dev>",
            "to": [to_address],
            "subject": subject,
            "html": f"""
            <div style="font-family:sans-serif;max-width:520px;margin:0 auto;
                        background:#16213e;padding:28px;border-radius:12px;
                        border-left:4px solid #4f8ef7;">
                <h2 style="color:#4f8ef7;margin-top:0;">&#9200; Reminder</h2>
                <p style="color:#e0e0e0;font-size:16px;line-height:1.6;">{body}</p>
                <p style="color:#888;font-size:12px;margin-bottom:0;">
                    — Your Context Assistant
                </p>
            </div>
            """,
        }

        response = resend.Emails.send(params)
        logger.info(f"Email sent OK — to={to_address} id={response['id']}")
        return True

    except Exception as e:
        logger.error(f"Resend email failed: {e}")
        return False


def dispatch_notifications(user_id: str, reminder_message: str, db) -> dict:
    """
    Main dispatcher. Reads user notification prefs and fires all
    configured channels. SSE is always True (handled by caller).

    Returns dict: {"sse": True, "whatsapp": bool, "email": bool}
    """
    results = {"sse": True, "whatsapp": False, "email": False}

    try:
        prefs = db.get_notification_prefs(user_id)
        if not prefs:
            logger.info(f"No notification prefs for {user_id} — SSE only")
            return results

        channels = prefs.get("channels", "sse").split(",")
        text = f"Reminder: {reminder_message}"

        if "whatsapp" in channels and prefs.get("whatsapp"):
            results["whatsapp"] = send_whatsapp(
                to_number=prefs["whatsapp"],
                message=f"\u23f0 {text}"
            )

        if "email" in channels and prefs.get("email"):
            results["email"] = send_email(
                to_address=prefs["email"],
                subject="\u23f0 Reminder \u2014 Context Assistant",
                body=text
            )

    except Exception as e:
        logger.error(f"dispatch_notifications error (non-fatal): {e}")

    return results
