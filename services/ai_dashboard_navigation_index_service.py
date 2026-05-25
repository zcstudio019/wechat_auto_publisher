"""Compatibility wrapper for the AI Dashboard navigation and index center."""

from __future__ import annotations

from services.ai_dashboard_navigation_service import AIDashboardNavigationService


class AIDashboardNavigationIndexService:
    """Expose the requested navigation-index service name without duplicating logic."""

    @staticmethod
    def build_navigation_index_center() -> dict:
        return AIDashboardNavigationService.build_navigation_index_center()

    @staticmethod
    def build_navigation_index_text(center: dict | None = None) -> str:
        return AIDashboardNavigationService.build_navigation_text(center)

    @staticmethod
    def build_navigation_index_rows(center: dict | None = None) -> list[dict]:
        return AIDashboardNavigationService.build_navigation_rows(center)
