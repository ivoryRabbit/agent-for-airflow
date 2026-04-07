import re
from dataclasses import dataclass, field


@dataclass
class AirflowAlert:
    dag_id: str
    dag_run_id: str
    task_id: str | None = field(default=None)
    try_number: int | None = field(default=None)
    error_msg: str | None = field(default=None)


# Patterns for common Airflow Slack alert formats.
# Adjust these to match your team's actual alert message format.
_DAG_ID_PATTERNS = [
    r"DAG[:\s]+[`*_]*([a-zA-Z0-9_.-]+)[`*_]*",   # "DAG: my_dag" or "DAG *my_dag*"
    r"dag_id[:\s=]+[`*_]*([a-zA-Z0-9_.-]+)[`*_]*",
]

_RUN_ID_PATTERNS = [
    r"Run ID[:\s]+[`*_]*([a-zA-Z0-9_:+.<>-]+)[`*_]*",
    r"dag_run_id[:\s=]+[`*_]*([a-zA-Z0-9_:+.<>-]+)[`*_]*",
    r"(scheduled__\S+|manual__\S+|backfill__\S+)",
]

_TASK_ID_PATTERNS = [
    r"Failed task[:\s]+[`*_]*([a-zA-Z0-9_.-]+)[`*_]*",
    r"task_id[:\s=]+[`*_]*([a-zA-Z0-9_.-]+)[`*_]*",
]

_TRY_NUMBER_PATTERNS = [
    r"attempt\s+(\d+)",
    r"try_number[:\s=]+(\d+)",
]

_ERROR_PATTERNS = [
    r"Error[:\s]+(.+)",
]


def parse_alert(text: str) -> AirflowAlert | None:
    """Extract alert fields from an Airflow failure Slack message.

    Returns None if the message does not look like an Airflow failure alert.
    """
    dag_id = _first_match(text, _DAG_ID_PATTERNS)
    dag_run_id = _first_match(text, _RUN_ID_PATTERNS)

    if dag_id and dag_run_id:
        try_number_str = _first_match(text, _TRY_NUMBER_PATTERNS)
        return AirflowAlert(
            dag_id=dag_id,
            dag_run_id=dag_run_id,
            task_id=_first_match(text, _TASK_ID_PATTERNS),
            try_number=int(try_number_str) if try_number_str else None,
            error_msg=_first_match(text, _ERROR_PATTERNS),
        )
    return None


def is_failure_alert(text: str) -> bool:
    """Return True if the message looks like an Airflow DAG failure alert."""
    lower = text.lower()
    has_dag = "dag" in lower
    has_failure = "failed" in lower or "failure" in lower
    return has_dag and has_failure


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None
