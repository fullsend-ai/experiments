# User API

A minimal REST API for managing users, backed by PostgreSQL.

## Endpoints

- `GET /health` — health check
- `GET /users` — list all users
- `GET /users/{id}` — get a user by ID
- `POST /users` — create a new user

## Running

```bash
go run .
```

Requires a PostgreSQL database. Set `DATABASE_URL` to configure the connection.
