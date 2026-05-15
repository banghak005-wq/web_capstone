#새 세션을 생성 후 session_dict에 추가하는 함수.

import uuid	#파이썬 기본 라이브러리.
from classes.session import Session
import secrets

def create_session(user_id: str, session_dict: dict,session_lock):
    print("todo: uuid로 토큰 생성, Session 객체 만들어서 session_dict에 추가 후 토큰 반환")	#토큰은 무작위 생성된 문자열 변수임.
    token = secrets.token_urlsafe(32)
    session = Session(token,user_id)
    with session_lock:
        session_dict[token] = session #추가 완료
    return token #예정대로 토큰 반환 그런데 어디에 쓰려고 했는지 기억이 안 남
    pass
