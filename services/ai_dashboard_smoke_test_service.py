"""AI Dashboard 运行时冒烟测试服务。

该服务只做只读检查：验证 Dashboard 聚合、Runtime key、模板标题、导出路由和 JSON 读取容错，
不执行审核、发布、Agent、worker 或文章修改动作。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from services.article_health_service import (
    AI_DASHBOARD_SNAPSHOT_FILE_PATH,
    AI_OPS_DUTY_HISTORY_FILE_PATH,
    AI_OPS_SCORE_HISTORY_FILE_PATH,
    ArticleHealthService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AI_DASHBOARD_TEMPLATE_PATH = PROJECT_ROOT / "web_ui" / "templates" / "ai_dashboard.html"
APP_PATH = PROJECT_ROOT / "web_ui" / "app.py"


class AIDashboardSmokeTestService:
    """运行 AI Dashboard 只读冒烟测试。"""

    RUNTIME_MODULES = [
        ("ai_runtime_observability_center", "AI 运行时可观测中心"),
        ("ai_runtime_alert_center", "AI 运行时告警中心"),
        ("ai_runtime_recovery_center", "AI 运行时恢复中心"),
        ("ai_runtime_incident_center", "AI 运行时事故中心"),
        ("ai_runtime_postmortem_center", "AI 运行时事故复盘中心"),
        ("ai_runtime_learning_center", "AI 运行时学习中心"),
        ("ai_runtime_knowledge_sync_center", "AI 运行时知识同步中心"),
        ("ai_runtime_weekly_review_center", "AI 运行时周复盘中心"),
        ("ai_runtime_feedback_loop_center", "AI 运行时反馈闭环中心"),
        ("ai_runtime_evolution_center", "AI 运行时进化中心"),
        ("ai_runtime_orchestrator_center", "AI 运行时编排中心"),
        ("ai_runtime_control_policy_center", "AI 运行时控制策略中心"),
        ("ai_runtime_policy_gate_center", "AI 运行时策略闸门中心"),
        ("ai_runtime_confidence_center", "AI 运行时置信度中心"),
        ("ai_runtime_trust_center", "AI 运行时信任中心"),
        ("ai_runtime_delegation_readiness_center", "AI 运行时授权准备度中心"),
        ("ai_runtime_boundary_center", "AI 运行时边界中心"),
        ("ai_runtime_constitution_center", "AI 运行时宪法中心"),
    ]

    EXPORT_ROUTES = [
        "/ai-dashboard/runtime-learning-export",
        "/ai-dashboard/runtime-knowledge-sync-export",
        "/ai-dashboard/runtime-weekly-review-export",
        "/ai-dashboard/runtime-feedback-loop-export",
        "/ai-dashboard/runtime-evolution-export",
        "/ai-dashboard/runtime-orchestrator-export",
        "/ai-dashboard/runtime-control-policy-export",
        "/ai-dashboard/runtime-policy-gate-export",
        "/ai-dashboard/runtime-confidence-export",
        "/ai-dashboard/runtime-trust-export",
        "/ai-dashboard/runtime-delegation-readiness-export",
        "/ai-dashboard/runtime-boundary-export",
        "/ai-dashboard/runtime-constitution-export",
    ]

    @classmethod
    def run_smoke_test(cls) -> dict:
        """执行只读冒烟测试并返回页面展示数据。"""
        checks: list[dict[str, Any]] = []
        dashboard: dict[str, Any] = {}
        centers: dict[str, Any] = {}

        try:
            dashboard = ArticleHealthService.build_ai_risk_dashboard()
            cls._add_check(
                checks,
                "Dashboard 聚合执行",
                "passed",
                "Dashboard 基础聚合可以正常执行。",
            )
        except Exception as exc:  # pragma: no cover - 防御性兜底
            cls._add_check(
                checks,
                "Dashboard 聚合执行",
                "failed",
                f"Dashboard 基础聚合失败：{exc}",
                "优先检查 ArticleHealthService.build_ai_risk_dashboard()。",
            )

        if dashboard:
            try:
                centers = ArticleHealthService.build_ai_dashboard_centers(dashboard)
                dashboard.update(centers)
                cls._add_check(
                    checks,
                    "Runtime Center 聚合执行",
                    "passed",
                    "Runtime Center 二次聚合可以正常执行。",
                )
            except Exception as exc:  # pragma: no cover - 防御性兜底
                cls._add_check(
                    checks,
                    "Runtime Center 聚合执行",
                    "failed",
                    f"Runtime Center 聚合失败：{exc}",
                    "检查 build_ai_dashboard_centers() 内部依赖顺序。",
                )
        else:
            cls._add_check(
                checks,
                "Runtime Center 聚合执行",
                "failed",
                "Dashboard 基础聚合无结果，无法继续检查 Runtime Center。",
                "先恢复 Dashboard 基础聚合。",
            )

        cls._check_runtime_keys(checks, dashboard)
        cls._check_runtime_center_shapes(checks, dashboard)
        cls._check_template_titles(checks)
        cls._check_export_routes(checks)
        cls._check_json_files(checks)
        cls._check_json_error_tolerance(checks)

        failed_checks = [item for item in checks if item.get("status") == "failed"]
        warning_checks = [item for item in checks if item.get("status") == "warning"]
        passed_checks = [item for item in checks if item.get("status") == "passed"]
        if failed_checks:
            status = "failed"
        elif warning_checks:
            status = "warning"
        else:
            status = "passed"

        recommended_actions = [
            item.get("recommended_action")
            for item in failed_checks + warning_checks
            if item.get("recommended_action")
        ]
        if not recommended_actions:
            recommended_actions = ["当前冒烟测试未发现阻断项，保持只读观察即可。"]

        return {
            "status": status,
            "summary": cls._build_summary(status, passed_checks, warning_checks, failed_checks),
            "checks": checks,
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "passed_checks": passed_checks,
            "recommended_actions": recommended_actions,
        }

    @classmethod
    def _check_runtime_keys(cls, checks: list[dict], dashboard: dict) -> None:
        missing_keys = [key for key, _title in cls.RUNTIME_MODULES if key not in dashboard]
        if missing_keys:
            cls._add_check(
                checks,
                "Runtime key 完整性",
                "failed",
                f"缺少 {len(missing_keys)} 个 Runtime key：{', '.join(missing_keys)}",
                "补齐缺失 Runtime Center 的 dashboard 挂载。",
            )
            return
        cls._add_check(checks, "Runtime key 完整性", "passed", "所有 Runtime key 均已挂载。")

    @classmethod
    def _check_runtime_center_shapes(cls, checks: list[dict], dashboard: dict) -> None:
        invalid_keys = [
            key for key, _title in cls.RUNTIME_MODULES
            if key in dashboard and not isinstance(dashboard.get(key), dict)
        ]
        if invalid_keys:
            cls._add_check(
                checks,
                "Runtime Center 数据结构",
                "failed",
                f"以下 Runtime Center 未返回 dict：{', '.join(invalid_keys)}",
                "确保 Runtime Center helper 返回 dict，并为空数据提供兜底。",
            )
            return
        cls._add_check(checks, "Runtime Center 数据结构", "passed", "所有 Runtime Center 均返回 dict。")

    @classmethod
    def _check_template_titles(cls, checks: list[dict]) -> None:
        try:
            template_text = AI_DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")
        except Exception as exc:
            cls._add_check(
                checks,
                "Runtime 中文标题模板检查",
                "failed",
                f"读取 ai_dashboard.html 失败：{exc}",
                "检查模板文件是否存在且可读。",
            )
            return

        missing_titles = [title for _key, title in cls.RUNTIME_MODULES if title not in template_text]
        if missing_titles:
            cls._add_check(
                checks,
                "Runtime 中文标题模板检查",
                "failed",
                f"模板缺少中文标题：{', '.join(missing_titles)}",
                "把缺失 Runtime 模块卡片补入 ai_dashboard.html。",
            )
            return
        cls._add_check(checks, "Runtime 中文标题模板检查", "passed", "所有 Runtime 中文标题均存在于模板。")

    @classmethod
    def _check_export_routes(cls, checks: list[dict]) -> None:
        try:
            app_text = APP_PATH.read_text(encoding="utf-8")
        except Exception as exc:
            cls._add_check(
                checks,
                "导出路由注册检查",
                "failed",
                f"读取 web_ui/app.py 失败：{exc}",
                "检查 app.py 是否存在且可读。",
            )
            return

        missing_routes = [route for route in cls.EXPORT_ROUTES if route not in app_text]
        if missing_routes:
            cls._add_check(
                checks,
                "导出路由注册检查",
                "failed",
                f"缺少导出路由：{', '.join(missing_routes)}",
                "在 app.py 中补齐缺失导出路由。",
            )
            return
        cls._add_check(checks, "导出路由注册检查", "passed", "关键 Runtime 导出路由均已注册。")

    @classmethod
    def _check_json_files(cls, checks: list[dict]) -> None:
        json_paths = [
            ("Dashboard 快照", AI_DASHBOARD_SNAPSHOT_FILE_PATH),
            ("运营评分历史", AI_OPS_SCORE_HISTORY_FILE_PATH),
            ("值班模式历史", AI_OPS_DUTY_HISTORY_FILE_PATH),
        ]
        unreadable = []
        missing = []
        for label, path in json_paths:
            if not os.path.exists(path):
                missing.append(label)
                continue
            try:
                with open(path, "r", encoding="utf-8") as json_file:
                    json_file.read(1)
            except Exception as exc:
                unreadable.append(f"{label}：{exc}")

        if unreadable:
            cls._add_check(
                checks,
                "关键 JSON 文件可读性",
                "warning",
                f"部分 JSON 文件不可读：{'; '.join(unreadable)}",
                "检查 data 目录文件权限或文件占用情况。",
            )
            return
        if missing:
            cls._add_check(
                checks,
                "关键 JSON 文件可读性",
                "warning",
                f"以下 JSON 文件暂不存在，将按首次访问处理：{', '.join(missing)}",
                "如需历史趋势，等待 Dashboard 正常访问后自动生成历史文件。",
            )
            return
        cls._add_check(checks, "关键 JSON 文件可读性", "passed", "关键 JSON 文件均可读。")

    @classmethod
    def _check_json_error_tolerance(cls, checks: list[dict]) -> None:
        try:
            ArticleHealthService._parse_result_json("{broken")
            ArticleHealthService._read_ai_dashboard_snapshot()
            ArticleHealthService._read_ai_ops_score_history()
            ArticleHealthService._read_ai_ops_duty_history()
        except Exception as exc:  # pragma: no cover - 防御性兜底
            cls._add_check(
                checks,
                "JSON 损坏容错",
                "failed",
                f"JSON 损坏容错失败：{exc}",
                "确保 JSON 读取方法捕获异常并返回空数据。",
            )
            return
        cls._add_check(checks, "JSON 损坏容错", "passed", "JSON 损坏或异常读取不会拖垮页面。")

    @staticmethod
    def _add_check(
        checks: list[dict],
        name: str,
        status: str,
        summary: str,
        recommended_action: str = "",
    ) -> None:
        checks.append({
            "name": name,
            "status": status,
            "summary": summary,
            "recommended_action": recommended_action,
        })

    @staticmethod
    def _build_summary(status: str, passed_checks: list, warning_checks: list, failed_checks: list) -> str:
        if status == "failed":
            return f"冒烟测试发现 {len(failed_checks)} 个阻断项、{len(warning_checks)} 个警告项，请优先处理失败检查。"
        if status == "warning":
            return f"冒烟测试通过核心链路，但存在 {len(warning_checks)} 个警告项。"
        return f"冒烟测试通过，共 {len(passed_checks)} 项检查正常。"
