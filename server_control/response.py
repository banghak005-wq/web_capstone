#json 형식을 반환하는 함수.

def response(success: bool, data=None, error=None):	#모든 api 요청에 대응할 수 있도록 할 것.
    return {"success": success, "data": data, "error": error}	#성공 여부, 데이터, 무슨 에러인지.
