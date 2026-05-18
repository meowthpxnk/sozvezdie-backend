from __future__ import annotations

import asyncio
from functools import partial
from io import BytesIO
from urllib.parse import urlparse
from uuid import UUID, uuid4

from minio import Minio


class MediaClient:
    def __init__(self, uri: str) -> None:
        parsed = urlparse(uri)

        self.bucket_name = parsed.path.lstrip("/")

        self.client = Minio(
            endpoint=parsed.netloc.split("@")[-1],
            access_key=parsed.username,
            secret_key=parsed.password,
            secure=parsed.scheme == "https",
        )

    async def _run(self, func, *args, **kwargs):
        return await asyncio.to_thread(partial(func, *args, **kwargs))

    @staticmethod
    def _object_name(image_id: str) -> str:
        UUID(image_id)
        return image_id

    async def ensure_bucket(self) -> None:
        exists = await self._run(
            self.client.bucket_exists,
            self.bucket_name,
        )

        if not exists:
            await self._run(
                self.client.make_bucket,
                self.bucket_name,
            )

    async def upload_image(
        self,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        image_uuid = str(uuid4())
        data = BytesIO(image_bytes)

        await self._run(
            self.client.put_object,
            bucket_name=self.bucket_name,
            object_name=self._object_name(image_uuid),
            data=data,
            length=len(image_bytes),
            content_type=content_type,
        )
        return image_uuid

    async def download_image(
        self,
        image_id: str,
    ) -> bytes:
        response = await self._run(
            self.client.get_object,
            bucket_name=self.bucket_name,
            object_name=self._object_name(image_id),
        )

        try:
            return await self._run(response.read)
        finally:
            response.close()
            response.release_conn()

    async def delete_image(self, image_id: str) -> None:
        await self._run(
            self.client.remove_object,
            bucket_name=self.bucket_name,
            object_name=self._object_name(image_id),
        )
