from pydantic import BaseModel

class Prompt(BaseModel):
    session_token: str
    prompt: str