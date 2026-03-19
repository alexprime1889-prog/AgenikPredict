"""
Artifact storage abstraction.

Provides a single interface for project/report/simulation artifacts across:
- local filesystem
- shared filesystem
- S3-compatible object storage with local scratch cache
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import uuid
from typing import Iterable, Optional

from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from ..config import Config
from ..utils.logger import get_logger


logger = get_logger("agenikpredict.artifacts")


PROJECT_NAMESPACE = "projects"
REPORT_NAMESPACE = "reports"
SIMULATION_NAMESPACE = "simulations"


class ArtifactStoreError(RuntimeError):
    """Raised when the configured artifact backend is unavailable."""


class BaseArtifactStore:
    def ensure_namespace(self, namespace: str) -> str:
        raise NotImplementedError

    def get_resource_dir(self, namespace: str, resource_id: str, *, ensure: bool = False, sync: bool = False) -> str:
        raise NotImplementedError

    def sync_resource(self, namespace: str, resource_id: str) -> str:
        raise NotImplementedError

    def flush_resource(self, namespace: str, resource_id: str) -> str:
        raise NotImplementedError

    def delete_resource(self, namespace: str, resource_id: str) -> bool:
        raise NotImplementedError

    def list_resource_ids(self, namespace: str) -> list[str]:
        raise NotImplementedError

    def probe(self) -> dict:
        raise NotImplementedError


class LocalArtifactStore(BaseArtifactStore):
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def _namespace_dir(self, namespace: str) -> str:
        return os.path.join(self.root, namespace)

    def _resource_dir(self, namespace: str, resource_id: str) -> str:
        return os.path.join(self._namespace_dir(namespace), resource_id)

    def ensure_namespace(self, namespace: str) -> str:
        path = self._namespace_dir(namespace)
        os.makedirs(path, exist_ok=True)
        return path

    def get_resource_dir(self, namespace: str, resource_id: str, *, ensure: bool = False, sync: bool = False) -> str:
        if sync:
            path = self.sync_resource(namespace, resource_id)
            if ensure:
                os.makedirs(path, exist_ok=True)
            return path
        path = self._resource_dir(namespace, resource_id)
        if ensure:
            os.makedirs(path, exist_ok=True)
        return path

    def sync_resource(self, namespace: str, resource_id: str) -> str:
        path = self._resource_dir(namespace, resource_id)
        if os.path.exists(path):
            return path
        return path

    def flush_resource(self, namespace: str, resource_id: str) -> str:
        return self._resource_dir(namespace, resource_id)

    def delete_resource(self, namespace: str, resource_id: str) -> bool:
        path = self._resource_dir(namespace, resource_id)
        if not os.path.exists(path):
            return False
        shutil.rmtree(path)
        return True

    def list_resource_ids(self, namespace: str) -> list[str]:
        root = self.ensure_namespace(namespace)
        ids = []
        for name in os.listdir(root):
            if name.startswith("."):
                continue
            if os.path.isdir(os.path.join(root, name)):
                ids.append(name)
        return sorted(ids)

    def probe(self) -> dict:
        os.makedirs(self.root, exist_ok=True)
        probe_dir = tempfile.mkdtemp(prefix="artifact-probe-", dir=self.root)
        try:
            probe_path = os.path.join(probe_dir, "probe.txt")
            with open(probe_path, "w", encoding="utf-8") as f:
                f.write("ok")
            with open(probe_path, "r", encoding="utf-8") as f:
                if f.read() != "ok":
                    raise ArtifactStoreError("Artifact probe read mismatch")
            return {
                "mode": Config.ARTIFACT_STORAGE_MODE,
                "root": self.root,
                "writable": True,
            }
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)


class ObjectArtifactStore(BaseArtifactStore):
    INLINE_PUT_OBJECT_MAX_BYTES = 8 * 1024 * 1024

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        scratch_root: str,
        region: str,
        endpoint_url: Optional[str],
        access_key_id: str,
        secret_access_key: str,
        force_path_style: bool,
    ):
        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.scratch_root = os.path.abspath(scratch_root)
        self.region = region
        self.endpoint_url = endpoint_url or None
        self.force_path_style = force_path_style
        self._resource_locks: dict[tuple[str, str], threading.RLock] = {}
        self._resource_locks_guard = threading.Lock()
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=BotoConfig(
                connect_timeout=Config.ARTIFACT_OBJECT_CONNECT_TIMEOUT_SECONDS,
                read_timeout=Config.ARTIFACT_OBJECT_READ_TIMEOUT_SECONDS,
                retries={"max_attempts": 2, "mode": "standard"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                s3={"addressing_style": "path" if force_path_style else "auto"},
            ),
        )

    def _namespace_dir(self, namespace: str) -> str:
        return os.path.join(self.scratch_root, namespace)

    def _resource_dir(self, namespace: str, resource_id: str) -> str:
        return os.path.join(self._namespace_dir(namespace), resource_id)

    def _prefix_for(self, namespace: str, resource_id: str = "", relative_path: str = "") -> str:
        parts = [p.strip("/") for p in (self.prefix, namespace, resource_id, relative_path) if p]
        return "/".join(parts)

    def _resource_lock(self, namespace: str, resource_id: str) -> threading.RLock:
        key = (namespace, resource_id)
        with self._resource_locks_guard:
            lock = self._resource_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._resource_locks[key] = lock
            return lock

    def ensure_namespace(self, namespace: str) -> str:
        path = self._namespace_dir(namespace)
        os.makedirs(path, exist_ok=True)
        return path

    def get_resource_dir(self, namespace: str, resource_id: str, *, ensure: bool = False, sync: bool = False) -> str:
        if sync:
            path = self.sync_resource(namespace, resource_id)
            if ensure:
                os.makedirs(path, exist_ok=True)
            return path
        path = self._resource_dir(namespace, resource_id)
        if ensure:
            os.makedirs(path, exist_ok=True)
        return path

    def _list_remote_objects(self, prefix: str) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                key = obj.get("Key")
                if key:
                    keys.append(key)
        return keys

    def _upload_local_file(self, local_path: str, remote_key: str):
        """
        Upload a local artifact to object storage.

        Small runtime artifacts are uploaded via put_object with in-memory bytes
        to avoid non-seekable streaming retry issues seen with some S3-compatible
        backends during frequent run-state flushes.
        """
        file_size = os.path.getsize(local_path)
        if file_size <= self.INLINE_PUT_OBJECT_MAX_BYTES:
            with open(local_path, "rb") as file_obj:
                payload = file_obj.read()
            self._client.put_object(Bucket=self.bucket, Key=remote_key, Body=payload)
            return

        self._client.upload_file(local_path, self.bucket, remote_key)

    def sync_resource(self, namespace: str, resource_id: str) -> str:
        with self._resource_lock(namespace, resource_id):
            local_dir = self.get_resource_dir(namespace, resource_id, ensure=True, sync=False)
            prefix = self._prefix_for(namespace, resource_id)
            remote_keys = self._list_remote_objects(prefix)
            remote_rel_paths: set[str] = set()

            for key in remote_keys:
                relative = key[len(prefix):].lstrip("/")
                if not relative or relative.endswith("/"):
                    continue
                remote_rel_paths.add(relative)
                local_path = os.path.join(local_dir, relative)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self._client.download_file(self.bucket, key, local_path)

            for root, _, files in os.walk(local_dir):
                for name in files:
                    local_path = os.path.join(root, name)
                    relative = os.path.relpath(local_path, local_dir)
                    if relative not in remote_rel_paths:
                        os.remove(local_path)

            for root, dirs, _ in os.walk(local_dir, topdown=False):
                for name in dirs:
                    dir_path = os.path.join(root, name)
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)

            return local_dir

    def flush_resource(self, namespace: str, resource_id: str) -> str:
        with self._resource_lock(namespace, resource_id):
            local_dir = self.get_resource_dir(namespace, resource_id, ensure=False, sync=False)
            if not os.path.exists(local_dir):
                return local_dir

            prefix = self._prefix_for(namespace, resource_id)
            remote_keys = self._list_remote_objects(prefix)
            remote_rel_to_key = {
                key[len(prefix):].lstrip("/"): key
                for key in remote_keys
                if key[len(prefix):].lstrip("/") and not key.endswith("/")
            }
            local_rel_paths: set[str] = set()

            for root, _, files in os.walk(local_dir):
                for name in files:
                    local_path = os.path.join(root, name)
                    relative = os.path.relpath(local_path, local_dir).replace(os.sep, "/")
                    local_rel_paths.add(relative)
                    remote_key = self._prefix_for(namespace, resource_id, relative)
                    self._upload_local_file(local_path, remote_key)

            delete_keys = [remote_rel_to_key[rel] for rel in (set(remote_rel_to_key) - local_rel_paths)]
            if delete_keys:
                for i in range(0, len(delete_keys), 1000):
                    batch = delete_keys[i:i + 1000]
                    self._client.delete_objects(
                        Bucket=self.bucket,
                        Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                    )

            return local_dir

    def delete_resource(self, namespace: str, resource_id: str) -> bool:
        with self._resource_lock(namespace, resource_id):
            local_dir = self._resource_dir(namespace, resource_id)
            if os.path.exists(local_dir):
                shutil.rmtree(local_dir, ignore_errors=True)

            prefix = self._prefix_for(namespace, resource_id)
            keys = self._list_remote_objects(prefix)
            if not keys:
                return False

            for i in range(0, len(keys), 1000):
                batch = keys[i:i + 1000]
                self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                )
            return True

    def list_resource_ids(self, namespace: str) -> list[str]:
        prefix = self._prefix_for(namespace)
        paginator = self._client.get_paginator("list_objects_v2")
        ids: set[str] = set()
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{prefix}/", Delimiter="/"):
            for entry in page.get("CommonPrefixes", []) or []:
                raw = entry.get("Prefix", "")
                resource_id = raw[len(f"{prefix}/"):].strip("/")
                if resource_id:
                    ids.add(resource_id)
        return sorted(ids)

    def probe(self) -> dict:
        probe_key = self._prefix_for("_probes", uuid.uuid4().hex, "probe.txt")
        try:
            self._client.put_object(Bucket=self.bucket, Key=probe_key, Body=b"ok")
            obj = self._client.get_object(Bucket=self.bucket, Key=probe_key)
            if obj["Body"].read() != b"ok":
                raise ArtifactStoreError("Object-store probe read mismatch")
            self._client.delete_object(Bucket=self.bucket, Key=probe_key)
        except (ClientError, BotoCoreError) as exc:
            raise ArtifactStoreError(f"Object-store probe failed: {exc}") from exc
        return {
            "mode": Config.ARTIFACT_STORAGE_MODE,
            "bucket": self.bucket,
            "prefix": self.prefix,
            "scratch_root": self.scratch_root,
            "endpoint_url": self.endpoint_url,
            "writable": True,
        }


_store_lock = threading.Lock()
_store_instance: Optional[BaseArtifactStore] = None


def get_artifact_store() -> BaseArtifactStore:
    global _store_instance

    if _store_instance is not None:
        return _store_instance

    with _store_lock:
        if _store_instance is not None:
            return _store_instance

        if Config.ARTIFACT_STORAGE_MODE in {"local", "shared_fs"}:
            _store_instance = LocalArtifactStore(Config.ARTIFACT_ROOT)
            return _store_instance

        if Config.ARTIFACT_STORAGE_MODE == "object_store":
            _store_instance = ObjectArtifactStore(
                bucket=Config.ARTIFACT_OBJECT_BUCKET,
                prefix=Config.ARTIFACT_OBJECT_PREFIX,
                scratch_root=Config.ARTIFACT_SCRATCH_DIR,
                region=Config.ARTIFACT_OBJECT_REGION,
                endpoint_url=Config.ARTIFACT_OBJECT_ENDPOINT_URL,
                access_key_id=Config.ARTIFACT_OBJECT_ACCESS_KEY_ID,
                secret_access_key=Config.ARTIFACT_OBJECT_SECRET_ACCESS_KEY,
                force_path_style=Config.ARTIFACT_OBJECT_FORCE_PATH_STYLE,
            )
            return _store_instance

        raise ArtifactStoreError(f"Unsupported artifact storage mode: {Config.ARTIFACT_STORAGE_MODE}")


def reset_artifact_store():
    global _store_instance
    with _store_lock:
        _store_instance = None
