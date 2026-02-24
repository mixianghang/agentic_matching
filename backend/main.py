from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from backend.models import Task, User, Agent
from backend.storage import storage
from backend.agent_system import agent_system
from backend.auth import get_password_hash, verify_password
import uuid
import logging

logger = logging.getLogger(__name__)
import os
import secrets

app = FastAPI(title="Agentic Matching System")
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = credentials.credentials
    if not token:
        logger.warning("Empty token provided")
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        user = storage.verify_token(token)
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")
    
    if not user:
        logger.warning(f"Invalid or expired token: {token[:20]}...")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    if not user.is_active:
        logger.warning(f"Inactive user tried to access: {user.username}")
        raise HTTPException(status_code=403, detail="User account is inactive")
    
    logger.debug(f"User authenticated: {user.username}")
    return user

class CreateUserRequest(BaseModel):
    username: str
    email: str | None = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    user: User
    access_token: str
    token_type: str = "bearer"

class ThirdPartyLoginRequest(BaseModel):
    provider: str
    code: str

class ThirdPartyCallbackRequest(BaseModel):
    provider: str
    code: str
    username: str | None = None

class CreateTaskRequest(BaseModel):
    task_type: str
    description: str
    requirements: dict = None

class SendMessageRequest(BaseModel):
    task_id: str
    user_message: str

class StartNegotiationRequest(BaseModel):
    task1_id: str
    task2_id: str

def generate_token() -> str:
    return secrets.token_urlsafe(32)


def create_user_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    storage.create_token(user_id, token, expires_in_hours=24*7)
    return token

@app.post("/api/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest):
    existing_user = storage.get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    password_hash = get_password_hash(request.password)
    user = storage.create_user(
        username=request.username,
        email=request.email,
        password_hash=password_hash,
        auth_provider="local"
    )
    
    access_token = create_user_token(user.id)
    return LoginResponse(user=user, access_token=access_token)

@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    user = storage.get_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token = create_user_token(user.id)
    return LoginResponse(user=user, access_token=access_token)

@app.post("/api/auth/third-party/login")
def third_party_login(request: ThirdPartyCallbackRequest):
    if request.provider == "wechat":
        return {
            "provider": "wechat",
            "message": "WeChat login not yet implemented",
            "status": "pending"
        }
    elif request.provider == "alipay":
        return {
            "provider": "alipay", 
            "message": "Alipay login not yet implemented",
            "status": "pending"
        }
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

@app.post("/api/auth/third-party/register", response_model=LoginResponse)
def third_party_register(request: ThirdPartyCallbackRequest):
    if request.provider == "wechat":
        existing_user = storage.get_user_by_username(request.username or f"wechat_user_{request.code[:8]}")
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        user = storage.create_user(
            username=request.username or f"wechat_user_{request.code[:8]}",
            auth_provider="wechat",
            third_party_id=request.code
        )
        
        access_token = create_user_token(user.id)
        return LoginResponse(user=user, access_token=access_token)
    
    elif request.provider == "alipay":
        existing_user = storage.get_user_by_username(request.username or f"alipay_user_{request.code[:8]}")
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        user = storage.create_user(
            username=request.username or f"alipay_user_{request.code[:8]}",
            auth_provider="alipay",
            third_party_id=request.code
        )
        
        access_token = create_user_token(user.id)
        return LoginResponse(user=user, access_token=access_token)
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")


class LogoutRequest(BaseModel):
    access_token: str


@app.post("/api/auth/logout")
def logout(request: LogoutRequest):
    storage.revoke_token(request.access_token)
    return {"message": "Logged out successfully"}


@app.get("/api/users/{user_id}", response_model=User)
def get_user(user_id: str):
    user = storage.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/api/tasks/", response_model=Task)
def create_task(request: CreateTaskRequest, current_user: User = Depends(get_current_user)):
    agent = storage.create_agent(current_user.id, "task_agent")
    task = storage.create_task(
        current_user.id,
        agent.id,
        request.task_type,
        request.description,
        request.requirements
    )
    return task

@app.get("/api/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/api/tasks/", response_model=list[Task])
def get_all_tasks():
    return storage.get_all_tasks()

@app.post("/api/messages/")
def send_message(request: SendMessageRequest, current_user: User = Depends(get_current_user)):
    task = storage.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")
    user_message = agent_system.create_user_agent_interaction(request.task_id, request.user_message)
    return {"message": user_message}

@app.get("/api/tasks/{task_id}/matches/")
def get_matching_tasks(task_id: str, current_user: User = Depends(get_current_user)):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")
    matches = agent_system.find_matching_tasks(task)
    return {"matches": matches}

@app.post("/api/negotiate/")
def start_negotiation(request: StartNegotiationRequest, current_user: User = Depends(get_current_user)):
    agent_system.start_negotiation(request.task1_id, request.task2_id)
    return {"status": "negotiation started"}

@app.get("/")
def read_index():
    static_dir = os.path.join(os.path.dirname(__file__), "../static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Agentic Matching System API is running"}

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
