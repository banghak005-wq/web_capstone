#대기열 상태 확인 후 현재 작업 진행 상황을 반환하는 함수.

from collections import deque	#collections는 튜플이나 dict같은 자료형이 있는 파이썬 라이브러리.
from server_control.check_session import check_session
from server_control.response import response
from classes import QueueManager

def check_awaiting(session: str, session_dict: dict, queue: deque, jobs_dict: dict,queue_manager: QueueManager,session_lock,job_lock):
    print("todo: 세션 확인 후 해당 유저의 작업이 대기열 몇 번째인지 확인, status(waiting/processing/done) 반환") #idle 필요 없음
    user_id = check_session(session, session_dict,session_lock) #세션 확인. join_awaiting.py와 같음.
    if not user_id:
        return response(success = False, error = "세션 만료됨.")
        
    with job_lock:
        if user_id not in jobs_dict: #진행 중인 작업 없음.
            return response(success = True, data = {"status": "waiting"})
        job = jobs_dict[user_id] #Job 객체 가져오기.

        if job.status == "done": #작업 완료됨.
            return response(success = True, data = {"status": "done", "job_id": job.job_id})
        
        if job.status == "processing": #작업 처리 중.
            return response(success = True, data = {"status": "processing", "queue_position": 0})
        
        queue_position = queue_manager.get_queue(job.job_id) #유저의 작업이 대기열 몇 번째인지 확인.
        return response(success = True, data = {"status": "waiting", "queue_position": queue_position})
