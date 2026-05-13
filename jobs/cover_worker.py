"""Background worker for queued AI cover generation tasks."""
from services.cover_task_service import run_pending_cover_tasks


def run_once(limit: int = 2) -> int:
    """Consume a small batch of queued cover tasks."""
    return run_pending_cover_tasks(limit=limit)
