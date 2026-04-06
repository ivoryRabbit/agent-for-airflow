"""Claude-based agent for Airflow failure analysis and DE instruction execution."""

from typing import Any

from app.tools import read, write
from slack.llm.base import LLMProvider, ToolDefinition
from slack.llm.factory import create_provider

WRITE_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="trigger_dag",
        description="Manually trigger a new DAG run.",
        properties={
            "dag_id": {"type": "string"},
            "conf": {"type": "object", "description": "Optional runtime config passed to the DAG"},
        },
        required=["dag_id"],
    ),
    ToolDefinition(
        name="clear_task",
        description=(
            "Clear a task instance to re-run it within the existing DAG run. "
            "Set include_downstream=true to also clear all downstream tasks."
        ),
        properties={
            "dag_id": {"type": "string"},
            "dag_run_id": {"type": "string"},
            "task_id": {"type": "string"},
            "include_downstream": {"type": "boolean"},
        },
        required=["dag_id", "dag_run_id", "task_id"],
    ),
    ToolDefinition(
        name="mark_task_state",
        description=(
            "Force-set a task instance to 'success' or 'failed'. "
            "Marking as 'success' lets downstream tasks proceed automatically."
        ),
        properties={
            "dag_id": {"type": "string"},
            "dag_run_id": {"type": "string"},
            "task_id": {"type": "string"},
            "state": {"type": "string", "enum": ["success", "failed"]},
        },
        required=["dag_id", "dag_run_id", "task_id", "state"],
    ),
    ToolDefinition(
        name="set_dag_paused",
        description="Pause or unpause a DAG to prevent or allow scheduled runs.",
        properties={
            "dag_id": {"type": "string"},
            "is_paused": {"type": "boolean"},
        },
        required=["dag_id", "is_paused"],
    ),
]

ANALYZE_SYSTEM = """\
You are an Airflow operations assistant. A DAG has failed.
Analyze the provided task logs and respond in this exact format:

[Analysis]
• Failed task: <task_id>
• Root cause: <one-line summary>
• Key error: <most relevant log line>

[Suggested actions — reply with a number to proceed]
1. <action>
2. <action>
3. <action>

Keep the analysis concise. The audience is a data engineer who needs to act quickly.\
"""

INSTRUCTION_SYSTEM = """\
You are an Airflow operations assistant executing instructions from a data engineer.
You have tools to interact with Airflow. Use them to fulfill the DE's request.
After executing, briefly confirm what was done.\
"""

GENERAL_SYSTEM = """\
You are an Airflow operations assistant. You have read-only tools to query Airflow.
Answer the user's question using the tools when needed.
Be concise. Respond in the same language the user used.\
"""

READ_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="list_dags",
        description="List DAGs registered in Airflow.",
        properties={"only_active": {"type": "boolean", "description": "If true, return only unpaused DAGs (default: true)"}},
        required=[],
    ),
    ToolDefinition(
        name="get_dag_run_status",
        description="Get the status of a specific DAG run.",
        properties={
            "dag_id": {"type": "string"},
            "dag_run_id": {"type": "string"},
        },
        required=["dag_id", "dag_run_id"],
    ),
    ToolDefinition(
        name="get_dag_runs",
        description="Get recent DAG runs for a given DAG.",
        properties={
            "dag_id": {"type": "string"},
            "limit": {"type": "integer"},
            "start_date_gte": {"type": "string"},
        },
        required=["dag_id"],
    ),
    ToolDefinition(
        name="get_failed_tasks",
        description="Get the list of failed tasks within a DAG run.",
        properties={
            "dag_id": {"type": "string"},
            "dag_run_id": {"type": "string"},
        },
        required=["dag_id", "dag_run_id"],
    ),
]


class AirflowAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or create_provider()

    async def analyze_failure(self, dag_id: str, dag_run_id: str) -> str:
        """Fetch logs for all failed tasks and return a structured analysis."""
        failed_tasks = await read.get_failed_tasks(dag_id, dag_run_id)

        if not failed_tasks:
            return f"No failed tasks found in `{dag_id}` run `{dag_run_id}`."

        log_sections: list[str] = []
        for task in failed_tasks:
            log_data = await read.get_task_logs(
                dag_id, dag_run_id, task["task_id"], task["try_number"]
            )
            trimmed = log_data["logs"][-3000:] if len(log_data["logs"]) > 3000 else log_data["logs"]
            log_sections.append(f"=== Task: {task['task_id']} ===\n{trimmed}")

        prompt = (
            f"DAG: {dag_id}\nRun ID: {dag_run_id}\n\n"
            f"Failed task logs:\n\n" + "\n\n".join(log_sections)
        )
        return await self._provider.analyze(ANALYZE_SYSTEM, prompt)

    async def handle_instruction(
        self,
        instruction: str,
        dag_id: str,
        dag_run_id: str,
        failed_tasks: list[dict[str, Any]],
    ) -> str:
        """Interpret a DE's natural language instruction and execute the appropriate tool."""
        prompt = (
            f"DAG: {dag_id}\n"
            f"Run ID: {dag_run_id}\n"
            f"Failed tasks: {', '.join(t['task_id'] for t in failed_tasks)}\n\n"
            f"DE instruction: {instruction}"
        )
        return await self._provider.run_with_tools(
            INSTRUCTION_SYSTEM, prompt, WRITE_TOOLS, _execute_tool
        )


    async def handle_general_question(self, question: str) -> str:
        """Answer a free-form question about Airflow using read-only tools."""
        return await self._provider.run_with_tools(
            GENERAL_SYSTEM, question, READ_TOOLS, _execute_read_tool
        )


async def _execute_read_tool(name: str, inputs: dict[str, Any]) -> Any:
    match name:
        case "list_dags":
            return await read.list_dags(**inputs)
        case "get_dag_run_status":
            return await read.get_dag_run_status(**inputs)
        case "get_dag_runs":
            return await read.get_dag_runs(**inputs)
        case "get_failed_tasks":
            return await read.get_failed_tasks(**inputs)
        case _:
            return {"error": f"Unknown tool: {name}"}


async def _execute_tool(name: str, inputs: dict[str, Any]) -> Any:
    match name:
        case "trigger_dag":
            return await write.trigger_dag(**inputs)
        case "clear_task":
            return await write.clear_task(**inputs)
        case "mark_task_state":
            return await write.mark_task_state(**inputs)
        case "set_dag_paused":
            return await write.set_dag_paused(**inputs)
        case _:
            return {"error": f"Unknown tool: {name}"}
