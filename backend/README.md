# Workflow Builder Backend (FastAPI)

This backend provides:
- Admin/user auth
- Workflow CRUD with versioning
- JSON import/export
- AI workflow generation (OpenAI)

## Quickstart (local)

```bash
cd /Users/crowdanalytix/Documents/personal/flow/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

API base: `http://localhost:8000/api`
Health: `http://localhost:8000/health`

## Environment

- `DATABASE_URL` (default `sqlite:///./data/app.db`)
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` (admin seed on startup)
- `TEST_USERS` (semicolon separated `email:password:role`)
- `COOKIE_SECURE`, `COOKIE_SAMESITE`
- `CORS_ORIGINS` (comma-separated)
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `OPENAI_API_MODE` (`responses` or `chat`)

## Auth

`POST /api/auth/login`

```json
{
  "email": "admin@example.com",
  "password": "change-me"
}
```

Returns
```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

Use `Authorization: Bearer <token>` for protected endpoints.

Refresh / logout:
- `POST /api/auth/refresh` (uses httpOnly refresh cookie)
- `POST /api/auth/logout` (revokes refresh cookie)
- `POST /api/auth/request-reset`
- `POST /api/auth/reset`
- `POST /api/auth/change-password`

Note: `request-reset` returns a token in the response for now (no email delivery wired).

## Users (admin only)

- `POST /api/users`
- `GET /api/users`
- `PATCH /api/users/{id}`
- `GET /api/users/me`
- `PATCH /api/users/me`

## Audit Logs (admin only)

- `GET /api/audit?limit=100`

## Workflows

- `POST /api/workflows`
- `GET /api/workflows`
- `GET /api/workflows?templates=only|exclude`
- `GET /api/workflows/{id}`
- `PATCH /api/workflows/{id}`
- `POST /api/workflows/{id}/template?is_template=true|false`
- `DELETE /api/workflows/{id}`
- `POST /api/workflows/{id}/duplicate`
- `POST /api/workflows/{id}/export`
- `POST /api/workflows/import`

### Workflow JSON Shape

```json
{
  "id": "wf_...",
  "name": "My Workflow",
  "updatedAt": "2024-01-01T00:00:00Z",
  "nodes": [
    {
      "id": "node_1",
      "type": "start",
      "position": { "x": 0, "y": 0 },
      "data": { "label": "Start" }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2"
    }
  ]
}
```

### Export envelope

```json
{
  "version": 1,
  "exportedAt": "2024-01-01T00:00:00Z",
  "workflow": { ... }
}
```

## AI Generate

`POST /api/workflows/generate`

```json
{
  "description": "webhook intake validate then task then end",
  "mode": "replace"
}
```

Returns `workflow` JSON matching the schema.

## Docker

```bash
docker build -t workflow-backend .
docker run --env-file .env -p 8000:8000 workflow-backend
```

Or from repo root:
```bash
cd /Users/crowdanalytix/Documents/personal/flow
docker compose up --build
```
