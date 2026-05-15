from pydantic import BaseModel

class Session(BaseModel):
    session_token: str