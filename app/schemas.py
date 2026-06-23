from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}
ALLOWED_STATUSES = {"active", "in_progress", "blocked", "completed"}
ALLOWED_ROLES = {"admin", "member", "viewer"}
ALLOWED_TEAM_ROLES = {"lead", "manager", "developer", "tester", "viewer"}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    email: EmailStr
    password: str = Field(min_length=6, max_length=80)
    full_name: str | None = Field(default=None, max_length=120)
    role: str = "member"

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "-")
        if not value:
            raise ValueError("Username cannot be empty.")
        return value

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        value = value.lower()
        if value not in ALLOWED_ROLES:
            raise ValueError("Role must be admin, member, or viewer.")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Team name cannot be empty.")
        return value


class TeamMemberCreate(BaseModel):
    user_id: int
    role: str = "developer"

    @field_validator("role")
    @classmethod
    def valid_team_role(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_TEAM_ROLES:
            raise ValueError("Team role must be lead, manager, developer, tester, or viewer.")
        return value


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    team_id: int
    user_id: int
    role: str


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    created_at: datetime
    members: list[TeamMemberRead] = []


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    team_id: int | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be empty.")
        return value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    team_id: int | None
    created_at: datetime


class SubTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class SubTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    title: str
    done: bool


class CommentCreate(BaseModel):
    author: str = Field(default="system", min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=1000)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    author: str
    body: str
    created_at: datetime


class DependencyCreate(BaseModel):
    depends_on_task_id: int


class DependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    depends_on_task_id: int


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    priority: str = "medium"
    status: str = "active"
    due_date: date | None = None
    estimated_minutes: int = Field(default=30, ge=1, le=24 * 60)
    actual_minutes: int = Field(default=0, ge=0, le=24 * 60)
    tags: list[str] = Field(default_factory=list)
    project_id: int | None = None
    owner_id: int | None = None
    ai_notes: str | None = None
    blocked_reason: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be empty.")
        return value

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value: str) -> str:
        value = value.lower()
        if value not in ALLOWED_PRIORITIES:
            raise ValueError("Priority must be low, medium, high, or critical.")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        value = value.lower()
        if value not in ALLOWED_STATUSES:
            raise ValueError("Invalid task status.")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return sorted({tag.strip().lower() for tag in values if tag.strip()})

    @model_validator(mode="after")
    def blocked_tasks_need_reason(self):
        if self.status == "blocked" and not self.blocked_reason:
            raise ValueError("Blocked tasks must include blocked_reason.")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    due_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    actual_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    tags: list[str] | None = None
    project_id: int | None = None
    owner_id: int | None = None
    ai_notes: str | None = None
    blocked_reason: str | None = None

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value: str | None) -> str | None:
        if value is None: return value
        value = value.lower()
        if value not in ALLOWED_PRIORITIES: raise ValueError("Invalid priority.")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is None: return value
        value = value.lower()
        if value not in ALLOWED_STATUSES: raise ValueError("Invalid task status.")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None: return values
        return sorted({tag.strip().lower() for tag in values if tag.strip()})

    @model_validator(mode="after")
    def blocked_tasks_need_reason(self):
        if self.status == "blocked" and not self.blocked_reason:
            raise ValueError("Blocked tasks must include blocked_reason.")
        return self


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def split_tags(cls, value):
        if hasattr(value, "tags") and isinstance(value.tags, str):
            value.tags = [tag for tag in value.tags.split(",") if tag]
        elif isinstance(value, dict) and isinstance(value.get("tags"), str):
            value["tags"] = [tag for tag in value["tags"].split(",") if tag]
        return value

    id: int
    title: str
    description: str | None
    priority: str
    status: str
    due_date: date | None
    estimated_minutes: int
    actual_minutes: int
    tags: list[str]
    ai_notes: str | None
    blocked_reason: str | None
    project_id: int | None
    owner_id: int | None
    created_at: datetime
    completed_at: datetime | None
    subtasks: list[SubTaskRead] = []
    comments: list[CommentRead] = []
    dependencies: list[DependencyRead] = []


class AnalyticsRead(BaseModel):
    total: int
    completed: int
    active: int
    blocked: int
    overdue: int
    completion_rate: float
    estimated_hours_remaining: float
    actual_hours_logged: float
    by_priority: dict[str, int]
    by_status: dict[str, int]
    team_load: dict[str, int]


class PlanRead(BaseModel):
    today: list[TaskRead]
    upcoming: list[TaskRead]
    backlog: list[TaskRead]
    blocked: list[TaskRead]


class DashboardRead(BaseModel):
    analytics: AnalyticsRead
    high_risk_tasks: list[TaskRead]
    recommendations: list[str]


class AIRecommendationRead(BaseModel):
    task_id: int | None = None
    recommendation: str
    reason: str
    confidence: float


class EmailCreate(BaseModel):
    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1)


class EmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipient: str
    subject: str
    body: str
    status: str
    created_at: datetime
    sent_at: datetime | None


class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=40)
    payload: str = "{}"


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_type: str
    payload: str
    status: str
    result: str | None
    created_at: datetime
    processed_at: datetime | None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entity_type: str
    entity_id: int
    action: str
    details: str | None
    created_at: datetime
