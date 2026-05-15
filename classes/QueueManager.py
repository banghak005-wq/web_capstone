# 대기열 순번을 관리하기 위한 클래스 입니다.
class QueueManager:
    def __init__(self,max_size):
        self.max = max_size #대기열 최대 길이 100
        #job.job_id = 25
        self.current = 0 #현재 진행중인 프로세스 몇 번인지
        self.counter =  0 #현재 대기열 맨 뒷번호

    def get_queue(self, job_id: int): #작업 id 를 주면 순번 뽑아서 반환해줍니다. 굳이 쓰기 싫으시면 따로 외부 파일에서 조작하셔도 됩니다.
        if(job_id >= self.current):
            return job_id - self.current
        else :
            return job_id + self.max - self.current
        
    
            


