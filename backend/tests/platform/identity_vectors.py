"""Independent known answers: HMAC sessions, NFKC/scrypt and ECMAScript text.

Synthetic Node crypto answers retained without the retired implementation/generators.
"""

SECRET = "synthetic-session-signing-key-only-0123456789"
A = "A:4102444800000:0.bzIaCfl-HBdi1hNUozJ1KvoX3iuNvQlU4lsMjHTTgoM"
B = "B:4102444800000:3.bnIHnDX1EThhBW28CEd3RxWE2wyCSW71gNIZKHlrt-I"
LEGACY = "A:4102444800000.C1O2RHKPjiCNBmQweN8Dixi97cbEgp9szhDF8fBxTKI"

HASH = "$scrypt$v=1$ln=15,r=8,p=1$aW5kZXBlbmRlbnQtc2FsdA==$Bjd+MjiP3fgJgtBQ7YtA+FZz32RnxkRW4AqlBrzwRIM="
PASSWORD = "Café Ａngstrom 42!"
LEGACY_HASH = "$scrypt$v=1$ln=10,r=1,p=1$aW5kZXBlbmRlbnQtc2FsdA==$7q5/DEoUyWDpbMYpdSK5qoxVH54x7p8Fcv+dWLSO2jolDKTbroESipjhjom7bpUGaeEUDC4q1k1PkuThD1MnIw=="

PASSWORD_CASES = [
    ("Café Ａngstrom 42!", HASH, True),
    ("Café Ａngstrom 42!", HASH, True),
    ("café ａngstrom 42!", HASH, False),
    ("wrong", HASH, False),
    (" legacy key length ", LEGACY_HASH, True),
    ("legacy key length", LEGACY_HASH, False),
    ("wrong", LEGACY_HASH, False),
]
ALIASES = [
    [" ＡＬＩＣＥ ", "alice"],
    ["İ", "i̇"],
    ["ΟΣ", "ος"],
    ["﻿Ana﻿", "ana"],
    ["Ana", "ana"],
    ["Straße", "straße"],
    ["Kelvin", "kelvin"],
]
IDENTIFIERS = [
    [0, "0"],
    [-0.0, "0"],
    [1, "1"],
    [0.000001, "0.000001"],
    [1e-7, "1e-7"],
    [100000000000000000000, "100000000000000000000"],
    [1e21, "1e+21"],
    [9007199254740992, "9007199254740992"],
]
