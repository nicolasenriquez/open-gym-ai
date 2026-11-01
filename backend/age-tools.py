"""Build-only fetch of the pinned, standard age executables (never runtime IO)."""

import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

pin = json.loads(Path("versions.json").read_text())["age"]
with urllib.request.urlopen(pin["url"], timeout=60) as response:
    archive = response.read(32 * 1024 * 1024)
if hashlib.sha256(archive).hexdigest() != pin["sha256"]:
    raise ValueError("AGE_ASSET_DIGEST_MISMATCH")
root = Path("/tmp/age-tools")
root.mkdir(mode=0o700)
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
    for name in ("age", "age-keygen"):
        member = source.getmember(f"age/{name}")
        if not member.isfile():
            raise ValueError("AGE_ASSET_TYPE_INVALID")
        with source.extractfile(member) as stream:
            (root / name).write_bytes(stream.read())
        (root / name).chmod(0o555)
