# agent-for-airflow

## Overview

An AI agent that lives in Slack, monitors Apache Airflow pipeline failures, analyzes root causes, and executes remediation actions on behalf of Data Engineers (DE).
The goal is to reduce manual intervention by surfacing the right context and acting on explicit DE instructions.

## Core Features

### 1. Failure Detection & Triage
- Receives DAG failure alerts via Slack `message` events (posted by the DAG `on_failure_callback`)
- Automatically fetches logs and analyzes the failure
- Posts a structured summary + suggested actions in the alert thread
- No auto-remediation — all write actions require explicit DE instruction

### 2. Log Analysis & Summary
- Queries failed DAG/Task logs via Airflow REST API v2
- LLM analyzes and posts a concise root cause summary in the Slack thread
- Helps DE quickly understand context without opening Airflow UI

### 3. General Q&A via @mention or thread reply
- DE can @mention the bot to ask questions
- DE can also reply in any existing thread without @mention — agent answers as a general question if the thread is not a known alert thread
- Agent uses read-only tools (list_dags, get_dag_runs, etc.) to answer
- While processing, adds 🤔 reaction to the user's message; removes it when done

### 4. Daily Operations Report
- Runs on a cron schedule (e.g., every day at 9 AM)
- Reports success/failure/skip statistics for a target DAG list
- Includes a brief summary of failed DAGs and their causes

### 5. Human-in-the-loop Command Execution
- DE replies in the alert thread with a natural language instruction
- Agent interprets intent, calls the appropriate write tool, and reports back
- Example: "sensor timeout이지만 문제없으니 success 처리하고 다음 task 실행해줘"

## Architecture

```
Airflow (DAG failure)
    │
    ▼ on_failure_callback → chat.postMessage to alert channel
Slack Channel
    │
    ├─ message_event (top-level alert)
    │       └─ Agent analyzes → posts summary in thread
    │
    ├─ message_event (thread reply from DE)
    │       ├─ Known alert thread → execute DE instruction (write tools)
    │       └─ Other thread → answer as general question (read-only tools)
    │
    └─ app_mention event (@mention)
            └─ Agent answers using read-only tools

    [Processing indicator]
    While handling any user message → add 🤔 reaction to the message
    After responding → remove 🤔 reaction

AI Agent
    ├── LLM Provider (Claude / OpenAI / Gemini — swappable via LLM_PROVIDER)
    ├── app/tools/
    │     ├── read.py  — list_dags, get_dag_run_status, get_failed_tasks,
    │     │              get_task_logs, get_dag_runs
    │     └── write.py — trigger_dag, clear_task, mark_task_state, set_dag_paused
    └── Scheduler — daily report cron trigger

[Failure Response Flow]
DAG fails → Airflow posts alert to Slack channel
    → Agent fetches logs and analyzes failure
    → Posts summary + suggested actions in alert thread
    → DE replies with instruction
    → Agent executes action and reports back
```

## Tech Stack

- **LLM**: Claude / OpenAI / Gemini (selectable via `LLM_PROVIDER` env var)
- **Airflow integration**: Internal Airflow REST API v2 via async httpx (`app/airflow_client.py`)
- **Slack integration**: Slack Bolt for Python (Socket Mode, event-driven)
- **Required Slack scopes**: `chat:write`, `channels:history`, `channels:read`, `app_mentions:read`, `reactions:write`
- **Scheduling**: cron for daily report
- **Local dev / testing**: Airflow running via Docker Compose

## Constraints

Actions the agent can take autonomously (read-only):
- List DAGs
- Query DAG/Task status and run history
- Fetch and analyze Task logs

Actions that require explicit DE instruction (write):
- Trigger or clear a DAG run
- Mark task as success/failed
- Pause/unpause a DAG

Out of scope:
- Modifying or deleting DAG code
- Changing Airflow system configuration

## Directory Structure

```
agent-for-airflow/
├── CLAUDE.md
├── TOOLS.md                # tool specifications
├── WORKFLOWS.md            # step-by-step flows for each scenario
├── README.md               # setup guide
├── pyproject.toml
├── docker-compose.yml      # local Airflow for development & testing
├── dags/                   # example DAGs for local testing
│   └── example_pipeline.py
├── app/                    # Airflow REST API client + tools
│   ├── airflow_client.py
│   ├── config.py
│   └── tools/
│       ├── read.py
│       └── write.py
└── slack/                  # Slack agent
    ├── app.py
    ├── agent.py
    ├── parser.py
    ├── store.py
    ├── llm/
    │   ├── base.py
    │   ├── claude.py
    │   ├── openai.py
    │   ├── gemini.py
    │   └── factory.py
    └── handlers/
        ├── alert.py
        └── reply.py
```
