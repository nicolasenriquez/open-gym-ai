"""Independent signed COSE/WebAuthn known answers, not business document dumps.

Only shared public keys, two base credentials per algorithm and changed signed
response bytes are retained. Expected outcomes/counters stay explicit here.
No private keys or generator/runtime dependency on the retired API.
"""

import json
from copy import deepcopy
from pathlib import Path

packed = json.loads((Path(__file__).parent / "fixtures/webauthn.json").read_text())
VECTORS = {key: packed[key] for key in ("challenge", "origin", "rpId")}
VECTORS["cases"] = []
for algorithm, data in packed["algorithms"].items():
    for name in ("register", "assertion", *data["variants"]):
        kind = "register" if name.startswith("register") else "login"
        credential = deepcopy(data["register" if kind == "register" else "assertion"])
        credential["response"].update(data["variants"].get(name, {}))
        accepted = name in (
            "register",
            "register-backed-up",
            "assertion",
            "uv",
            "zero",
            "backup",
        )
        VECTORS["cases"].append(
            {
                "name": algorithm + "/" + name,
                "algorithm": algorithm,
                "kind": kind,
                "credential": credential,
                "publicKey": data["publicKey"],
                "credentialId": credential["id"],
                "expected": accepted,
                "observedCounter": 1 if name == "replay" else 0,
                "newCounter": 1
                if accepted and kind == "login" and name != "zero"
                else 0,
            }
        )
