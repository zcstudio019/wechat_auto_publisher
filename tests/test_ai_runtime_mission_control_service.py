import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_mission_control_service import AIRuntimeMissionControlService


class AIRuntimeMissionControlServiceTest(unittest.TestCase):
    def _dashboard_fixture(self):
        return {
            "ai_dashboard_workspace_center": {
                "recommended_workspace": {
                    "title": "管理者工作台",
                    "summary": "workspace ok",
                    "reason": "normal",
                }
            },
            "ai_runtime_forecast_center": {
                "forecast_status": "normal",
                "potential_risks": [{"title": "关注趋势波动", "summary": "观察 Runtime 趋势", "priority": "medium"}],
                "future_trends": [{"title": "健康趋势观察", "summary": "继续观察"}],
            },
            "ai_runtime_predictive_action_center": {
                "priority_actions": [{"title": "复核预测动作", "summary": "只读复核", "priority": "high"}],
                "potential_blockers": [{"title": "潜在阻塞", "summary": "blocked runtime path", "priority": "critical"}],
            },
            "ai_runtime_continuous_improvement_center": {
                "recommended_actions": ["沉淀改进建议"],
            },
            "ai_dashboard_ops_maintenance_center": {
                "today_tasks": [{"task": "检查运维健康", "reason": "daily check", "priority": "medium"}],
            },
            "ai_dashboard_export_operations_center": {
                "operations_status": "normal",
                "warnings": ["检查导出归档"],
            },
            "ai_runtime_alert_center": {
                "alert_status": "normal",
                "warning_alerts": [{"title": "运行时提醒", "summary": "warning alert"}],
            },
            "ai_runtime_incident_center": {"incident_status": "none", "critical_incidents": []},
            "ai_dashboard_ops_health_center": {"ops_status": "healthy"},
        }

    def test_build_mission_control_center_returns_dict(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertIsInstance(center, dict)
        self.assertIn("task_command_status", center)
        self.assertIn("today_command", center)
        self.assertIn("task_groups", center)
        self.assertIn("priority_tasks", center)
        self.assertIn("manual_confirm_tasks", center)
        self.assertIn("blocked_tasks", center)
        self.assertIn("runtime_dependencies", center)
        self.assertIn("execution_order", center)
        self.assertIn("risk_tasks", center)
        self.assertIn("mission_status", center)
        self.assertIn("today_missions", center)

    def test_today_missions_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["today_missions"])

    def test_critical_missions_returns_list(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertIsInstance(center["critical_missions"], list)

    def test_recommended_execution_order_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_execution_order"])

    def test_recommended_workspaces_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_workspaces"])

    def test_recommended_exports_is_not_empty(self):
        center = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        self.assertTrue(center["recommended_exports"])

    def test_critical_status_from_incident(self):
        dashboard = self._dashboard_fixture()
        dashboard["ai_runtime_incident_center"]["incident_status"] = "critical"
        center = AIRuntimeMissionControlService.build_mission_control_center(dashboard)
        self.assertEqual(center["mission_status"], "critical")

    def test_markdown_export_contains_title(self):
        markdown = AIRuntimeMissionControlService.build_mission_control_markdown(
            AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        )
        self.assertIn("# AI Runtime 任务指挥中心", markdown)
        self.assertIn("## 今日任务", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-task-command", rules)
        self.assertIn("/ai-dashboard/runtime-task-command-export", rules)
        self.assertIn("/ai-dashboard/mission-control", rules)
        self.assertIn("/ai-dashboard/mission-control-export", rules)

        fixture = AIRuntimeMissionControlService.build_mission_control_center(self._dashboard_fixture())
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={}):
            with patch("web_ui.app.AIRuntimeMissionControlService.build_mission_control_center", return_value=fixture):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    response = client.get("/ai-dashboard/runtime-task-command")
                    txt_response = client.get("/ai-dashboard/runtime-task-command-export?format=txt")
                    csv_response = client.get("/ai-dashboard/runtime-task-command-export?format=csv")
                    md_response = client.get("/ai-dashboard/runtime-task-command-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Runtime 任务指挥中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 400)

    def test_ai_dashboard_template_contains_quick_entry_matrix(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Dashboard 快捷入口", template)
        for title in [
            "管理首页",
            "工作台中心",
            "任务指挥中心",
            "高管仪表盘",
            "运维健康",
            "导出运营",
            "文档中心",
            "导航中心",
            "架构地图",
            "冒烟测试",
        ]:
            self.assertIn(title, template)
        self.assertIn("展开全部", template)
        self.assertIn("收起全部", template)

    def test_ai_dashboard_template_keeps_core_center_titles_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        for title in [
            "AI Dashboard 管理首页中心",
            "AI Dashboard 工作台中心",
            "AI Runtime 任务指挥中心",
            "AI Runtime Executive Dashboard Center",
            "AI Dashboard 运维健康中心",
            "AI Dashboard 导出运营中心",
            "AI Dashboard 文档中心",
            "AI Dashboard 导航与索引中心",
            "AI Dashboard 系统架构地图中心",
            "AI Dashboard 冒烟测试中心",
        ]:
            self.assertIn(title, template)

    def test_ai_dashboard_template_contains_advanced_runtime_archive(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("高级 Runtime 分析归档区", template)
        self.assertIn("以下模块用于深度诊断、长期治理、因果推断、战略演化和文明级安全分析，默认折叠，必要时展开。", template)
        self.assertIn("advanced-runtime-analysis-archive", template)
        self.assertIn("展开高级分析", template)
        self.assertIn("收起高级分析", template)
        self.assertIn('<div class="collapse" id="advanced-runtime-analysis-archive">', template)

    def test_ai_dashboard_template_keeps_visible_runtime_center_titles(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        for title in [
            "AI Runtime OS 分层首页",
            "AI Runtime 高层摘要中心",
            "AI Runtime 实用控制台",
            "AI Runtime 操作系统内核",
            "AI Dashboard 管理首页中心",
            "AI Dashboard 工作台中心",
            "AI Runtime 任务指挥中心",
            "AI Dashboard 动作启动台中心",
            "AI Dashboard 模块搜索中心",
        ]:
            self.assertIn(title, template)

    def test_ai_dashboard_template_keeps_deep_runtime_titles_searchable(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        for title in [
            "AI Runtime 事件时间线",
            "AI Runtime 信号智能中心",
            "AI Runtime 关联分析中心",
            "AI Runtime 因果图谱中心",
            "AI Runtime 干预计划中心",
            "AI Runtime 决策中心",
            "AI Runtime 模拟推演中心",
            "AI Runtime 战略中心",
            "AI Runtime 记忆中心",
            "AI Runtime 元认知中心",
            "AI Runtime 判断中心",
            "AI Runtime 治理法庭中心",
            "AI Runtime 文明中心",
            "AI Runtime 完整性中心",
            "AI Runtime 免疫系统中心",
            "AI Runtime 自适应系统中心",
            "AI Runtime 韧性系统中心",
            "AI Runtime 演化适应度中心",
        ]:
            self.assertIn(title, template)

    def test_ai_dashboard_keeps_runtime_dashboard_keys(self):
        app_source = Path("web_ui/app.py").read_text(encoding="utf-8")
        for key in [
            "ai_runtime_executive_digest_center",
            "ai_runtime_command_layer",
            "ai_runtime_policy_compiler",
            "ai_runtime_policy_linter",
            "ai_runtime_capability_matrix",
            "ai_runtime_capability_governance",
            "ai_runtime_governance_summary",
            "ai_runtime_daily_operator_brief",
            "ai_runtime_weekly_executive_report",
            "ai_runtime_monthly_board_report",
            "ai_runtime_entry_router",
            "ai_runtime_layered_home",
            "ai_runtime_one_page_console",
            "ai_runtime_practical_console",
            "ai_runtime_os_kernel",
            "ai_dashboard_admin_home_center",
            "ai_dashboard_workspace_center",
            "ai_runtime_mission_control_center",
            "ai_dashboard_action_launchpad_center",
            "ai_dashboard_module_search_center",
            "ai_runtime_event_timeline",
            "ai_runtime_signal_intelligence",
            "ai_runtime_correlation_center",
            "ai_runtime_causal_graph_center",
            "ai_runtime_intervention_center",
            "ai_runtime_decision_center",
            "ai_runtime_simulation_center",
            "ai_runtime_strategy_center",
            "ai_runtime_memory_center",
            "ai_runtime_metacognition_center",
            "ai_runtime_judgment_center",
            "ai_runtime_governance_court_center",
            "ai_runtime_civilization_center",
            "ai_runtime_integrity_center",
            "ai_runtime_immune_center",
            "ai_runtime_adaptive_center",
            "ai_runtime_resilience_center",
            "ai_runtime_evolutionary_fitness_center",
        ]:
            self.assertIn(key, app_source)

    def test_existing_dashboard_routes_and_exports_are_kept(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        for route in [
            "/ai-dashboard/smoke-test",
            "/ai-dashboard/ops-health",
            "/ai-dashboard/export-operations",
            "/ai-dashboard/documentation",
            "/ai-dashboard/navigation",
            "/ai-dashboard/architecture-map",
            "/ai-dashboard/home",
            "/ai-dashboard/workspace",
            "/ai-dashboard/mission-control",
        ]:
            self.assertIn(route, rules)
        for route in [
            "/ai-dashboard/home-export",
            "/ai-dashboard/workspace-export",
            "/ai-dashboard/mission-control-export",
            "/ai-dashboard/documentation-export",
            "/ai-dashboard/navigation-export",
            "/ai-dashboard/architecture-map-export",
            "/ai-dashboard/ops-health-export",
            "/ai-dashboard/export-all-reports",
        ]:
            self.assertIn(route, rules)
        for route in [
            "/ai-dashboard/executive-digest-export",
            "/ai-dashboard/runtime-command-layer-export",
            "/ai-dashboard/runtime-policy-compiler-export",
            "/ai-dashboard/runtime-policy-linter-export",
            "/ai-dashboard/runtime-capability-matrix-export",
            "/ai-dashboard/runtime-capability-governance-export",
            "/ai-dashboard/governance-summary-export",
            "/ai-dashboard/runtime-daily-operator-brief-export",
            "/ai-dashboard/runtime-weekly-executive-report-export",
            "/ai-dashboard/runtime-monthly-board-report-export",
            "/ai-dashboard/runtime-entry-router-export",
            "/ai-dashboard/runtime-layered-home-export",
            "/ai-dashboard/runtime-one-page-console-export",
            "/ai-dashboard/runtime-practical-console-export",
            "/ai-dashboard/runtime-os-kernel-export",
            "/ai-dashboard/runtime-event-timeline-export",
            "/ai-dashboard/runtime-signal-intelligence-export",
            "/ai-dashboard/runtime-correlation-export",
            "/ai-dashboard/runtime-causal-graph-export",
            "/ai-dashboard/runtime-intervention-export",
            "/ai-dashboard/runtime-decision-export",
            "/ai-dashboard/runtime-simulation-export",
            "/ai-dashboard/runtime-strategy-export",
            "/ai-dashboard/runtime-memory-export",
            "/ai-dashboard/runtime-metacognition-export",
            "/ai-dashboard/runtime-judgment-export",
            "/ai-dashboard/runtime-governance-court-export",
            "/ai-dashboard/runtime-civilization-export",
            "/ai-dashboard/runtime-integrity-export",
            "/ai-dashboard/runtime-immune-export",
            "/ai-dashboard/runtime-adaptive-export",
            "/ai-dashboard/runtime-resilience-export",
            "/ai-dashboard/runtime-evolutionary-fitness-export",
            "/ai-dashboard/runtime-task-command-export",
        ]:
            self.assertIn(route, rules)


if __name__ == "__main__":
    unittest.main()
