import argparse, json, os, sys
from urllib import request, error, parse

BASE_URL = os.getenv("TASKFLOW_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("TASKFLOW_TOKEN", "")


def call(method: str, path: str, data: dict | None = None):
    body = json.dumps(data).encode() if data is not None else None
    req = request.Request(BASE_URL + path, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN: req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {"status": resp.status}
    except error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr); sys.exit(exc.code)


def main():
    parser = argparse.ArgumentParser(description="TaskFlow AI Enterprise CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register"); reg.add_argument("username"); reg.add_argument("email"); reg.add_argument("password")
    log = sub.add_parser("login"); log.add_argument("username"); log.add_argument("password")
    team = sub.add_parser("team-create"); team.add_argument("name"); team.add_argument("--description")
    proj = sub.add_parser("project-create"); proj.add_argument("name"); proj.add_argument("--team-id", type=int); proj.add_argument("--description")
    add = sub.add_parser("add-task"); add.add_argument("title"); add.add_argument("--priority", default="medium"); add.add_argument("--project-id", type=int); add.add_argument("--owner-id", type=int); add.add_argument("--tag", action="append", default=[])
    ls = sub.add_parser("list-tasks"); ls.add_argument("--status"); ls.add_argument("--priority"); ls.add_argument("--tag")
    search = sub.add_parser("search"); search.add_argument("q")
    comp = sub.add_parser("complete"); comp.add_argument("task_id", type=int)
    sub.add_parser("dashboard"); sub.add_parser("analytics"); sub.add_parser("ai")
    email = sub.add_parser("email"); email.add_argument("recipient"); email.add_argument("subject"); email.add_argument("body")
    job = sub.add_parser("job"); job.add_argument("job_type")
    sub.add_parser("run-jobs")
    args = parser.parse_args()
    if args.cmd == "register": result = call("POST", "/auth/register", {"username": args.username, "email": args.email, "password": args.password, "role": "member"})
    elif args.cmd == "login": result = call("POST", "/auth/login", {"username": args.username, "password": args.password})
    elif args.cmd == "team-create": result = call("POST", "/teams", {"name": args.name, "description": args.description})
    elif args.cmd == "project-create": result = call("POST", "/projects", {"name": args.name, "description": args.description, "team_id": args.team_id})
    elif args.cmd == "add-task": result = call("POST", "/tasks", {"title": args.title, "priority": args.priority, "project_id": args.project_id, "owner_id": args.owner_id, "tags": args.tag})
    elif args.cmd == "list-tasks":
        params = {k: v for k, v in {"status": args.status, "priority": args.priority, "tag": args.tag}.items() if v}
        qs = "?" + parse.urlencode(params) if params else ""
        result = call("GET", "/tasks" + qs)
    elif args.cmd == "search": result = call("GET", f"/tasks/search?q={parse.quote_plus(args.q)}")
    elif args.cmd == "complete": result = call("POST", f"/tasks/{args.task_id}/complete")
    elif args.cmd == "dashboard": result = call("GET", "/dashboard")
    elif args.cmd == "analytics": result = call("GET", "/analytics")
    elif args.cmd == "ai": result = call("GET", "/ai/recommendations")
    elif args.cmd == "email": result = call("POST", "/notifications/email", {"recipient": args.recipient, "subject": args.subject, "body": args.body})
    elif args.cmd == "job": result = call("POST", "/jobs", {"job_type": args.job_type})
    elif args.cmd == "run-jobs": result = call("POST", "/jobs/run")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__": main()
