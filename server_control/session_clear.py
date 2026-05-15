from datetime import datetime, timedelta
from server_control.remove_session import remove_session #이거 굳이 필요 없어서 갖다버림

def session_clear(session_dict: dict,session_lock):
    print("todo: 일정 시간이 지난 세션 청소, 일단 3시간 지난 것 청소")
    now = datetime.now()
    expire_time = timedelta(hours = 3)
    #삭제 대상만 모음
    to_delete = []

    with session_lock:
        copied = list(session_dict.items())
    for token, session in copied:
        if session and (now - session.created_at > expire_time):
            to_delete.append(token)

    with session_lock:
        for token in to_delete:
            session_dict.pop(token,None)
