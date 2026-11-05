"""Node-compatible signup validation; no database or cryptographic work."""

import re
import unicodedata

from opengym_platform.identity.passwords import SPACE, name_key, normalize

COMMON = {
    "1234567890",
    "0987654321",
    "12345678910",
    "123456789012",
    "1234567890123",
    "11111111111",
    "1111111111",
    "0000000000",
    "9999999999",
    "1q2w3e4r5t",
    "1q2w3e4r5t6y",
    "q1w2e3r4t5",
    "qwertyuiop",
    "qwertyuiop[]",
    "asdfghjkl;",
    "asdfghjkl",
    "zxcvbnm,./",
    "1qaz2wsx3edc",
    "qazwsxedc123",
    "qwerty123456",
    "qwertz123456",
    "azerty123456",
    "password12",
    "password123",
    "password1234",
    "password12345",
    "passw0rd123",
    "iloveyou123",
    "abcdefghij",
    "abcd123456",
    "abc1234567",
    "a1b2c3d4e5",
    "aaaaaaaaaa",
    "princess123",
    "football123",
    "baseball123",
    "sunshine123",
    "superman123",
    "welcome123",
    "welcome1234",
    "letmein123",
    "trustno1234",
    "changeme123",
    "administrator",
    "opengym123",
    "opengym1234",
    "qwerty1234567",
    "123qweasdzxc",
    "zaq12wsxcde3",
    "1q2w3e4r5t6y7u",
    "q1w2e3r4t5y6",
    "123123123123",
    "1234512345",
    "123456123456",
    "monkey12345",
    "dragon12345",
    "master12345",
    "shadow12345",
    "michael123",
    "jennifer123",
    "computer123",
    "starwars123",
    "whatever123",
    "freedom1234",
    "pokemon1234",
    "liverpool123",
    "chelsea1234",
    "arsenal1234",
    "barcelona123",
    "realmadrid123",
    "juventus123",
    "hallo12345",
    "passwort123",
    "passwort1234",
    "motdepasse123",
    "contrasena123",
    "contraseña123",
    "senha123456",
    "parola12345",
    "haslo123456",
    "wachtwoord123",
    "salasana123",
    "gymgymgym1",
}

STEMS = {
    "password",
    "passwort",
    "passw0rd",
    "motdepasse",
    "contrasena",
    "contraseña",
    "senha",
    "parola",
    "haslo",
    "wachtwoord",
    "salasana",
    "qwerty",
    "qwertz",
    "azerty",
    "qwertyuiop",
    "asdfgh",
    "letmein",
    "welcome",
    "iloveyou",
    "admin",
    "administrator",
    "changeme",
    "opengym",
    "gym",
    "workout",
    "fitness",
    "dragon",
    "monkey",
    "football",
    "baseball",
    "sunshine",
    "princess",
    "superman",
    "batman",
    "master",
    "shadow",
    "trustno",
    "abc",
    "abcdef",
    "secret",
    "login",
}

EMAIL_RE = re.compile(
    r'^[^\s@<>()[\]\\,;:"]{1,64}@(?=.{1,253}$)[^\s@<>()[\]\\,;:"._-][^\s@<>()[\]\\,;:"]*\.[^\s@<>()[\]\\,;:".]{2,}$'.replace(
        r"\s", re.escape(SPACE)
    )
)

ERRORS = {
    "too-short": "the password needs at least 10 characters",
    "too-long": "the password can have at most 256 characters",
    "too-common": "this password is too easy to guess",
    "email-invalid": "that is not an e-mail address",
    "email-taken": "another profile already uses this e-mail address",
    "name-taken": "another profile already signs in with this name",
}


def password_problem(password, name):
    if not isinstance(password, str) or len(normalize(password)) < 10:
        return "too-short"
    if len(normalize(password)) > 256:
        return "too-long"
    low = normalize(password).lower()
    stem = low
    while stem and not unicodedata.category(stem[0]).startswith("L"):
        stem = stem[1:]
    while stem and not unicodedata.category(stem[-1]).startswith("L"):
        stem = stem[:-1]
    key = name_key(name)
    if (
        len(set(low)) <= 2
        or low in COMMON
        or stem in STEMS
        or (len(key.encode("utf-16-le", "surrogatepass")) >= 6 and stem == key)
    ):
        return "too-common"
    return None


def normalize_email(value):
    email = name_key(value)
    return (
        email
        if len(email) <= 254 and ".." not in email and EMAIL_RE.fullmatch(email)
        else None
    )
