from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .auth import hash_password, new_token
from .models import (
    ActivityLog,
    BackgroundJob,
    Comment,
    EmailNotification,
    Project,
    SubTask,
    Task,
    TaskDependency,
    Team,
    TeamMember,
    User,
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


class RepositoryConflictError(Exception):
    pass


def _commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RepositoryConflictError(message) from exc


def _flush_commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RepositoryConflictError(message) from exc


def _tags_to_string(tags: List[str] | None) -> str:
    return ",".join(tags or [])


def _task_payload(data: TaskCreate | TaskUpdate, exclude_unset: bool = False) -> dict:
    payload = data.model_dump(exclude_unset=exclude_unset)
    if "tags" in payload:
        payload["tags"] = _tags_to_string(payload["tags"])
    return payload


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        details: str | None = None,
    ) -> None:
        self.db.add(ActivityLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details=details,
        ))

    def list(self, limit: int = 50) -> List[ActivityLog]:
        return list(
            self.db.scalars(
                select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
            )
        )


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: UserCreate) -> User:
        payload = data.model_dump(exclude={"password"})
        user = User(**payload, password_hash=hash_password(data.password), api_token=new_token())
        self.db.add(user)
        _commit_or_conflict(self.db, "Username or email already exists.")
        self.db.refresh(user)
        return user

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def by_username(self, username: str) -> User | None:
        return self.db.scalars(
            select(User).where(User.username == username.strip().lower())
        ).first()

    def list(self) -> List[User]:
        return list(self.db.scalars(select(User).order_by(User.username)))


