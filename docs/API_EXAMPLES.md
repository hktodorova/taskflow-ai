# API Examples

Start the API:

```bash
uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

## Register user

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo-user","email":"demo-user@example.com","password":"secret123","role":"member"}'
```

## Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo-user","password":"secret123"}'
```

Copy `access_token` and use it as a Bearer token.

## Create task

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Finish SoftUni AI Project","description":"Complete documentation and screenshots","priority":"high","estimated_minutes":180,"tags":["softuni","ai","exam"],"ai_notes":"High-priority final submission task"}'
```

## Analytics

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/analytics
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/dashboard
```

## Run tests

```bash
pytest -v
```

Public registration creates a `member` user. Use the admin-only `/users` endpoint if you need to create additional users with specific roles.
