#로그인 시 발급할 세션 클래스.

from datetime import datetime

class Session:
    def __init__(self, token: str, user_id: str):
        print("todo: Session 객체 초기화 - token, user_id, 생성 시각 설정")
        self.token = token			# 세션 토큰
        self.user_id = user_id			# 맵핑된 유저 ID
        self.created_at = datetime.now()	# 세션 생성 시각
