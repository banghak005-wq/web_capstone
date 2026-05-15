#제일 먼저 실행되는 파일. FastAPI 앱 실행 및 공유 자원(세션, 대기열, 작업 목록)을 초기화함.

from collections import deque
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import Response
import secrets

from api.login import login
from api.login_g import login_g
from api.logout import logout
from api.me import me
from api.join_awaiting import join_awaiting
from api.check_awaiting import check_awaiting
from api.get_result import get_result
from api.result_ack import result_ack

from models.LoginRequest import LoginRequest #로그인 basemodel
from models.Session import Session
from models.Prompt import Prompt
from models.LoginRequest_g import LoginRequest_g

from classes.QueueManager import QueueManager #대기열 관리자
from server_control.session_clear import session_clear
from server_control.job_clear import job_clear

import threading
import time
import requests
import datetime
import base64

MAX = 100

app = FastAPI()

#CORS 설정(개발 중에만 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#공유 자원
session_dict = {}			# { session_token: user_id }
queue: deque = deque()	# 대기열: Job 객체들
jobs_dict = {}			# { user_id: Job } queue_id -> user_id 로 맵핑 수정

queue_lock = threading.Lock() #만들어 놓고 안 쓰게됨;;
session_lock = threading.Lock()
job_lock = threading.Lock()


queueManager = QueueManager(MAX) #대기열 최대 길이 설정
from fastapi.responses import FileResponse
@app.get("/")
def serve_front():
    # FileResponse 대신 직접 파일 내용을 읽어 응답을 만들면서 헤더 추가
    with open("frontend.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    return Response(
        content=content, 
        media_type="text/html",
        headers={
            # 이 헤더가 구글 팝업과의 통신을 허용하게 해줍니다.
            "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
            #"Cross-Origin-Embedder-Policy": "require-corp" # 보안 오류 일으켜서 제거
        }
    )

@app.post("/login") #LoginRequest basemodel 사용 id:str pw:str
def route_login(req:LoginRequest , res: Response ):
    result = login(req.id,req.pw,session_dict,session_lock)

    if result["success"]: #data -> success 검사로 로그인 성공 판정 수정됨
        res.delete_cookie("session_token", path="/")
        res.set_cookie(
            key="session_token",
            value=result["data"]["session_token"],
            httponly=False,
            secure=True,
            samesite="Lax",
            path="/"
        )
    return result

@app.post("/login_g")
def route_login_g(req: LoginRequest_g, res: Response):
    result = login_g(req.id, session_dict, session_lock)
    
    if result["success"]:
        res.delete_cookie("session_token", path="/")
        res.set_cookie(
            key="session_token",
            value=result["data"]["session_token"],
            httponly=False,
            secure=True,
            samesite="None",
            path="/"
        )
    return result

@app.post("/logout") #여긴 좀더 고민
def route_logout(req:Session, res:Response): #Session basemodel 사용, session_token:str
    result = logout(req.session_token, session_dict,session_lock)
    res.delete_cookie(key="session_token")
    return result

@app.post("/me") # @app.get에서 @app.post로 수정
def route_me(req: Session): # Session 모델을 Body로 받기 위함
    return me(req.session_token, session_dict, session_lock)


@app.post("/join_awaiting")
def route_join_awaiting(req:Prompt, res: Response): #Prompt basemodel 사용, session_token_str,prompt:str
    return join_awaiting(req.session_token, req.prompt, session_dict, queue, jobs_dict, queueManager,session_lock,job_lock)

@app.post("/check_awaiting") #Session basemodel 사용, session_token:str
def route_check_awaiting(req:Session):
    #with session_lock:
        #print("받은 토큰:", req.session_token)
        #print("현재 세션:", session_dict.keys())
    return check_awaiting(req.session_token, session_dict, queue, jobs_dict,queueManager,session_lock,job_lock)

@app.post("/get_result") #Session basemodel 사용, session_token:str
def route_get_result(req:Session):
    return get_result(req.session_token, session_dict, jobs_dict,session_lock,job_lock)

@app.post("/result_ack") #Session basemodel 사용, session_token:str
def route_result_ack(req:Session):
    return result_ack(req.session_token, session_dict, jobs_dict,session_lock,job_lock)

def session_cleaner():
    while True:
        session_clear(session_dict,session_lock)
        time.sleep(60)  # 1분마다

def gpu_worker():
    while True:
        job = None
        # 1. 대기열에서 작업 꺼내기
        if queue:
            with job_lock: # 작업 상태 변경을 위한 락
                job = queue.popleft()
                queueManager.current = job.job_id
                job.status = "processing"

        if job:
            try:
                # 2. GPU 서버(7300)에 요청 날리기
                gpu_res = requests.post(
                    "http://localhost:7300/get_image",
                    json={"prompt": job.prompt},
                    timeout=120 # SDXL 생성 시간을 고려한 넉넉한 타임아웃
                )
                
                if gpu_res.status_code == 200:
                    # 3. 결과 저장 (WebP 바이너리 데이터)
                    job.completed_time = datetime.datetime.now()
                    job.image = base64.b64encode(gpu_res.content).decode("utf-8") 
                    job.status = "done"
                else:
                    job.status = "failed"
            except Exception as e:
                print(f"GPU Server Error: {e}")
                job.status = "error"
        else:
            time.sleep(1) # 대기열이 비어있으면 휴식

def job_cleaner():
    while True:
        job_clear(jobs_dict, job_lock)
        time.sleep(300)  # 5분마다
        

# 메인 서버 실행 시 워커 시작
threading.Thread(target=gpu_worker, daemon=True).start()
threading.Thread(target=session_cleaner, daemon=True).start()
threading.Thread(target=job_cleaner, daemon=True).start()

def main():
    pass
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)



