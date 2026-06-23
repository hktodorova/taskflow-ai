from datetime import date, datetime, timedelta, timezone
import csv
import io

from .auth import verify_password
from .models import BackgroundJob, Project, SubTask, Task, Team, TeamMember, User
from .repository import (
    ActivityRepository,
    JobRepository,
    NotificationRepository,
    ProjectRepository,
    TaskRepository,
    TeamRepository,
    UserRepository,
)
from .schemas import (
    CommentCreate,
    DependencyCreate,
    EmailCreate,
    JobCreate,
    ProjectCreate,
    SubTaskCreate,
    TaskCreate,
    TaskUpdate,
    TeamCreate,
    TeamMemberCreate,
    UserCreate,
)


class TaskNotFoundError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class TeamNotFoundError(Exception):
    pass


class SubTaskNotFoundError(Exception):
    pass


class DependencyError(Exception):
    pass


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def login(self, username: str, password: str) -> User:
        user = self.repo.by_username(username)
        if not user or not verify_password(password, user.password_hash):
            raise AuthError("Invalid username or password.")
        return user


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def create_user(self, data: UserCreate) -> User:
        return self.repo.create(data)

    def list_users(self) -> list[User]:
        return self.repo.list()


class TeamService:
    def __init__(self, repo: TeamRepository, users: UserRepository):
        self.repo = repo
        self.users = users

    def create_team(self, data: TeamCreate) -> Team:
        return self.repo.create(data)

    def list_teams(self) -> list[Team]:
        return self.repo.list()

    def add_member(self, team_id: int, data: TeamMemberCreate) -> TeamMember:
        if not self.repo.get(team_id):
            raise TeamNotFoundError(f"Team with id {team_id} was not found.")
        if not self.users.get(data.user_id):
            raise UserNotFoundError(f"User with id {data.user_id} was not found.")
        return self.repo.add_member(team_id, data)


class ProjectService:
    def __init__(self, repo: ProjectRepository, team_repo: TeamRepository | None = None):
        self.repo = repo
        self.team_repo = team_repo

    def create_project(self, data: ProjectCreate) -> Project:
        if data.team_id is not None and self.team_repo and not self.team_repo.get(data.team_id):
            raise TeamNotFoundError(f"Team with id {data.team_id} was not found.")
        return self.repo.create(data)

    def list_projects(self) -> list[Project]:
        return self.repo.list()


