#이미지 생성 시 전달받는 사용자 정보 및 프롬프트(요청받은 작업) 클래스.

class Job:
    def __init__(self, job_id: str, user_id: str, prompt: str):
        print("todo: Job 객체 초기화 - queue_id, user_id, prompt, status 설정")
        self.job_id = job_id	# 작업 고유 ID -> 수정: 앞으로 순번표로 쓰겠습니다.
        self.user_id = user_id		# 요청한 유저 ID
        self.prompt = prompt		# 이미지 생성 프롬프트
        self.status = "waiting"		# waiting / processing / done
        self.image = None		# 완료 시 webp 이미지 저장
        self.completed_time = None # 작업 완료 시각 저장해둘것 (나중에 ack 안 보낸 작업 스스로 삭제)
