#현재 세션 목록에서 세션 제거하는 함수. 그게 로그아웃임.
#세션은 로그인 된 상태인데, 만료될 수 있고, 토큰이나 쿠키와는 별개임.

from server_control.check_session import check_session
from server_control.remove_session import remove_session
from server_control.response import response

def logout(session: str, session_dict: dict,session_lock):
    print("todo: check_session으로 세션 유효성 확인 후 remove_session 호출하여 세션 제거")
    if check_session(session,session_dict,session_lock):
        with session_lock:
            session_dict.pop(session, None)
        return response(success=True,data = "logged_out")
    else:
        return response(success=False,data = None,error="session_end")
