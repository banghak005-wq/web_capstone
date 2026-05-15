#session_dict에서 현재 로그인된 유저 정보를 반환하는 함수.

from server_control.check_session import check_session
from server_control.response import response

def me(session: str, session_dict: dict,session_lock):
    user_id = check_session(session, session_dict,session_lock)
    if user_id:
        return response(success=True, data={"user_id": user_id})
    return response(success=False, error="session_end")
        
    
