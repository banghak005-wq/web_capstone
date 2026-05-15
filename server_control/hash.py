# hash.py
import os
import sys
import base64
import hashlib

ALGO = "pbkdf2_sha256"
ITERATIONS = 150_000
DKLEN = 32  # 256-bit

def make_hash(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(16)

    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
        dklen=DKLEN,
    )

    return (
        f"{ALGO}${ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}$"
        f"{base64.b64encode(dk).decode()}"
    )

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python hash.py <username> <password> [salt]")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    if len(sys.argv) >= 4:
        salt = sys.argv[3].encode("utf-8")
    else:
        salt = None

    hashed = make_hash(password, salt=salt)

    print("\n-- raw hash ---------------------------")
    print(hashed)

    print("\n-- sqlite insert -----------------------")
    print(
        "INSERT INTO users (username, pw_hash)\n"
        f"VALUES ('{username}', '{hashed}');"
    )