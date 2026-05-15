from pydantic import BaseModel

class LoginRequest(BaseModel):
    id: str
    pw: str