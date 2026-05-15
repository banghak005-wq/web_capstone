import sqlite3
import base64
import hashlib
import hmac
#해시를 db에서 꺼내와서 검증하는 함수
DB_PATH = "database/users.db" 

def check_user_password(username: str, password: str) -> bool:
    # 1) DB에서 해시 가져오기
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        "SELECT pw_hash FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    con.close()

    if not row:
        return False  # 유저 없음

    stored = row[0]

    # 2) 해시 파싱
    # 포맷: pbkdf2_sha256$iterations$salt_b64$hash_b64
    try:
        algo, iters_s, salt_b64, hash_b64 = stored.split("$", 3)
        iters = int(iters_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except Exception:
        return False  # DB 값 깨졌거나 포맷 이상

    # 3) 같은 조건으로 재해시
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iters,
        dklen=len(expected),
    )

    # 4) 비교
    return hmac.compare_digest(dk, expected)