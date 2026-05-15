#이미지 생성 결과를 반환하는 함수.

from server_control.check_session import check_session
from server_control.response import response
from classes.job import Job

def get_result(session: str, session_dict: dict, jobs_dict: dict,session_lock,job_lock):
    
    user_id = check_session(session, session_dict,session_lock)
    if not user_id:
        return response(success=False, error="session_end")

    with job_lock:
        job = jobs_dict.get(user_id)
        if not job:
            return response(success=False, error="작업 없음")

        if job.status != "done":
            return response(success=False, error="아직 완료 안 됨")

    return response(success=True, data={"image": job.image, "prompt": job.prompt})


