"""Service layer for API tokens and webhooks."""

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.webhooks.models import ApiToken, Webhook, WebhookDelivery
from src.webhooks.schemas import VALID_EVENTS

logger = logging.getLogger("roboscope.webhooks")

# --- API Token Service ---

TOKEN_PREFIX = "rbs_"
TOKEN_BYTES = 32  # 32 random bytes → 64 hex chars


def generate_token() -> tuple[str, str, str]:
    """Generate a new API token.

    Returns (plaintext_token, token_hash, display_prefix).
    """
    random_part = secrets.token_hex(TOKEN_BYTES)
    plaintext = f"{TOKEN_PREFIX}{random_part}"
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    display_prefix = f"{TOKEN_PREFIX}{random_part[:8]}"
    return plaintext, token_hash, display_prefix


def verify_token(plaintext: str) -> str:
    """Hash a plaintext token for lookup."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def create_api_token(
    db: Session,
    name: str,
    role: str,
    user_id: int,
    expires_in_days: int | None = None,
) -> tuple[ApiToken, str]:
    """Create a new API token. Returns (token_model, plaintext_token)."""
    plaintext, token_hash, prefix = generate_token()

    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    token = ApiToken(
        name=name,
        token_hash=token_hash,
        prefix=prefix,
        role=role,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    db.refresh(token)
    return token, plaintext


def get_token_by_hash(db: Session, token_hash: str) -> ApiToken | None:
    """Look up an API token by its hash."""
    result = db.execute(
        select(ApiToken).where(ApiToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


def list_tokens(db: Session, user_id: int | None = None) -> list[ApiToken]:
    """List API tokens, optionally filtered by user."""
    stmt = select(ApiToken).where(ApiToken.is_active.is_(True))
    if user_id is not None:
        stmt = stmt.where(ApiToken.user_id == user_id)
    stmt = stmt.order_by(ApiToken.created_at.desc())
    result = db.execute(stmt)
    return list(result.scalars().all())


def revoke_token(db: Session, token_id: int) -> ApiToken | None:
    """Revoke (deactivate) an API token."""
    result = db.execute(select(ApiToken).where(ApiToken.id == token_id))
    token = result.scalar_one_or_none()
    if token:
        token.is_active = False
        db.flush()
        db.refresh(token)
    return token


def update_token_last_used(db: Session, token: ApiToken) -> None:
    """Update the last_used_at timestamp."""
    token.last_used_at = datetime.now(timezone.utc)
    db.flush()


# --- Webhook Service ---


def create_webhook(db: Session, data: dict, user_id: int) -> Webhook:
    """Create a new webhook."""
    events = data.get("events", list(VALID_EVENTS))
    # Validate events
    invalid = [e for e in events if e not in VALID_EVENTS]
    if invalid:
        raise ValueError(f"Invalid events: {', '.join(invalid)}")

    webhook = Webhook(
        name=data["name"],
        url=data["url"],
        secret=data.get("secret"),
        events=json.dumps(events),
        is_active=data.get("is_active", True),
        repository_id=data.get("repository_id"),
        created_by=user_id,
    )
    db.add(webhook)
    db.flush()
    db.refresh(webhook)
    return webhook


def update_webhook(db: Session, webhook: Webhook, data: dict) -> Webhook:
    """Update an existing webhook."""
    if "name" in data and data["name"] is not None:
        webhook.name = data["name"]
    if "url" in data and data["url"] is not None:
        webhook.url = data["url"]
    if "secret" in data:
        webhook.secret = data["secret"]
    if "events" in data and data["events"] is not None:
        invalid = [e for e in data["events"] if e not in VALID_EVENTS]
        if invalid:
            raise ValueError(f"Invalid events: {', '.join(invalid)}")
        webhook.events = json.dumps(data["events"])
    if "is_active" in data and data["is_active"] is not None:
        webhook.is_active = data["is_active"]
    if "repository_id" in data:
        webhook.repository_id = data["repository_id"]
    db.flush()
    db.refresh(webhook)
    return webhook


def get_webhook(db: Session, webhook_id: int) -> Webhook | None:
    result = db.execute(select(Webhook).where(Webhook.id == webhook_id))
    return result.scalar_one_or_none()


def list_webhooks(db: Session, repository_id: int | None = None) -> list[Webhook]:
    stmt = select(Webhook).order_by(Webhook.created_at.desc())
    if repository_id is not None:
        stmt = stmt.where(Webhook.repository_id == repository_id)
    result = db.execute(stmt)
    return list(result.scalars().all())


def delete_webhook(db: Session, webhook: Webhook) -> None:
    db.delete(webhook)
    db.flush()


def list_deliveries(
    db: Session, webhook_id: int, limit: int = 20,
) -> list[WebhookDelivery]:
    result = db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# --- Webhook Dispatch ---


def _sign_payload(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for a webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _get_matching_webhooks(
    session: Session, event: str, repository_id: int | None = None,
) -> list[Webhook]:
    """Find all active webhooks matching an event."""
    stmt = select(Webhook).where(
        Webhook.is_active.is_(True),
    )
    result = session.execute(stmt)
    webhooks = []
    for wh in result.scalars().all():
        events = json.loads(wh.events)
        if event not in events:
            continue
        # Match: global webhooks (no repo filter) or repo-specific
        if wh.repository_id is None or wh.repository_id == repository_id:
            webhooks.append(wh)
    return webhooks


def dispatch_webhook_event(
    event: str,
    payload: dict,
    repository_id: int | None = None,
) -> None:
    """Dispatch a webhook event to all matching webhooks.

    Called from background threads — uses its own DB session.
    """
    from src.database import get_sync_session

    with get_sync_session() as session:
        webhooks = _get_matching_webhooks(session, event, repository_id)
        if not webhooks:
            return

        payload_json = json.dumps(payload, default=str)

        for webhook in webhooks:
            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event=event,
                payload=payload_json,
                created_at=datetime.now(timezone.utc),
            )
            session.add(delivery)
            session.flush()

            headers = {
                "Content-Type": "application/json",
                "X-RoboScope-Event": event,
                "User-Agent": "RoboScope-Webhook/1.0",
            }
            if webhook.secret:
                signature = _sign_payload(payload_json, webhook.secret)
                headers["X-RoboScope-Signature"] = f"sha256={signature}"

            # Retry with exponential backoff (3 attempts)
            max_retries = 3
            for attempt in range(max_retries):
                start = time.monotonic()
                try:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(
                            webhook.url,
                            content=payload_json,
                            headers=headers,
                        )
                    duration_ms = int((time.monotonic() - start) * 1000)
                    delivery.status_code = resp.status_code
                    delivery.duration_ms = duration_ms

                    if resp.status_code < 400:
                        delivery.response_body = resp.text[:2000]
                        break  # Success
                    else:
                        delivery.response_body = resp.text[:2000]
                        delivery.error_message = f"HTTP {resp.status_code}"
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # 1s, 2s backoff

                except Exception as e:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    delivery.duration_ms = duration_ms
                    delivery.error_message = str(e)[:1000]
                    logger.warning(
                        "Webhook delivery failed (attempt %d/%d) to %s: %s",
                        attempt + 1, max_retries, webhook.url, e,
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)

            # Update webhook metadata
            webhook.last_triggered_at = datetime.now(timezone.utc)
            webhook.last_status_code = delivery.status_code
            session.commit()


def test_webhook(webhook: Webhook) -> dict:
    """Send a test ping to a webhook URL."""
    payload = json.dumps({
        "event": "ping",
        "webhook_id": webhook.id,
        "webhook_name": webhook.name,
        "message": "This is a test delivery from RoboScope.",
    })

    headers = {
        "Content-Type": "application/json",
        "X-RoboScope-Event": "ping",
        "User-Agent": "RoboScope-Webhook/1.0",
    }
    if webhook.secret:
        signature = _sign_payload(payload, webhook.secret)
        headers["X-RoboScope-Signature"] = f"sha256={signature}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook.url, content=payload, headers=headers)
        return {
            "success": resp.status_code < 400,
            "status_code": resp.status_code,
            "error": None if resp.status_code < 400 else f"HTTP {resp.status_code}",
        }
    except Exception as e:
        return {"success": False, "status_code": None, "error": str(e)}