class TeamRepository:
    def __init__(self, db: Session):
        self.db = db
        self.activity = ActivityRepository(db)

    def create(self, data: TeamCreate) -> Team:
        team = Team(**data.model_dump())
        self.db.add(team)
        try:
            self.db.flush()
            self.activity.add("team", team.id, "created", team.name)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RepositoryConflictError("Team name already exists.") from exc
        self.db.refresh(team)
        return team

    def get(self, team_id: int) -> Team | None:
        return self.db.scalars(
            select(Team).options(selectinload(Team.members)).where(Team.id == team_id)
        ).first()

    def list(self) -> List[Team]:
        return list(
            self.db.scalars(
                select(Team).options(selectinload(Team.members)).order_by(Team.name)
            )
        )

    def add_member(self, team_id: int, data: TeamMemberCreate) -> TeamMember:
        member = TeamMember(team_id=team_id, user_id=data.user_id, role=data.role)
        self.db.add(member)
        try:
            self.db.flush()
            self.activity.add("team", team_id, "member_added", f"user={data.user_id}")
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RepositoryConflictError("User is already a member of this team.") from exc
        self.db.refresh(member)
        return member


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db
        self.activity = ActivityRepository(db)

    def create(self, data: ProjectCreate) -> Project:
        project = Project(**data.model_dump())
        self.db.add(project)
        try:
            self.db.flush()
            self.activity.add("project", project.id, "created", project.name)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RepositoryConflictError("Project name already exists.") from exc
        self.db.refresh(project)
        return project

    def list(self) -> List[Project]:
        return list(self.db.scalars(select(Project).order_by(Project.name)))

    def get(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db
        self.activity = ActivityRepository(db)

    def create(self, data: TaskCreate) -> Task:
        task = Task(**_task_payload(data))
        self.db.add(task)
        try:
            self.db.flush()
            self.activity.add("task", task.id, "created", task.title)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RepositoryConflictError("Task could not be created.") from exc
        return self.get(task.id)  # type: ignore[return-value]

    def get(self, task_id: int) -> Task | None:
        return self.db.scalars(
            select(Task)
            .options(
                selectinload(Task.subtasks),
                selectinload(Task.comments),
                selectinload(Task.dependencies),
            )
            .where(Task.id == task_id)
        ).first()

    def list(
        self,
        status=None,
        query=None,
        priority=None,
        tag=None,
        project_id=None,
        owner_id=None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        stmt = select(Task).options(
            selectinload(Task.subtasks),
            selectinload(Task.comments),
            selectinload(Task.dependencies),
        )
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        if project_id:
            stmt = stmt.where(Task.project_id == project_id)
        if owner_id:
            stmt = stmt.where(Task.owner_id == owner_id)
        if tag:
            stmt = stmt.where(Task.tags.ilike(f"%{tag.lower()}%"))
        if query:
            stmt = stmt.where(
                Task.title.ilike(f"%{query}%")
                | Task.description.ilike(f"%{query}%")
                | Task.ai_notes.ilike(f"%{query}%")
            )
        return list(
            self.db.scalars(
                stmt.order_by(Task.due_date.is_(None), Task.due_date, Task.id)
                .offset(skip)
                .limit(limit)
            )
        )

    def update(self, task: Task, data: TaskUpdate) -> Task:
        old_status = task.status
        for key, value in _task_payload(data, exclude_unset=True).items():
            setattr(task, key, value)
        if data.status == "completed" and task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
        if data.status and data.status != "completed":
            task.completed_at = None
        self.activity.add("task", task.id, "updated", f"status {old_status} -> {task.status}")
        self.db.commit()
        return self.get(task.id)  # type: ignore[return-value]

    def complete(self, task: Task) -> Task:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        self.activity.add("task", task.id, "completed", task.title)
        self.db.commit()
        return self.get(task.id)  # type: ignore[return-value]

    def add_subtask(self, task: Task, data: SubTaskCreate) -> Task:
        self.db.add(SubTask(task_id=task.id, title=data.title))
        self.activity.add("task", task.id, "subtask_added", data.title)
        self.db.commit()
        return self.get(task.id)  # type: ignore[return-value]

    def add_comment(self, task: Task, data: CommentCreate) -> Task:
        self.db.add(Comment(task_id=task.id, author=data.author, body=data.body))
        self.activity.add("task", task.id, "comment_added", data.body[:120])
        self.db.commit()
        return self.get(task.id)  # type: ignore[return-value]

    def add_dependency(self, task: Task, data: DependencyCreate) -> Task:
        self.db.add(TaskDependency(task_id=task.id, depends_on_task_id=data.depends_on_task_id))
        self.activity.add("task", task.id, "dependency_added", str(data.depends_on_task_id))
        self.db.commit()
        return self.get(task.id)  # type: ignore[return-value]

    def set_subtask_state(self, subtask_id: int, done: bool) -> SubTask | None:
        subtask = self.db.get(SubTask, subtask_id)
        if not subtask:
            return None
        subtask.done = done
        self.activity.add("subtask", subtask.id, "state_changed", f"done={done}")
        self.db.commit()
        self.db.refresh(subtask)
        return subtask

    def delete(self, task: Task) -> None:
        self.activity.add("task", task.id, "deleted", task.title)
        self.db.delete(task)
        self.db.commit()

    def analytics(self) -> dict:
        tasks = list(self.db.scalars(select(Task)))
        today = datetime.now(timezone.utc).date()
        by_priority: dict[str, int] = {}
        by_status: dict[str, int] = {}
        team_load: dict[str, int] = {}

        project_team = {
            p.id: (p.team.name if p.team else "No team")
            for p in self.db.scalars(select(Project).options(selectinload(Project.team)))
        }

        for task in tasks:
            by_priority[task.priority] = by_priority.get(task.priority, 0) + 1
            by_status[task.status] = by_status.get(task.status, 0) + 1
            team_name = project_team.get(task.project_id, "No team")
            team_load[team_name] = team_load.get(team_name, 0) + 1

        completed = sum(1 for t in tasks if t.status == "completed")
        remaining_minutes = sum(t.estimated_minutes for t in tasks if t.status != "completed")
        actual_minutes = sum(t.actual_minutes for t in tasks)

        return {
            "total": len(tasks),
            "completed": completed,
            "active": sum(1 for t in tasks if t.status != "completed"),
            "blocked": sum(1 for t in tasks if t.status == "blocked"),
            "overdue": sum(
                1 for t in tasks
                if t.due_date and t.due_date < today and t.status != "completed"
            ),
            "completion_rate": round((completed / len(tasks) * 100) if tasks else 0, 2),
            "estimated_hours_remaining": round(remaining_minutes / 60, 2),
            "actual_hours_logged": round(actual_minutes / 60, 2),
            "by_priority": by_priority,
            "by_status": by_status,
            "team_load": team_load,
        }


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def queue_email(self, data: EmailCreate) -> EmailNotification:
        email = EmailNotification(**data.model_dump())
        self.db.add(email)
        self.db.commit()
        self.db.refresh(email)
        return email

    def list(self) -> List[EmailNotification]:
        return list(
            self.db.scalars(
                select(EmailNotification).order_by(EmailNotification.created_at.desc())
            )
        )

    def send_queued(self) -> int:
        emails = list(
            self.db.scalars(
                select(EmailNotification).where(EmailNotification.status == "queued")
            )
        )
        now = datetime.now(timezone.utc)
        for email in emails:
            email.status = "sent"
            email.sent_at = now
        self.db.commit()
        return len(emails)


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: JobCreate) -> BackgroundJob:
        job = BackgroundJob(**data.model_dump())
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list(self) -> List[BackgroundJob]:
        return list(
            self.db.scalars(
                select(BackgroundJob).order_by(BackgroundJob.created_at.desc())
            )
        )

    def queued(self) -> List[BackgroundJob]:
        return list(
            self.db.scalars(
                select(BackgroundJob).where(BackgroundJob.status == "queued")
            )
        )

    def complete(self, job: BackgroundJob, result: str) -> BackgroundJob:
        job.status = "completed"
        job.result = result
        job.processed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job
