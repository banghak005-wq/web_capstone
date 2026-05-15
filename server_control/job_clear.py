from datetime import datetime, timedelta

def job_clear(jobs_dict: dict, job_lock):
    now = datetime.now()
    expire_time = timedelta(minutes=15)

    to_delete = []

    with job_lock:
        copied = list(jobs_dict.items())

    for user_id, job in copied:
        if job.status == "done" and job.completed_time:
            if now - job.completed_time > expire_time:
                to_delete.append(user_id)

    with job_lock:
        for user_id in to_delete:
            jobs_dict.pop(user_id, None)