"""
AWS S3 integration for biweekly report distribution.

Uploads a generated/uploaded report HTML to S3 and returns a public URL.
Ported from biweekly-reporter (server/index.ts `/api/upload-report`).
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

from src.utils.logger import get_logger

logger = get_logger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _get_region() -> str:
    return os.getenv("AWS_REGION", "ap-northeast-2")


def _get_bucket() -> str:
    # Separate from the MongoDB backup bucket (S3_BACKUP_BUCKET)
    return os.getenv("S3_REPORTS_BUCKET", "tokamak-reports")


def _get_s3_client():
    """Create a boto3 S3 client from environment credentials."""
    return boto3.client(
        "s3",
        region_name=_get_region(),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def upload_report_html(html: str, report_number: str) -> str:
    """
    Upload report HTML to S3 and return its public URL.

    Args:
        html: Full report HTML content.
        report_number: Report number used in the object key (e.g. "8").

    Returns:
        Public HTTPS URL of the uploaded object.

    Raises:
        RuntimeError: If required AWS configuration is missing.
        botocore.exceptions.ClientError: On S3 upload failure.
    """
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise RuntimeError(
            "AWS credentials not configured (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)."
        )

    bucket = _get_bucket()
    region = _get_region()

    # Timestamp like 2026-06-03T14-30-00 (filesystem/url safe)
    ts = datetime.now(KST).strftime("%Y-%m-%dT%H-%M-%S")
    safe_number = (report_number or "0").strip() or "0"
    s3_key = f"reports/biweekly-{safe_number}-{ts}.html"

    client = _get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=html.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )

    url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    logger.info(f"📤 Uploaded report HTML to {url} ({len(html)} bytes)")
    return url
