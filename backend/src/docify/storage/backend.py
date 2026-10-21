"""Object storage for the repo cache (tarballs). S3 in the cloud, a folder locally (D24)."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Protocol

from docify.config import get_settings


class Storage(Protocol):
    async def put_file(self, key: str, path: Path) -> None: ...
    async def get_file(self, key: str, dest: Path) -> bool: ...
    async def delete_prefix(self, prefix: str) -> None: ...


def _safe_key(key: str) -> str:
    if key.startswith("/") or ".." in key.split("/"):
        raise ValueError("invalid storage key")
    return key


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / _safe_key(key)

    async def put_file(self, key: str, path: Path) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, path, dest)

    async def get_file(self, key: str, dest: Path) -> bool:
        src = self._path(key)
        if not src.exists():
            return False
        await asyncio.to_thread(shutil.copyfile, src, dest)
        return True

    async def delete_prefix(self, prefix: str) -> None:
        target = self._path(prefix.rstrip("/"))
        if target.is_dir():
            await asyncio.to_thread(shutil.rmtree, target, True)
        elif target.exists():
            os.remove(target)


class S3Storage:
    def __init__(self, bucket: str, region: str) -> None:
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    async def put_file(self, key: str, path: Path) -> None:
        await asyncio.to_thread(self.client.upload_file, str(path), self.bucket, _safe_key(key))

    async def get_file(self, key: str, dest: Path) -> bool:
        def _get() -> bool:
            try:
                with open(dest, "wb") as fh:
                    obj = self.client.get_object(Bucket=self.bucket, Key=_safe_key(key))
                    shutil.copyfileobj(obj["Body"], fh)
                return True
            except self.client.exceptions.NoSuchKey:
                return False

        return await asyncio.to_thread(_get)

    async def delete_prefix(self, prefix: str) -> None:
        def _delete() -> None:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=_safe_key(prefix)):
                keys: list[Any] = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if keys:
                    self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})

        await asyncio.to_thread(_delete)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage(s.s3_repo_cache_bucket, s.aws_region) if s.storage_backend == "s3" \
            else LocalStorage(s.local_storage_dir)
    return _storage
