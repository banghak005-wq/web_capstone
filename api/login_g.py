from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests
from server_control.response import response
from server_control.create_session import create_session

GOOGLE_CLIENT_ID = "281972226742-0n2csh9se175549hnhp8ql0b5docfkr0.apps.googleusercontent.com"

def login_g(token: str, session_dict: dict,session_lock):
    try:
        id_info = google_id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        user_email = id_info.get('email')
        session_token = create_session(user_email, session_dict,session_lock)
        return response(True, {"session_token": session_token, "user_id": user_email}, None)
    except ValueError:
        return response(False, None, "login_failed")
    except Exception as e:
        print(f"Login Error: {str(e)}")
        return response(False, None, "login_failed")
