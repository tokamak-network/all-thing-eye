"""
AWS SES integration for biweekly report distribution.

Sends HTML emails (test sends + batched broadcast to subscribers).
Ported from biweekly-reporter (server/index.ts `/api/send-test-email` and
`/api/send-to-all`). Batching mirrors the original: 10 recipients per batch
with a 1-second delay between batches to stay under SES rate limits.
"""

import os
import time
from typing import Iterable

import boto3

from src.utils.logger import get_logger

logger = get_logger(__name__)

BATCH_SIZE = 10  # Below the SES default send rate (e.g. 14/sec)
BATCH_DELAY_SECONDS = 1


def _get_region() -> str:
    return os.getenv("AWS_REGION", "ap-northeast-2")


def _get_sender() -> str:
    sender = os.getenv("SENDER_EMAIL_ADDRESS")
    if not sender:
        raise RuntimeError("SENDER_EMAIL_ADDRESS is not configured.")
    return sender


def _get_ses_client():
    """Create a boto3 SES client from environment credentials."""
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise RuntimeError(
            "AWS credentials not configured (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)."
        )
    return boto3.client(
        "ses",
        region_name=_get_region(),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def send_email(to: list[str], subject: str, html: str) -> None:
    """
    Send a single HTML email to one or more To: recipients.

    Used for test sends. Raises on failure.
    """
    if not to:
        raise ValueError("Recipient list is empty.")

    client = _get_ses_client()
    client.send_email(
        Source=_get_sender(),
        Destination={"ToAddresses": list(to)},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html}},
        },
    )
    logger.info(f"📧 Sent email to {len(to)} recipient(s): {', '.join(to)}")


def send_batch(recipients: list[str], subject: str, html: str) -> None:
    """
    Send a single BCC batch (raises on failure).

    Used by the progress-tracked broadcast (`/send-all`) which loops batches
    itself so it can persist per-batch progress to MongoDB between sends.
    """
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return
    client = _get_ses_client()
    client.send_email(
        Source=_get_sender(),
        Destination={"BccAddresses": recipients},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html}},
        },
    )


def send_bulk(recipients: Iterable[str], subject: str, html: str) -> dict:
    """
    Send an HTML email to many subscribers using BCC batches.

    Recipients are chunked into BATCH_SIZE groups (BCC) with a delay between
    batches. Returns a summary dict. Designed to run inside a FastAPI
    BackgroundTask so the request returns immediately.

    Returns:
        {"total": int, "sent": int, "failed": int, "errors": [str]}
    """
    recipients = [r.strip() for r in recipients if r and r.strip()]
    summary = {"total": len(recipients), "sent": 0, "failed": 0, "errors": []}

    if not recipients:
        logger.warning("send_bulk called with no recipients.")
        return summary

    client = _get_ses_client()
    sender = _get_sender()

    for i in range(0, len(recipients), BATCH_SIZE):
        batch = recipients[i : i + BATCH_SIZE]
        try:
            client.send_email(
                Source=sender,
                Destination={"BccAddresses": batch},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": html}},
                },
            )
            summary["sent"] += len(batch)
            logger.info(f"✅ Sent batch starting at index {i} ({len(batch)} recipients).")
        except Exception as e:  # noqa: BLE001 - record and continue to next batch
            summary["failed"] += len(batch)
            summary["errors"].append(f"batch@{i}: {e}")
            logger.error(f"❌ Failed batch starting at index {i}: {e}")

        # Delay between batches (skip after the last one)
        if i + BATCH_SIZE < len(recipients):
            time.sleep(BATCH_DELAY_SECONDS)

    logger.info(
        f"📨 Bulk send complete: {summary['sent']}/{summary['total']} sent, "
        f"{summary['failed']} failed."
    )
    return summary