class TaskService:
    def __init__(
        self,
        repo: TaskRepository,
        project_repo: ProjectRepository | None = None,
        user_repo: UserRepository | None = None,
    ):
        self.repo = repo
        self.project_repo = project_repo
        self.user_repo = user_repo

    def _ensure_project_exists(self, project_id: int | None) -> None:
        if project_id is not None and self.project_repo and not self.project_repo.get(project_id):
            raise ProjectNotFoundError(f"Project with id {project_id} was not found.")

    def _ensure_user_exists(self, user_id: int | None) -> None:
        if user_id is not None and self.user_repo and not self.user_repo.get(user_id):
            raise UserNotFoundError(f"User with id {user_id} was not found.")

    def create_task(self, data: TaskCreate) -> Task:
        self._ensure_project_exists(data.project_id)
        self._ensure_user_exists(data.owner_id)
        return self.repo.create(data)

    def get_task(self, task_id: int) -> Task:
        task = self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} was not found.")
        return task

    def list_tasks(
        self,
        status=None,
        query=None,
        priority=None,
        tag=None,
        project_id=None,
        owner_id=None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Task]:
        return self.repo.list(
            status=status,
            query=query,
            priority=priority,
            tag=tag,
            project_id=project_id,
            owner_id=owner_id,
            skip=skip,
            limit=limit,
        )

    def update_task(self, task_id: int, data: TaskUpdate) -> Task:
        task = self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} was not found.")
        self._ensure_project_exists(data.project_id)
        self._ensure_user_exists(data.owner_id)
        return self.repo.update(task, data)

    def complete_task(self, task_id: int) -> Task:
        task = self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found.")
        open_deps = [
            dep.depends_on_task_id
            for dep in task.dependencies
            if (dep_task := self.repo.get(dep.depends_on_task_id))
            and dep_task.status != "completed"
        ]
        if open_deps:
            raise DependencyError(
                f"Task cannot be completed before dependencies are done: {open_deps}"
            )
        return self.repo.complete(task)

    def add_subtask(self, task_id: int, data: SubTaskCreate) -> Task:
        task = self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} was not found.")
        return self.repo.add_subtask(task, data)

    def add_comment(self, task_id: int, data: CommentCreate) -> Task:
        task = self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} was not found.")
        return self.repo.add_comment(task, data)

    def _would_create_cycle(self, from_id: int, to_id: int) -> bool:
        visited: set[int] = set()
        queue = [to_id]
        while queue:
            current = queue.pop()
            if current == from_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            task = self.repo.get(current)
            if task:
                for dep in task.dependencies:
                    queue.append(dep.depends_on_task_id)
        return False

    def add_dependency(self, task_id: int, data: DependencyCreate) -> Task:
        task = self.repo.get(task_id)
        depends_on = self.repo.get(data.depends_on_task_id)
        if not task or not depends_on:
            raise TaskNotFoundError("Task or dependency task was not found.")
        if task_id == data.depends_on_task_id:
            raise DependencyError("A task cannot depend on itself.")
        if self._would_create_cycle(task_id, data.depends_on_task_id):
            raise DependencyError("Adding this dependency would create a cycle.")
        return self.repo.add_dependency(task, data)

    def set_subtask_state(self, subtask_id: int, done: bool) -> SubTask:
        subtask = self.repo.set_subtask_state(subtask_id, done)
        if not subtask:
            raise SubTaskNotFoundError(f"Subtask with id {subtask_id} was not found.")
        return subtask

    def daily_plan(self) -> dict[str, list[Task]]:
        tasks = self.repo.list()
        today = datetime.now(timezone.utc).date()
        week_out = today + timedelta(days=7)
        return {
            "today": [t for t in tasks if t.due_date == today and t.status != "completed"],
            "upcoming": [
                t for t in tasks
                if t.due_date and today < t.due_date <= week_out and t.status != "completed"
            ],
            "backlog": [
                t for t in tasks
                if t.due_date is None and t.status not in {"completed", "blocked"}
            ],
            "blocked": [t for t in tasks if t.status == "blocked"],
        }

    def analytics(self) -> dict:
        return self.repo.analytics()

    def dashboard(self) -> dict:
        today = datetime.now(timezone.utc).date()
        tasks = self.repo.list()
        high_risk = [
            t for t in tasks
            if t.status != "completed"
            and (t.priority == "critical" or (t.due_date and t.due_date <= today))
        ]
        return {
            "analytics": self.analytics(),
            "high_risk_tasks": high_risk[:10],
            "recommendations": [r["recommendation"] for r in self.ai_recommendations()],
        }

    def ai_recommendations(self) -> list[dict]:
        tasks = self.repo.list()
        today = datetime.now(timezone.utc).date()
        recs: list[dict] = []

        for t in tasks:
            if t.status == "completed":
                continue
            if t.due_date and t.due_date < today:
                recs.append({
                    "task_id": t.id,
                    "recommendation": f"Move '{t.title}' to the top of today's plan.",
                    "reason": "Task is overdue.",
                    "confidence": 0.95,
                })
            elif t.priority == "critical":
                recs.append({
                    "task_id": t.id,
                    "recommendation": f"Start '{t.title}' before lower-priority tasks.",
                    "reason": "Critical priority.",
                    "confidence": 0.9,
                })
            elif t.status == "blocked":
                recs.append({
                    "task_id": t.id,
                    "recommendation": f"Resolve blocker for '{t.title}'.",
                    "reason": t.blocked_reason or "Task is blocked.",
                    "confidence": 0.86,
                })

        if not recs:
            recs.append({
                "task_id": None,
                "recommendation": "Workload looks stable. Continue with the next upcoming task.",
                "reason": "No overdue or critical open tasks found.",
                "confidence": 0.75,
            })

        return recs[:10]

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "title", "status", "priority",
            "due_date", "estimated_minutes", "actual_minutes", "tags",
        ])
        for t in self.repo.list():
            writer.writerow([
                t.id, t.title, t.status, t.priority,
                t.due_date or "", t.estimated_minutes, t.actual_minutes, t.tags,
            ])
        return output.getvalue()

    def delete_task(self, task_id: int) -> None:
        task = self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task {task_id} does not exist.")
        self.repo.delete(task)


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def queue_email(self, data: EmailCreate):
        return self.repo.queue_email(data)

    def list_emails(self):
        return self.repo.list()

    def send_queued(self) -> dict:
        return {"sent": self.repo.send_queued()}


class JobService:
    def __init__(self, jobs: JobRepository, notifications: NotificationRepository):
        self.jobs = jobs
        self.notifications = notifications

    def create_job(self, data: JobCreate) -> BackgroundJob:
        return self.jobs.create(data)

    def list_jobs(self) -> list[BackgroundJob]:
        return self.jobs.list()

    def run_queued(self) -> dict:
        processed = 0
        for job in self.jobs.queued():
            if job.job_type == "send_emails":
                result = f"sent={self.notifications.send_queued()}"
            elif job.job_type == "daily_digest":
                result = "daily digest generated"
            else:
                result = "noop"
            self.jobs.complete(job, result)
            processed += 1
        return {"processed": processed}


class ActivityService:
    def __init__(self, repo: ActivityRepository):
        self.repo = repo

    def list_activity(self, limit: int = 50):
        return self.repo.list(limit=limit)
