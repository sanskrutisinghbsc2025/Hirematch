
import hashlib
from typing import BinaryIO, Union


def compute_file_hash(content: Union[bytes, BinaryIO]) -> str:
    hasher = hashlib.sha256()

    if isinstance(content, bytes):
        hasher.update(content)
    else:
        orig_pos = 0
        if hasattr(content, "seek") and hasattr(content, "tell"):
            orig_pos = content.tell()
            content.seek(0)

        chunk = content.read(65536)
        while chunk:
            hasher.update(chunk)
            chunk = content.read(65536)

        if hasattr(content, "seek"):
            content.seek(orig_pos)

    return hasher.hexdigest()
