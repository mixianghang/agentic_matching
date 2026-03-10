from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from backend.models import Task, User, Agent, Message
from backend.storage import storage
from backend.agent_system import agent_system
from backend.auth import get_password_hash, verify_password
from backend.sso import SSOFactory, SSOConfig
from backend.config import settings
import uuid
import logging
import os
import sys

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)
import secrets


def log_config():
    """输出配置信息（隐藏敏感信息）"""
    logger.info("=" * 50)
    logger.info("Server Configuration")
    logger.info("=" * 50)

    # LLM Configuration
    logger.info("LLM Configuration:")
    logger.info(f"  - Model: {settings.MODEL}")
    logger.info(f"  - Base URL: {settings.BASE_URL}")
    logger.info(f"  - Temperature: {settings.TEMPERATURE}")
    logger.info(f"  - Max Tokens: {settings.MAX_TOKENS}")
    logger.info(f"  - API Key: {'✓ Configured' if settings.OPENAI_API_KEY else '✗ Not configured'}")

    # Storage Configuration
    logger.info("Storage Configuration:")
    logger.info(f"  - Storage Type: {settings.STORAGE_TYPE}")
    if settings.STORAGE_TYPE == "sqlite":
        logger.info(f"  - Database URL: {settings.DATABASE_URL}")
    elif settings.STORAGE_TYPE == "postgres":
        logger.info(f"  - Host: {settings.POSTGRES_HOST}")
        logger.info(f"  - Port: {settings.POSTGRES_PORT}")
        logger.info(f"  - User: {settings.POSTGRES_USER}")
        logger.info(f"  - Database: {settings.POSTGRES_DB}")
        logger.info(f"  - Password: {'✓ Configured' if settings.POSTGRES_PASSWORD else '✗ Not configured'}")

    # Demand Definition Configuration
    logger.info("Demand Definition Configuration:")
    logger.info(f"  - Prompt Mode: {settings.DEMAND_PROMPT_MODE}")

    # SSO Configuration
    logger.info("SSO Configuration:")
    logger.info(f"  - WeChat: {'✓ Configured' if os.getenv('WECHAT_APP_ID') else '✗ Not configured'}")
    logger.info(f"  - Alipay: {'✓ Configured' if os.getenv('ALIPAY_APP_ID') else '✗ Not configured'}")

    logger.info("=" * 50)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时输出配置
    log_config()
    yield
    # 关闭时的清理工作（如果需要）


app = FastAPI(title="Agentic Matching System", lifespan=lifespan)

# SSO Configuration
SSO_CONFIGS = {
    "wechat": SSOConfig(
        app_id=os.getenv("WECHAT_APP_ID", ""),
        app_secret=os.getenv("WECHAT_APP_SECRET", ""),
        redirect_uri=os.getenv("WECHAT_REDIRECT_URI", "http://localhost:8000/api/auth/sso/wechat/callback"),
        scope="snsapi_login",
        state="wechat_auth"
    ),
    "alipay": SSOConfig(
        app_id=os.getenv("ALIPAY_APP_ID", ""),
        app_secret=os.getenv("ALIPAY_APP_SECRET", ""),
        redirect_uri=os.getenv("ALIPAY_REDIRECT_URI", "http://localhost:8000/api/auth/sso/alipay/callback"),
        scope="auth_user",
        state="alipay_auth"
    )
}
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

class UpdateTaskRequest(BaseModel):
    description: Optional[str] = None
    requirements: Optional[dict] = None
    status: Optional[str] = None

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

@app.get("/api/auth/sso/{provider}/url")
def get_sso_auth_url(provider: str):
    """Get SSO authorization URL for the specified provider."""
    if provider not in SSO_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    
    config = SSO_CONFIGS[provider]
    if not config.app_id:
        raise HTTPException(status_code=500, detail=f"{provider} SSO not configured")
    
    try:
        sso_provider = SSOFactory.get_provider(provider, config)
        auth_url = sso_provider.get_auth_url()
        return {"auth_url": auth_url, "provider": provider}
    except Exception as e:
        logger.error(f"Failed to generate auth URL for {provider}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")


