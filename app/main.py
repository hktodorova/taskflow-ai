import time
from collections import defaultdict, deque
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy.orm import Session
from .auth import create_access_token, get_current_user, require_role
from .config import get_settings
from .database import get_db
from .models import User
from .repository import ActivityRepository, JobRepository, NotificationRepository, ProjectRepository, RepositoryConflictError, TaskRepository, TeamRepository, UserRepository
from .schemas import (
    ActivityRead,
    AIRecommendationRead,
    AnalyticsRead,
    CommentCreate,
    DashboardRead,
    DependencyCreate,
    EmailCreate,
    EmailRead,
    JobCreate,
    JobRead,
    LoginRequest,
    PlanRead,
    ProjectCreate,
    ProjectRead,
    SubTaskCreate,
    SubTaskRead,
    TaskCreate,
    TaskRead,
    TaskUpdate,
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamRead,
    TokenRead,
    UserCreate,
    UserRead,
)
from .service import (
    ActivityService,
    AuthError,
    AuthService,
    DependencyError,
    JobService,
    NotificationService,
    ProjectNotFoundError,
    ProjectService,
    SubTaskNotFoundError,
    TaskNotFoundError,
    TaskService,
    TeamNotFoundError,
    TeamService,
    UserNotFoundError,
    UserService,
)

