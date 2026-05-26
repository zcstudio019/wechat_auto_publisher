"""Compatibility wrapper for the AI Dashboard Action Launchpad center."""

from __future__ import annotations

from services.ai_dashboard_action_launcher_service import AIDashboardActionLauncherService


class AIDashboardActionLaunchpadService(AIDashboardActionLauncherService):
    """Expose the launchpad naming required by the Dashboard."""

