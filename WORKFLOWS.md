# Workflows

Step-by-step flows for each scenario the agent handles.

---

## 1. DAG Failure Alert

**Trigger**: Airflow DAG `on_failure_callback` posts an alert via Slack Incoming Webhook (`SlackWebhookHook`, conn_id: `slack_default`).

**Alert message format**
```
:red_circle: DAG *{dag_id}* failed
• Run ID: `{dag_run_id}`
• Failed task: `{task_id}` (attempt {try_number})
• Execution date: `{execution_date}`
• Schedule: `{schedule_interval}`
• Owner: `{owner}`
• Duration: {duration}s
• Error: {error_msg}
• Log: {log_url}
```

```
Step 1. Slack App receives message_event (top-level, not a thread reply)
        └─ Skip if message contains a bot @mention (handled by app_mention handler)
        └─ Check if message contains "dag" AND ("failed" OR "failure")

Step 2. Parse alert fields from the message
        └─ Required: dag_id, dag_run_id
        └─ Optional hints: task_id, try_number, error_msg

Step 3. Fetch failed task list (skipped if task_id already parsed from alert)
        └─ If task_id present in alert → use directly, skip get_failed_tasks API call
        └─ Otherwise → call get_failed_tasks(dag_id, dag_run_id)

Step 4. For each failed task, call get_task_logs(dag_id, dag_run_id, task_id, try_number)

Step 5. LLM analyzes the logs and produces a structured summary
        └─ error_msg from alert used as a hint to guide analysis
        └─ Root cause (e.g., timeout, connection error, data issue, code error)
        └─ Key error message
        └─ Numbered list of suggested actions

Step 6. Post the analysis as a reply in the alert thread
```

**Example Slack thread reply (Step 6)**
```
[Analysis]
• Failed task: wait_for_source
• Root cause: Sensor timed out after 60s — upstream file was not delivered
• Key error: "Sensor has timed out; run duration of 61.2s exceeded the timeout of 60.0s"

[Suggested actions — reply with a number to proceed]
1. Mark wait_for_source as success → downstream tasks will run automatically
2. Re-run the full DAG from the beginning
3. Pause this DAG for today
```

---

## 2. DE Command Execution

**Trigger**: DE replies in an alert thread with an instruction.

```
Step 1. Slack App receives message_event in a thread
        └─ Ignore if sender is the bot itself (loop prevention)
        └─ Add 🤔 reaction to the DE's message
        └─ Look up thread context from store (dag_id, dag_run_id, failed_tasks)
        └─ If thread is NOT a known alert thread → fall back to general Q&A (Workflow 3)

Step 2. LLM interprets the DE's intent
        └─ Map natural language to one or more write tool calls
        └─ Extract parameters from thread context

Step 3. If intent is ambiguous, ask a clarifying question before acting
        └─ e.g., "Did you mean to clear only wait_for_source,
                  or also the downstream tasks (extract_data, load_data)?"

Step 4. Execute the tool call(s)

Step 5. Remove 🤔 reaction, post the result in the thread
```

**Scenario A — Sensor timeout**
```
DE:    "The file won't come today, mark the sensor as success"

Agent: "About to mark wait_for_source as success.
        Downstream tasks (extract_data → transform_data → load_data → notify)
        will run automatically.
        Do you also want me to explicitly clear them for a fresh run? (yes / no)"

DE:    "no"

Agent: → mark_task_state(dag_id, dag_run_id, "wait_for_source", "success")

Agent: "Done. wait_for_source marked as success.
        Downstream tasks should start shortly."
```

**Scenario B — Re-run a specific task**
```
DE:    "Re-run load_data"

Agent: → clear_task(dag_id, dag_run_id, "load_data", include_downstream=false)

Agent: "Done. load_data has been cleared and will re-run shortly."
```

**Scenario C — Pause a DAG**
```
DE:    "Pause this DAG for today"

Agent: → set_dag_paused(dag_id, is_paused=true)

Agent: "Done. example_pipeline is now paused. Remember to unpause it when ready."
```

**Scenario D — Trigger a fresh run**
```
DE:    "Just re-run the whole thing"

Agent: → trigger_dag(dag_id)

Agent: "Done. A new run has been triggered: manual__2024-01-01T09:10:00+00:00"
```

---

## 3. General Q&A via @mention

**Trigger**: DE @mentions the bot, or replies in a non-alert thread without @mention.

```
Step 1. Slack App receives app_mention event (or thread reply not in alert store)
        └─ Strip the @mention from the text if present
        └─ Add 🤔 reaction to the message

Step 2. LLM receives the question with read-only tools available
        └─ Calls tools as needed (list_dags, get_dag_runs, get_dag_run_status, etc.)

Step 3. Remove 🤔 reaction, post the answer in a thread under the mention message
```

**Example**
```
DE:    "@airflow-agent 지금 어떤 DAG가 있어?"

Agent: → list_dags(only_active=true)

Agent: "현재 활성화된 DAG는 다음과 같아요:
        • example_pipeline (매일 02:00)"

DE:    "@airflow-agent example_pipeline 오늘 실행됐어?"

Agent: → get_dag_runs("example_pipeline", limit=1)

Agent: "example_pipeline의 가장 최근 실행:
        • Run ID: scheduled__2024-01-01T02:00:00+00:00
        • 상태: failed
        • 시작: 2024-01-01 02:00 / 종료: 2024-01-01 02:01"
```

---

## 4. Daily Operations Report

**Trigger**: Cron job fires at a configured time (e.g., 9 AM daily).

```
Step 1. Load the target DAG list from config

Step 2. For each DAG, call get_dag_runs(dag_id, start_date_gte=<yesterday 00:00>)

Step 3. Aggregate results
        ├─ Total runs: success / failed / skipped counts
        └─ For failed runs: attach brief failure reason from task logs

Step 4. LLM formats the report

Step 5. Post to the designated Slack channel
```

**Example Slack report**
```
[Daily Pipeline Report] 2024-01-02 09:00

Summary: 12 DAGs tracked | 10 success / 2 failed / 0 skipped

Failed DAGs:
• example_pipeline  — wait_for_source timed out (file not delivered)
• another_dag       — load_data failed: connection refused to source DB

All other pipelines completed successfully.
```

---

## Error Handling

| Situation | Agent behavior |
|---|---|
| Cannot parse dag_id / dag_run_id from alert | Reply in thread asking DE to provide the info manually |
| Airflow API returns an error | Report the error in the thread and suggest retrying or checking Airflow UI |
| DE instruction is ambiguous | Ask a clarifying question before calling any write tool |
| API call times out | Notify DE in thread; do not retry automatically |
| @mention in unknown channel | No response (agent only monitors the alert channel) |