settings = get_settings()
app = FastAPI(title="TaskFlow AI Enterprise", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    """Bearer auth for Swagger UI."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="TaskFlow AI Enterprise",
        version="1.0.0",
        description="Task management API with auth, teams, projects and analytics.",
        routes=app.routes,
    )

    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste the token as: Bearer <access_token>"
    }

    public_paths = {
        "/health",
        "/auth/register",
        "/auth/login",
        "/openapi.json",
        "/docs",
        "/redoc"
    }

    for path, methods in openapi_schema.get("paths", {}).items():
        if path not in public_paths:
            for operation in methods.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"BearerAuth": []}])

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

_login_attempts: defaultdict[str, deque] = defaultdict(deque)
_LOGIN_LIMIT = 10
_LOGIN_WINDOW = 60


def _check_login_rate(ip: str) -> None:
    now = time.monotonic()
    bucket = _login_attempts[ip]
    while bucket and bucket[0] < now - _LOGIN_WINDOW:
        bucket.popleft()
    if len(bucket) >= _LOGIN_LIMIT:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    bucket.append(now)


@app.exception_handler(RepositoryConflictError)
def repository_conflict_handler(_, exc: RepositoryConflictError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


def repos(db: Session = Depends(get_db)):
    return {
        "users": UserRepository(db), "teams": TeamRepository(db), "projects": ProjectRepository(db),
        "tasks": TaskRepository(db), "activity": ActivityRepository(db), "notifications": NotificationRepository(db), "jobs": JobRepository(db)
    }


@app.get("/health")
def health(): return {"status": "ok", "version": "1.0.0"}

@app.post("/auth/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, r=Depends(repos)):
    # public registration is always member role
    data = data.model_copy(update={"role": "member"})
    return UserService(r["users"]).create_user(data)

@app.post("/auth/login", response_model=TokenRead)
def login(data: LoginRequest, request: Request, r=Depends(repos)):
    _check_login_rate(request.client.host if request.client else "unknown")
    try:
        user = AuthService(r["users"]).login(data.username, data.password)
        return {"access_token": create_access_token(user), "role": user.role}
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

@app.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)): return user

@app.post("/users", response_model=UserRead, status_code=201)
def create_user(data: UserCreate, r=Depends(repos), _: User = Depends(require_role("admin"))): return UserService(r["users"]).create_user(data)

@app.get("/users", response_model=list[UserRead])
def list_users(r=Depends(repos), _: User = Depends(require_role("admin"))): return UserService(r["users"]).list_users()

@app.post("/teams", response_model=TeamRead, status_code=201)
def create_team(data: TeamCreate, r=Depends(repos), _: User = Depends(require_role("admin"))): return TeamService(r["teams"], r["users"]).create_team(data)

@app.get("/teams", response_model=list[TeamRead])
def list_teams(r=Depends(repos), _: User = Depends(require_role("viewer"))): return TeamService(r["teams"], r["users"]).list_teams()

@app.post("/teams/{team_id}/members", response_model=TeamMemberRead, status_code=201)
def add_team_member(team_id: int, data: TeamMemberCreate, r=Depends(repos), _: User = Depends(require_role("admin"))):
    try:
        return TeamService(r["teams"], r["users"]).add_member(team_id, data)
    except (TeamNotFoundError, UserNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/projects", response_model=ProjectRead, status_code=201)
def create_project(data: ProjectCreate, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return ProjectService(r["projects"], r["teams"]).create_project(data)
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.get("/projects", response_model=list[ProjectRead])
def list_projects(r=Depends(repos), _: User = Depends(require_role("viewer"))): return ProjectService(r["projects"], r["teams"]).list_projects()

@app.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(data: TaskCreate, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"], r["projects"], r["users"]).create_task(data)
    except (ProjectNotFoundError, UserNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(task_status: str | None = Query(default=None, alias="status"), q: str | None = None, priority: str | None = None, tag: str | None = None, project_id: int | None = None, owner_id: int | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=1000), r=Depends(repos), _: User = Depends(require_role("viewer"))):
    return TaskService(r["tasks"], r["projects"], r["users"]).list_tasks(status=task_status, query=q, priority=priority, tag=tag, project_id=project_id, owner_id=owner_id, skip=skip, limit=limit)

@app.get("/tasks/search", response_model=list[TaskRead])
def search_tasks(q: str = Query(min_length=1), task_status: str | None = Query(default=None, alias="status"), priority: str | None = None, tag: str | None = None, project_id: int | None = None, owner_id: int | None = None, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=1000), r=Depends(repos), _: User = Depends(require_role("viewer"))):
    return TaskService(r["tasks"], r["projects"], r["users"]).list_tasks(status=task_status, query=q, priority=priority, tag=tag, project_id=project_id, owner_id=owner_id, skip=skip, limit=limit)

@app.get("/tasks/export.csv")
def export_tasks_csv(r=Depends(repos), _: User = Depends(require_role("viewer"))): return Response(content=TaskService(r["tasks"]).export_csv(), media_type="text/csv")

@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int, r=Depends(repos), _: User = Depends(require_role("viewer"))):
    try:
        return TaskService(r["tasks"]).get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: int, data: TaskUpdate, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"], r["projects"], r["users"]).update_task(task_id, data)
    except (TaskNotFoundError, ProjectNotFoundError, UserNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/tasks/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"]).complete_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DependencyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, r=Depends(repos), _: User = Depends(require_role("admin"))):
    try:
        TaskService(r["tasks"]).delete_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/tasks/{task_id}/subtasks", response_model=TaskRead, status_code=201)
def add_subtask(task_id: int, data: SubTaskCreate, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"]).add_subtask(task_id, data)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/tasks/{task_id}/comments", response_model=TaskRead, status_code=201)
def add_comment(task_id: int, data: CommentCreate, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"]).add_comment(task_id, data)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/tasks/{task_id}/dependencies", response_model=TaskRead, status_code=201)
def add_dependency(task_id: int, data: DependencyCreate, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"]).add_dependency(task_id, data)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DependencyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.patch("/subtasks/{subtask_id}", response_model=SubTaskRead)
def update_subtask(subtask_id: int, done: bool, r=Depends(repos), _: User = Depends(require_role("member"))):
    try:
        return TaskService(r["tasks"]).set_subtask_state(subtask_id, done)
    except SubTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.get("/analytics", response_model=AnalyticsRead)
def analytics(r=Depends(repos), _: User = Depends(require_role("viewer"))): return TaskService(r["tasks"]).analytics()

@app.get("/dashboard", response_model=DashboardRead)
def dashboard(r=Depends(repos), _: User = Depends(require_role("viewer"))): return TaskService(r["tasks"]).dashboard()

@app.get("/ai/recommendations", response_model=list[AIRecommendationRead])
def ai_recommendations(r=Depends(repos), _: User = Depends(require_role("viewer"))): return TaskService(r["tasks"]).ai_recommendations()

@app.get("/recommendations", response_model=list[str])
def old_recommendations(r=Depends(repos), _: User = Depends(require_role("viewer"))): return [x["recommendation"] for x in TaskService(r["tasks"]).ai_recommendations()]

@app.get("/plan/today", response_model=PlanRead)
def daily_plan(r=Depends(repos), _: User = Depends(require_role("viewer"))): return TaskService(r["tasks"]).daily_plan()

@app.post("/notifications/email", response_model=EmailRead, status_code=201)
def queue_email(data: EmailCreate, r=Depends(repos), _: User = Depends(require_role("member"))): return NotificationService(r["notifications"]).queue_email(data)

@app.get("/notifications/email", response_model=list[EmailRead])
def list_emails(r=Depends(repos), _: User = Depends(require_role("admin"))): return NotificationService(r["notifications"]).list_emails()

@app.post("/notifications/email/send")
def send_emails(r=Depends(repos), _: User = Depends(require_role("admin"))): return NotificationService(r["notifications"]).send_queued()

@app.post("/jobs", response_model=JobRead, status_code=201)
def create_job(data: JobCreate, r=Depends(repos), _: User = Depends(require_role("admin"))): return JobService(r["jobs"], r["notifications"]).create_job(data)

@app.get("/jobs", response_model=list[JobRead])
def list_jobs(r=Depends(repos), _: User = Depends(require_role("admin"))): return JobService(r["jobs"], r["notifications"]).list_jobs()

@app.post("/jobs/run")
def run_jobs(r=Depends(repos), _: User = Depends(require_role("admin"))): return JobService(r["jobs"], r["notifications"]).run_queued()

@app.get("/activity", response_model=list[ActivityRead])
def activity(limit: int = 50, r=Depends(repos), _: User = Depends(require_role("viewer"))): return ActivityService(r["activity"]).list_activity(limit=limit)
