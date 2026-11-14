"""Project-scoped, content-addressed experiment artifacts in GridFS."""
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from gridfs import GridFSBucket
from gridfs.errors import NoFile

from platform_api.models import Artifact

CHUNK = 4 * 1024 * 1024
MAX_BYTES = 512 * 1024 * 1024


def digest(file):
    value = sha256()
    while block := file.read(CHUNK):
        value.update(block)
    file.seek(0)
    return value.hexdigest()


class Artifacts:
    def __init__(self, db):
        self.bucket = GridFSBucket(db, bucket_name="artifacts", chunk_size_bytes=CHUNK)
        self.files = db["artifacts.files"]

    def check(self, who, artifact):
        row = self.files.find_one({"metadata.project_id": who.project_id,
                                   "metadata.sha256": artifact.sha256, "filename": artifact.filename,
                                   "length": artifact.bytes}, {"_id": 1})
        if not row:
            raise HTTPException(404, "artifact_not_found")
        return row["_id"]

    def put(self, who, filename, file):
        if who.role not in {"maintainer", "publisher"}:
            raise HTTPException(403, "publish_denied")
        size = file.seek(0, 2)
        file.seek(0)
        if not 0 < size <= MAX_BYTES:
            raise HTTPException(413, "unsupported_artifact_size")
        artifact = Artifact(filename=filename, sha256=digest(file), bytes=size)
        try:
            self.check(who, artifact)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            self.bucket.upload_from_stream_with_id(str(uuid4()), filename, file,
                metadata={"project_id": who.project_id, "sha256": artifact.sha256})
        return artifact

    def open(self, who, artifact):
        try:
            return self.bucket.open_download_stream(self.check(who, artifact))
        except NoFile:
            raise HTTPException(404, "artifact_not_found") from None
