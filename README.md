# agent-for-airflow

An AI agent that lives in Slack, monitors Apache Airflow pipeline failures, analyzes root causes, and executes remediation actions on behalf of Data Engineers.

## How it works

1. Airflow DAG fails → `on_failure_callback` posts an alert to a Slack channel
2. The agent detects the alert, fetches task logs, and posts an analysis + suggested actions in the thread
3. The DE reads the summary and replies with an instruction (e.g. "mark the sensor as success")
4. The agent executes the action via the Airflow REST API and reports back
5. DE can also @mention the bot anytime to ask general questions about DAGs

## Architecture

```
Airflow ──on_failure_callback──► Slack Channel
                                      │
                     ┌────────────────┼────────────────┐
                message_event    thread reply      app_mention
                (top-level)      (from DE)         (@mention)
                     │                │                 │
              Analyze failure   Execute action    Answer question
              Post in thread    Report back       Read-only tools
                     │
              ┌──────┴──────────────────────┐
              │  LLM Provider               │
              │  Claude / OpenAI / Gemini   │
              └──────┬──────────────────────┘
                     │
                app/airflow/tools/  →  Airflow REST API v2
```

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- A Slack workspace where you can create apps (free plan is fine)
- An API key for Claude, OpenAI, or Gemini

## Setup

### 1. Install dependencies

```bash
# Gemini (free tier available)
pip install -e ".[gemini]"

# Claude
pip install -e ".[claude]"

# OpenAI
pip install -e ".[openai]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values (see [Configuration Reference](#configuration-reference) below).

### 3. Start local Airflow

```bash
docker compose up -d
```

Airflow UI will be available at http://localhost:8080 (username: `airflow`, password: `airflow`).

```bash
docker compose ps   # webserver should show "(healthy)"
```

### 4. Create a Slack App

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Give it a name (e.g. `airflow-agent`) and select your workspace

**Enable Socket Mode**

3. Navigate to **Socket Mode** and toggle it on
4. Create an app-level token with scope `connections:write` → save as `SLACK_APP_TOKEN`

**Set OAuth scopes**

5. **OAuth & Permissions** → **Bot Token Scopes** → add:
   - `chat:write`
   - `channels:history`
   - `channels:read`
   - `app_mentions:read`
   - `reactions:write`

**Subscribe to events**

6. **Event Subscriptions** → toggle on → **Subscribe to bot events** → add:
   - `message.channels`
   - `app_mention`

**Install the app**

7. **OAuth & Permissions** → **Install to Workspace**
8. Copy the **Bot User OAuth Token** → save as `SLACK_BOT_TOKEN`

**Invite the bot to your alert channel**

9. In Slack, run `/invite @airflow-agent` in the alert channel
10. Copy the channel ID (right-click channel → **Copy link**, last segment) → save as `SLACK_ALERT_CHANNEL`

### 5. Configure Airflow to send Slack alerts

The example DAG in `dags/example_pipeline.py` already has an `on_failure_callback` configured using `SlackWebhookHook` (conn_id: `slack_default`). The `AIRFLOW_CONN_SLACK_DEFAULT` env var set in docker-compose is picked up automatically.

For your own DAGs, use the same hook pattern. The agent parses the following fields from the alert message — include as many as possible for faster and more accurate analysis:

| Field | Required | Benefit |
|---|---|---|
| `dag_id`, `dag_run_id` | Yes | Core identifiers for all API calls |
| `task_id`, `try_number` | Recommended | Skips `get_failed_tasks` API call |
| `error_msg` | Recommended | Used as a hint to guide LLM analysis |
| `execution_date`, `schedule`, `owner` | Optional | Richer context in the summary |
| `log_url` | Optional | Direct link for DE to open Airflow UI |

### 6. Run the agent

```bash
python -m app.app
```

### 7. Test

Trigger a failure using the example DAG:

```bash
# sensor timeout (default)
docker compose exec airflow-webserver airflow dags trigger example_pipeline

# connection error
docker compose exec airflow-webserver airflow dags trigger example_pipeline --conf '{"fail_at": "extract"}'
```

Or post a message manually in the alert channel to test without Airflow:

```
DAG example_pipeline failed
Run ID: manual__2024-01-01T00:00:00+00:00
```

You can also @mention the bot for general questions:

```
@airflow-agent 지금 어떤 DAG가 있어?
@airflow-agent example_pipeline 최근 실행 상태 알려줘
```

While the agent is processing, it adds a 🤔 reaction to your message. The reaction is removed when the response is ready.

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | No | `claude` | LLM backend: `claude`, `openai`, or `gemini` |
| `ANTHROPIC_API_KEY` | If using Claude | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-opus-4-6` | Claude model ID |
| `OPENAI_API_KEY` | If using OpenAI | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model ID |
| `GOOGLE_API_KEY` | If using Gemini | — | Google AI Studio API key |
| `GEMINI_MODEL` | No | `gemini-1.5-flash` | Gemini model ID |
| `AIRFLOW_BASE_URL` | No | `http://localhost:8080` | Airflow webserver URL |
| `AIRFLOW_USERNAME` | No | `airflow` | Airflow basic auth username |
| `AIRFLOW_PASSWORD` | No | `airflow` | Airflow basic auth password |
| `SLACK_BOT_TOKEN` | Yes | — | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Yes | — | App-level token for Socket Mode (`xapp-...`) |
| `SLACK_ALERT_CHANNEL` | Yes | — | Channel ID (not name) that receives Airflow alerts |
| `SLACK_AIRFLOW_BOT_USER` | No | — | If set, only messages from this user ID are treated as alerts. Leave empty when using the same bot token for alerts and the agent. |
| `SLACK_WEBHOOK_URL` | No | — | Incoming Webhook URL for Airflow `on_failure_callback` (set as `AIRFLOW_CONN_SLACK_DEFAULT` in Docker) |

## Project Structure

```
agent-for-airflow/
├── docker-compose.yml      # Local Airflow (Postgres + webserver + scheduler)
├── pyproject.toml
├── .env.example
├── dags/                   # Example DAGs for local testing
│   └── example_pipeline.py # 4 failure scenarios (sensor/extract/load/none)
└── app/
    ├── app.py              # Slack Bolt entry point (message + app_mention handlers)
    ├── agent.py            # analyze_failure, handle_instruction, handle_general_question
    ├── parser.py           # Parses dag_id/dag_run_id from alert messages
    ├── store.py            # In-memory thread context store (thread_ts → DAG context)
    ├── config.py           # Settings (base URL, credentials)
    ├── airflow/            # Airflow REST API client + tools
    │   ├── client.py       # Async httpx client for Airflow REST API v2
    │   └── tools/
    │       ├── read.py     # list_dags, get_dag_run_status, get_failed_tasks,
    │       │               # get_task_logs, get_dag_runs
    │       └── write.py    # trigger_dag, clear_task, mark_task_state, set_dag_paused
    ├── llm/                # LLM provider abstraction
    │   ├── base.py         # LLMProvider (ABC) + ToolDefinition
    │   ├── claude.py       # Anthropic implementation
    │   ├── openai.py       # OpenAI implementation
    │   ├── gemini.py       # Google Gemini implementation
    │   └── factory.py      # Selects provider from LLM_PROVIDER env var
    └── handlers/
        ├── alert.py        # New alert → fetch logs → analyze → post in thread
        └── reply.py        # DE thread reply → execute instruction → report back
```
