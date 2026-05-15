# 모든 요청에 선행되며 세션의 유효성을 검사하는 함수.
def check_session(token: str, session_dict: dict,session_lock):
    #print("todo: session_dict에서 session 토큰 조회, 없으면 False 반환, 있으면 user_id 반환")
    with session_lock:
        result = session_dict.get(token)
    if result:
        return result.user_id
    else:
        return False
    pass	#오류 회피용 코드. 나중에 다른 내용으로 채울 예정.
