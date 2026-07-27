import os
import logging
import asyncio
import uuid
import mimetypes
from typing import Optional
from backend.config import settings

logger = logging.getLogger(__name__)

# Module-level GCS SDK check
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    storage = None
    GCS_AVAILABLE = False


class StorageError(Exception):
    """Custom exception raised when storage operations fail."""
    pass


class StorageService:
    def __init__(self):
        # Cached singleton client instance
        self._gcs_client = None

    def _get_gcs_client(self):
        """Returns cached GCS client instance or raises StorageError."""
        if not GCS_AVAILABLE:
            raise StorageError("google-cloud-storage package is not installed in environment.")
        if self._gcs_client is None:
            self._gcs_client = storage.Client()
        return self._gcs_client

    async def save_output_image(
        self,
        local_file_path: str,
        filename: Optional[str] = None,
        subfolder: str = "outputs",
        delete_local: bool = False
    ) -> str:
        """
        Saves a single poster or Creation Agent image.
        Max size limit: 100 MB.
        """
        if not local_file_path:
            return local_file_path

        # Ensure unique filename to prevent blob collisions
        if not filename:
            filename = os.path.basename(local_file_path)
        base, ext = os.path.splitext(filename)
        if not ext:
            ext = ".png"
        unique_filename = f"{base}_{uuid.uuid4().hex[:8]}{ext}"

        if getattr(settings, "storage_type", "local").lower() == "gcs":
            return await self.upload_file_to_gcs(
                local_file_path=local_file_path,
                destination_blob_name=f"{subfolder}/{unique_filename}",
                content_type="image/png",
                max_size_bytes=100 * 1024 * 1024,  # 100 MB limit for single images
                delete_local=delete_local
            )

        return local_file_path

    async def save_bulk_zip(
        self,
        local_zip_path: str,
        zip_filename: Optional[str] = None,
        delete_local: bool = False
    ) -> str:
        """
        Saves a bulk export ZIP archive permanently.
        Max size limit: 50 GB (supports 10,000+ posters).
        Uses 8 MB resumable chunk size.
        """
        if not local_zip_path:
            return local_zip_path

        if not zip_filename:
            zip_filename = os.path.basename(local_zip_path)

        if getattr(settings, "storage_type", "local").lower() == "gcs":
            return await self.upload_file_to_gcs(
                local_file_path=local_zip_path,
                destination_blob_name=f"bulk_zips/{zip_filename}",
                content_type="application/zip",
                chunk_size=8 * 1024 * 1024,  # 8 MB chunk size for resumable multi-GB uploads
                max_size_bytes=50 * 1024 * 1024 * 1024,  # 50 GB limit for bulk ZIPs
                delete_local=delete_local
            )

        return local_zip_path

    async def upload_file_to_gcs(
        self,
        local_file_path: str,
        destination_blob_name: str,
        content_type: Optional[str] = None,
        chunk_size: Optional[int] = None,
        delete_local: bool = False,
        max_size_bytes: Optional[int] = None,
        max_retries: int = 3
    ) -> str:
        """
        Uploads a file to GCS off the main thread with resumable chunking, retries, and size checks.
        """
        if not os.path.exists(local_file_path):
            raise StorageError(f"Local file does not exist: {local_file_path}")

        file_size = os.path.getsize(local_file_path)
        if max_size_bytes and file_size > max_size_bytes:
            raise StorageError(f"File size ({file_size} bytes) exceeds maximum limit of {max_size_bytes} bytes.")

        if not content_type:
            content_type, _ = mimetypes.guess_type(local_file_path)
            if not content_type:
                content_type = "application/octet-stream"

        bucket_name = getattr(settings, "gcs_bucket_name", "")
        if not bucket_name:
            raise StorageError("GCS_BUCKET_NAME is not configured in settings.")

        # Synchronous worker running in executor thread pool
        def _do_upload():
            client = self._get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(destination_blob_name)

            if chunk_size:
                blob.chunk_size = chunk_size  # Enable resumable chunked upload

            blob.upload_from_filename(local_file_path, content_type=content_type)

            if getattr(settings, "gcs_use_signed_urls", False):
                return blob.generate_signed_url(expiration=3600 * 24 * 7)
            return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"

        # Exponential backoff retry loop
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                gcs_url = await asyncio.to_thread(_do_upload)
                logger.info(f"Successfully uploaded {local_file_path} -> GCS: {destination_blob_name}")

                if delete_local and os.path.exists(local_file_path):
                    try:
                        os.remove(local_file_path)
                        logger.info(f"Cleaned up local file: {local_file_path}")
                    except Exception as clean_err:
                        logger.warning(f"Failed to delete local file {local_file_path}: {clean_err}")

                return gcs_url
            except Exception as e:
                last_exception = e
                logger.warning(f"GCS upload attempt {attempt}/{max_retries} failed for {local_file_path}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))

        raise StorageError(f"GCS upload failed after {max_retries} attempts: {last_exception}")


storage_service = StorageService()