@app.post("/api/auth/sso/{provider}/callback", response_model=LoginResponse)
async def sso_callback(provider: str, request: ThirdPartyCallbackRequest):
    """
    Handle SSO callback. This endpoint:
    1. Exchanges code for access token
    2. Fetches user info from provider
    3. Checks if user exists in database
       - If exists: logs in the user
       - If not: creates new user and logs in
    4. Returns the same response format as regular login
    """
    if provider not in SSO_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    
    config = SSO_CONFIGS[provider]
    if not config.app_id or not config.app_secret:
        raise HTTPException(status_code=500, detail=f"{provider} SSO not properly configured")
    
    try:
        # Get SSO provider instance
        sso_provider = SSOFactory.get_provider(provider, config)
        
        # Exchange code for access token
        access_token = await sso_provider.get_access_token(request.code)
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token from provider")
        
        # Fetch user info from provider
        user_info = await sso_provider.get_user_info(access_token)
        if not user_info or not user_info.provider_user_id:
            raise HTTPException(status_code=400, detail="Failed to obtain user info from provider")
        
        # Check if user already exists
        existing_user = storage.get_user_by_third_party_id(provider, user_info.provider_user_id)
        
        if existing_user:
            # User exists - log them in
            logger.info(f"SSO login for existing user: {existing_user.username}")
            token = create_user_token(existing_user.id)
            return LoginResponse(user=existing_user, access_token=token)
        else:
            # Create new user
            username = user_info.username or f"{provider}_user_{user_info.provider_user_id[:8]}"
            
            # Ensure username is unique
            base_username = username
            counter = 1
            while storage.get_user_by_username(username):
                username = f"{base_username}_{counter}"
                counter += 1
            
            new_user = storage.create_user(
                username=username,
                email=user_info.email,
                auth_provider=provider,
                third_party_id=user_info.provider_user_id
            )
            
            logger.info(f"Created new user from SSO: {new_user.username}")
            token = create_user_token(new_user.id)
            return LoginResponse(user=new_user, access_token=token)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSO callback failed for {provider}: {e}")
        raise HTTPException(status_code=500, detail="SSO authentication failed")


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

    welcome_message = Message(
        id=str(uuid.uuid4()),
        sender_id=agent.id,
        receiver_id=current_user.id,
        content=(
            "你好！我是你的智能助手。我可以帮您创建以下类型的需求：\n\n"
            "🏠 租房 - 找室友或出租房源\n"
            "💕 相亲 - 寻找合适的对象\n"
            "🎮 游戏 - 找队友一起开黑\n\n"
            "请告诉我您需要什么服务？"
        ),
        message_type="system",
    )
    storage.add_message_to_task(task.id, welcome_message)

    return storage.get_task(task.id)

@app.get("/api/tasks/{task_id}", response_model=Task)
def get_task(task_id: str, current_user: User = Depends(get_current_user)):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")
    return task

@app.get("/api/tasks/", response_model=list[Task])
def get_all_tasks(current_user: User = Depends(get_current_user)):
    return storage.get_tasks_by_user(current_user.id)

# TODO: partial update, e.g., appending new requirements, or update existing ones but not all
@app.put("/api/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, request: UpdateTaskRequest, current_user: User = Depends(get_current_user)):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")
    
    if request.description is not None:
        task.description = request.description
    if request.requirements is not None:
        task.requirements = request.requirements
    if request.status is not None:
        task.status = request.status
    
    updated_task = storage.update_task(task)
    return updated_task

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, current_user: User = Depends(get_current_user)):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")
    
    storage.delete_task(task_id)
    return {"message": "Task deleted successfully"}

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


@app.get("/api/tasks/{task_id}/demand_progress")
def get_demand_progress(task_id: str, current_user: User = Depends(get_current_user)):
    """获取需求定义进度"""
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this task")

    progress = agent_system.get_demand_progress(task_id)
    return progress


@app.get("/api/demand_templates")
def get_demand_templates():
    """获取所有可用的需求模板"""
    from backend.demand_templates import list_all_templates
    return {"templates": list_all_templates()}

@app.get("/")
def read_index():
    static_dir = os.path.join(os.path.dirname(__file__), "../static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Agentic Matching System API is running"}

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


