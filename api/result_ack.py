#클라이언트가 결과 수신을 확인했을 때 해당 작업을 메모리에서 삭제하는 함수.

from server_control.check_session import check_session
from server_control.response import response

def result_ack(session: str, session_dict: dict, jobs_dict: dict,session_lock,job_lock):
    print("todo: 세션 확인 후 jobs_dict에서 해당 user_id의 Job 삭제")
    #그냥 todo 그대로 참고해서 코딩하면 될 것 같습니다.
    user_id = check_session(session,session_dict,session_lock)
    with job_lock:
        if user_id:
            jobs_dict.pop(user_id)
            return response(success=True)
    return response(success=False, error="todo")
