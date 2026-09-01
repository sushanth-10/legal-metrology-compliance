"""Move legacy local scan images into shared Supabase Storage."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from database import STORAGE_DIR, connect
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from server import (  # noqa: E402
    SUPABASE_STORAGE_BUCKET,
    _ensure_supabase_storage_bucket,
    _slugify_storage_object_name,
    _supabase_storage_client,
)


def _local_path(image_ref: str) -> Path:
    return (STORAGE_DIR / Path(image_ref).name).resolve()


def _upload(client: object, user_id: str, scan_id: str, filename: str, mime_type: str, data: bytes) -> str:
    safe_name = _slugify_storage_object_name(filename)
    object_key = f"{user_id}/{scan_id}/{uuid.uuid4().hex[:12]}-{safe_name}"
    response = client.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
        path=object_key,
        file=data,
        file_options={"content-type": mime_type or "application/octet-stream"},
    )
    if hasattr(response, "error") and response.error:
        raise RuntimeError(str(response.error))
    if isinstance(response, dict) and response.get("error"):
        raise RuntimeError(str(response["error"]))
    return f"{SUPABASE_STORAGE_BUCKET}/{object_key}"


def main() -> None:
    client = _supabase_storage_client()
    if not client:
        raise RuntimeError("Supabase Storage is not configured. Check SUPABASE_URL and SUPABASE_SECRET_KEY in .env.")
    _ensure_supabase_storage_bucket(client)

    migrated = 0
    skipped = 0
    failed = 0

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.scan_image_id, i.scan_id, i.image_ref, i.filename, i.mime_type,
                       i.sort_index, s.user_id
                FROM scan_images i
                JOIN scans s ON s.scan_id = i.scan_id
                WHERE i.image_ref LIKE %s
                ORDER BY i.scan_id, i.sort_index
                """,
                ("/api/uploads/%",),
            )
            image_rows = cursor.fetchall()

            for row in image_rows:
                source = _local_path(row["image_ref"])
                if not source.is_file():
                    skipped += 1
                    print(f"SKIP missing: {source.name}")
                    continue
                try:
                    filename = row["filename"] or source.name
                    mime_type = row["mime_type"] or mimetypes.guess_type(filename)[0] or "image/jpeg"
                    storage_ref = _upload(client, row["user_id"], row["scan_id"], filename, mime_type, source.read_bytes())
                    cursor.execute(
                        "UPDATE scan_images SET image_ref = %s WHERE scan_image_id = %s",
                        (storage_ref, row["scan_image_id"]),
                    )
                    if row["sort_index"] == 1:
                        cursor.execute("UPDATE scans SET image_ref = %s WHERE scan_id = %s", (storage_ref, row["scan_id"]))
                    migrated += 1
                    print(f"MIGRATED {row['scan_id']}: {filename}")
                except Exception as error:
                    failed += 1
                    print(f"FAILED {row['scan_id']}: {error}")

            cursor.execute(
                """
                SELECT s.scan_id, s.user_id, s.image_ref
                FROM scans s
                WHERE s.image_ref LIKE %s
                  AND NOT EXISTS (SELECT 1 FROM scan_images i WHERE i.scan_id = s.scan_id)
                """,
                ("/api/uploads/%",),
            )
            legacy_scan_rows = cursor.fetchall()
            for row in legacy_scan_rows:
                source = _local_path(row["image_ref"])
                if not source.is_file():
                    skipped += 1
                    print(f"SKIP missing: {source.name}")
                    continue
                try:
                    filename = source.name
                    mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
                    storage_ref = _upload(client, row["user_id"], row["scan_id"], filename, mime_type, source.read_bytes())
                    cursor.execute(
                        """
                        INSERT INTO scan_images (scan_image_id, scan_id, image_ref, filename, mime_type, sort_index)
                        VALUES (%s, %s, %s, %s, %s, 1)
                        """,
                        (f"scan_image-{uuid.uuid4().hex[:12]}", row["scan_id"], storage_ref, filename, mime_type),
                    )
                    cursor.execute("UPDATE scans SET image_ref = %s WHERE scan_id = %s", (storage_ref, row["scan_id"]))
                    migrated += 1
                    print(f"MIGRATED {row['scan_id']}: {filename}")
                except Exception as error:
                    failed += 1
                    print(f"FAILED {row['scan_id']}: {error}")

        connection.commit()

    print(f"Done. Migrated={migrated}, skipped_missing={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
