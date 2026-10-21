# Taskly

Taskly is a tiny task-tracking API used as Docify's evaluation fixture.

## Features

- Users sign up and log in with email and password (bcrypt hashes, JWT access tokens).
- Create, list, update and delete tasks; tasks can have a due date and a priority.
- Overdue task reminders are sent by email every morning.

## Run

```bash
cp .env.example .env
uvicorn app.main:app --reload
```
