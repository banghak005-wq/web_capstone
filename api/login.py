#유저 로그인 처리하고 세션 쿠키를 발급하는 함수.
#쿠키는 브라우저에 저장되는 문자열 변수임.

from server_control.check_session import check_session
from server_control.create_session import create_session
from server_control.response import response
from server_control.check_hash import check_user_password

def login(id: str, pw: str, session_dict: dict,session_lock):
    if check_user_password(id, pw):
        token = create_session(id, session_dict,session_lock)

        return response(
            success=True,
            data={
                "session_token": token,
                "user_id": id
            }
        )
    else:
        return response(success=False, error="login_failed")


