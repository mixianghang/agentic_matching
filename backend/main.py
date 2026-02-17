from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.models import Task, User, Agent
from backend.storage import storage
from backend.agent_system import agent_system
import uuid
import os

app = FastAPI(title="Agentic Matching System")

class CreateUserRequest(BaseModel):
    username: str
    email: str | None = None

class CreateTaskRequest(BaseModel):
    user_id: str
    task_type: str
    description: str
    requirements: dict = None

class SendMessageRequest(BaseModel):
    task_id: str
    user_message: str

class StartNegotiationRequest(BaseModel):
    task1_id: str
    task2_id: str

@app.post("/api/users/", response_model=User)
def create_user(request: CreateUserRequest):
    user = storage.create_user(request.username, request.email)
    return user

@app.get("/api/users/{user_id}", response_model=User)
def get_user(user_id: str):
    user = storage.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/api/tasks/", response_model=Task)
def create_task(request: CreateTaskRequest):
    user = storage.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    agent = storage.create_agent(request.user_id, "task_agent")
    task = storage.create_task(
        request.user_id,
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
def send_message(request: SendMessageRequest):
    task = storage.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_message = agent_system.create_user_agent_interaction(request.task_id, request.user_message)
    return {"message": user_message}

@app.get("/api/tasks/{task_id}/matches/")
def get_matching_tasks(task_id: str):
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    matches = agent_system.find_matching_tasks(task)
    return {"matches": matches}

@app.post("/api/negotiate/")
def start_negotiation(request: StartNegotiationRequest):
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
