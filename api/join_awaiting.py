#이미지 생성 요청을 대기열에 등록하는 함수.

from collections import deque
from server_control.check_session import check_session 
from server_control.response import response
from classes.job import Job
from classes.QueueManager import QueueManager


def join_awaiting(session: str, prompt: str, session_dict: dict, queue: deque, jobs_dict: dict, queue_manager: QueueManager,session_lock,job_lock):
    user_id = check_session(session, session_dict,session_lock) #세션 확인.
    if not user_id: #check_session 실패 시 세션 에러 반환.
        return response(success = False, error = "세션 만료됨.")
    with job_lock:
        if user_id in jobs_dict:
            return response(success=False, error="이미 추가됨.")

        job_id = queue_manager.counter
        queue_manager.counter = (queue_manager.counter + 1) % queue_manager.max
        job = Job(job_id=job_id, user_id=user_id, prompt=prompt)
        queue.append(job)
        jobs_dict[user_id] = job

    queue_position = queue_manager.get_queue(job.job_id) #대기 순서 조회.
    print(f"[join_awaiting] 등록 완료 user_id={user_id}, job_id={job_id}, 대기순번={queue_position}")
    return response(success = True, data = {"job_id": job_id, "queue_position": queue_position})
