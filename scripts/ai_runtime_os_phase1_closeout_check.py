"""AI Runtime OS phase-1 closeout checker.

This script is intentionally read-only. It validates that the phase-1
Dashboard closeout modules have service files, tests, dashboard keys,
export routes, searchable template titles, and no obvious execution hooks.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    {
        "name": "AI Runtime OS One-Page Console",
        "service": "services/ai_runtime_one_page_console_service.py",
        "test": "tests/test_ai_runtime_one_page_console_service.py",
        "dashboard_key": "ai_runtime_one_page_console",
        "export_route": "/ai-dashboard/runtime-one-page-console-export",
        "title": "AI Runtime OS 单页总控台",
    },
    {
        "name": "AI Runtime OS Layered Home",
        "service": "services/ai_runtime_layered_home_service.py",
        "test": "tests/test_ai_runtime_layered_home_service.py",
        "dashboard_key": "ai_runtime_layered_home",
        "export_route": "/ai-dashboard/runtime-layered-home-export",
        "title": "AI Runtime OS 分层首页",
    },
    {
        "name": "AI Runtime OS Entry Router",
        "service": "services/ai_runtime_entry_router_service.py",
        "test": "tests/test_ai_runtime_entry_router_service.py",
        "dashboard_key": "ai_runtime_entry_router",
        "export_route": "/ai-dashboard/runtime-entry-router-export",
        "title": "AI Runtime OS 入口路由器",
    },
    {
        "name": "AI Runtime OS Command Layer",
        "service": "services/ai_runtime_command_layer_service.py",
        "test": "tests/test_ai_runtime_command_layer_service.py",
        "dashboard_key": "ai_runtime_command_layer",
        "export_route": "/ai-dashboard/runtime-command-layer-export",
        "title": "AI Runtime 命令层",
    },
    {
        "name": "AI Runtime OS Policy Compiler",
        "service": "services/ai_runtime_policy_compiler_service.py",
        "test": "tests/test_ai_runtime_policy_compiler_service.py",
        "dashboard_key": "ai_runtime_policy_compiler",
        "export_route": "/ai-dashboard/runtime-policy-compiler-export",
        "title": "AI Runtime 策略编译器",
    },
    {
        "name": "AI Runtime OS Policy Linter",
        "service": "services/ai_runtime_policy_linter_service.py",
        "test": "tests/test_ai_runtime_policy_linter_service.py",
        "dashboard_key": "ai_runtime_policy_linter",
        "export_route": "/ai-dashboard/runtime-policy-linter-export",
        "title": "AI Runtime 策略静态检查器",
    },
    {
        "name": "AI Runtime OS Capability Matrix",
        "service": "services/ai_runtime_capability_matrix_service.py",
        "test": "tests/test_ai_runtime_capability_matrix_service.py",
        "dashboard_key": "ai_runtime_capability_matrix",
        "export_route": "/ai-dashboard/runtime-capability-matrix-export",
        "title": "AI Runtime OS 能力矩阵",
    },
    {
        "name": "AI Runtime OS Capability Governance",
        "service": "services/ai_runtime_capability_governance_service.py",
        "test": "tests/test_ai_runtime_capability_governance_service.py",
        "dashboard_key": "ai_runtime_capability_governance",
        "export_route": "/ai-dashboard/runtime-capability-governance-export",
        "title": "AI Runtime OS 能力治理层",
    },
    {
        "name": "AI Runtime Governance Summary Center",
        "service": "services/ai_runtime_governance_summary_service.py",
        "test": "tests/test_ai_runtime_governance_summary_service.py",
        "dashboard_key": "ai_runtime_governance_summary",
        "export_route": "/ai-dashboard/governance-summary-export",
        "title": "AI Runtime 治理汇总中心",
    },
    {
        "name": "AI Runtime OS Daily Operator Brief",
        "service": "services/ai_runtime_daily_operator_brief_service.py",
        "test": "tests/test_ai_runtime_daily_operator_brief_service.py",
        "dashboard_key": "ai_runtime_daily_operator_brief",
        "export_route": "/ai-dashboard/runtime-daily-operator-brief-export",
        "title": "AI Runtime OS 每日操作简报",
    },
    {
        "name": "AI Runtime OS Weekly Executive Report",
        "service": "services/ai_runtime_weekly_executive_report_service.py",
        "test": "tests/test_ai_runtime_weekly_executive_report_service.py",
        "dashboard_key": "ai_runtime_weekly_executive_report",
        "export_route": "/ai-dashboard/runtime-weekly-executive-report-export",
        "title": "AI Runtime OS 每周高管报告",
    },
    {
        "name": "AI Runtime OS Monthly Board Report",
        "service": "services/ai_runtime_monthly_board_report_service.py",
        "test": "tests/test_ai_runtime_monthly_board_report_service.py",
        "dashboard_key": "ai_runtime_monthly_board_report",
        "export_route": "/ai-dashboard/runtime-monthly-board-report-export",
        "title": "AI Runtime OS 月度董事会报告",
    },
]

FORBIDDEN_SNIPPETS = [
    "def execute",
    "def apply",
    "def dispatch",
    "def run",
    "publish_approved_articles",
    "subprocess",
]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def main() -> int:
    app_source = read_text("web_ui/app.py")
    template_source = read_text("web_ui/templates/ai_dashboard.html")
    failures: list[str] = []

    for module in MODULES:
        service_path = module["service"]
        test_path = module["test"]
        service_source = read_text(service_path) if exists(service_path) else ""

        checks = [
            (exists(service_path), f"{module['name']}: missing service {service_path}"),
            (exists(test_path), f"{module['name']}: missing test {test_path}"),
            (module["dashboard_key"] in app_source, f"{module['name']}: missing dashboard key {module['dashboard_key']}"),
            (module["export_route"] in app_source, f"{module['name']}: missing export route {module['export_route']}"),
            (module["title"] in template_source, f"{module['name']}: missing searchable title {module['title']}"),
            ("format=txt" in template_source and "format=csv" in template_source and "format=md" in template_source, f"{module['name']}: missing export format links"),
        ]
        for passed, message in checks:
            if not passed:
                failures.append(message)
        for forbidden in FORBIDDEN_SNIPPETS:
            if forbidden in service_source:
                failures.append(f"{module['name']}: forbidden execution snippet found: {forbidden}")

    if failures:
        print("AI Runtime OS Phase-1 Closeout: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("AI Runtime OS Phase-1 Closeout: OK")
    print(f"Verified modules: {len(MODULES)}")
    for module in MODULES:
        print(f"- {module['name']} / {module['dashboard_key']} / {module['export_route']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
