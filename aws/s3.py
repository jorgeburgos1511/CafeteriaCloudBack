import boto3
import os
from uuid import uuid4

s3 = boto3.client("s3")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")


def upload_product_image(file_content: bytes, content_type: str) -> str:
    ext = content_type.split("/")[-1]
    key = f"products/{uuid4()}.{ext}"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=file_content,
        ContentType=content_type,
    )
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return f"https://{BUCKET_NAME}.s3.{region}.amazonaws.com/{key}"


def upload_ticket_pdf(pedido_id: str, pdf_bytes: bytes) -> str:
    key = f"tickets/{pedido_id}.pdf"
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=604800,
    )
    return url
