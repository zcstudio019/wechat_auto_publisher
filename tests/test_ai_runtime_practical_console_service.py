import unittest

from services.ai_runtime_practical_console_service import AIRuntimePracticalConsoleService


class AIRuntimePracticalConsoleServiceTest(unittest.TestCase):
    def _dashboard(self):
        return {
            "ai_runtime_decision_center": {
                "decision_status": "critical",
                "blocked_decisions": [{"title": "policy gate blocked release", "risk": "critical"}],
                "high_risk_decisions": [{"title": "low trust decision", "risk": "critical"}],
            },
            "ai_runtime_intervention_center": {
                "blocking_interventions": [{"title": "block propagation", "priority": "critical"}],
                "root_cause_interventions": [{"title": "inspect json root cause", "priority": "high"}],
            },
            "ai_runtime_causal_graph_center": {
                "critical_paths": [{"title": "JSON -> Ops -> Release", "risk": "critical"}],
            },
            "ai_runtime_immune_center": {
                "immune_status": "critical",
                "systemic_risks": [{"title": "governance collapse chain", "risk": "critical"}],
                "governance_corruption_risks": [{"title": "automation bypassing governance", "risk": "critical"}],
            },
            "ai_dashboard_release_readiness_center": {
                "release_status": "blocked",
                "summary": "release blocked",
            },
            "ai_runtime_integrity_center": {
                "integrity_score": 42,
                "governance_conflicts": [{"title": "policy conflicts with constitution", "risk": "critical"}],
                "value_fragmentations": [{"title": "strategy values scaling", "risk": "high"}],
            },
            "ai_runtime_signal_intelligence": {
                "signal_status": "warning",
                "warning_signals": [{"signal_key": "REPEATED_WARNINGS", "severity": "warning"}],
            },
            "ai_runtime_correlation_center": {
                "correlation_status": "attention",
                "correlations": [{"source": "EXPORT_FAILED", "target": "OPS_WARNING", "confidence": "medium"}],
            },
            "ai_runtime_forecast_center": {
                "potential_risks": [{"title": "future governance complexity", "risk": "high"}],
            },
            "ai_runtime_adaptive_center": {
                "adaptive_status": "rigid",
                "environment_change_signals": [{"title": "runtime complexity increasing", "risk": "high"}],
                "aging_governance_patterns": [{"title": "governance rules outdated", "risk": "high"}],
            },
            "ai_runtime_resilience_center": {
                "resilience_status": "fragile",
                "stress_response_patterns": [{"title": "automation expands under pressure", "risk": "critical"}],
                "recommended_actions": ["Review fragility manually."],
            },
            "ai_runtime_judgment_center": {
                "dangerous_automations": [{"title": "autonomous approval", "risk": "critical"}],
            },
            "ai_runtime_governance_court_center": {
                "court_status": "critical",
                "forbidden_domains": [{"title": "autonomous publish", "risk": "critical"}],
            },
            "ai_runtime_civilization_center": {
                "forbidden_civilization_paths": [{"title": "uncontrolled automation civilization", "risk": "critical"}],
                "civilization_conflicts": [{"title": "efficiency conflicts with safety", "risk": "critical"}],
            },
            "ai_runtime_evolutionary_fitness_center": {
                "fitness_status": "unstable evolution",
                "extinction_risks": [{"title": "adaptive failure cascade", "risk": "critical"}],
                "recommended_actions": ["Review future fitness manually."],
            },
            "ai_runtime_strategy_center": {
                "stability_roadmap": [{"title": "restore Runtime stability", "priority": "critical"}],
                "governance_roadmap": [{"title": "standardize policy gate", "priority": "high"}],
            },
            "ai_runtime_memory_center": {
                "governance_lessons": [{"title": "policy gate should precede automation", "risk": "high"}],
                "stability_lessons": [{"title": "JSON dependency increases fragility", "risk": "high"}],
            },
            "ai_dashboard_ops_maintenance_center": {
                "recommended_actions": ["Review ops maintenance plan"],
            },
        }

    def test_build_practical_console_returns_dict(self):
        console = AIRuntimePracticalConsoleService.build_practical_console({})
        self.assertIsInstance(console, dict)
        self.assertIn("console_status", console)

    def test_must_handle_today_is_list(self):
        console = AIRuntimePracticalConsoleService.build_practical_console(self._dashboard())
        self.assertIsInstance(console["must_handle_today"], list)
        self.assertTrue(console["must_handle_today"])

    def test_observe_today_is_list(self):
        console = AIRuntimePracticalConsoleService.build_practical_console(self._dashboard())
        self.assertIsInstance(console["observe_today"], list)
        self.assertTrue(console["observe_today"])

    def test_never_automate_is_list(self):
        console = AIRuntimePracticalConsoleService.build_practical_console(self._dashboard())
        self.assertIsInstance(console["never_automate"], list)
        self.assertTrue(console["never_automate"])

    def test_long_term_governance_risks_is_list(self):
        console = AIRuntimePracticalConsoleService.build_practical_console(self._dashboard())
        self.assertIsInstance(console["long_term_governance_risks"], list)
        self.assertTrue(console["long_term_governance_risks"])

    def test_weekly_improvement_focus_is_list(self):
        console = AIRuntimePracticalConsoleService.build_practical_console(self._dashboard())
        self.assertIsInstance(console["weekly_improvement_focus"], list)
        self.assertTrue(console["weekly_improvement_focus"])

    def test_urgent_status_detected(self):
        console = AIRuntimePracticalConsoleService.build_practical_console(self._dashboard())
        self.assertEqual(console["console_status"], "urgent")

    def test_runtime_practical_console_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-practical-console-export", rules)

        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["role"] = "admin"
                sess["username"] = "admin"
            txt_response = client.get("/ai-dashboard/runtime-practical-console-export?format=txt")
            csv_response = client.get("/ai-dashboard/runtime-practical-console-export?format=csv")
            md_response = client.get("/ai-dashboard/runtime-practical-console-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 实用控制台】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("分类".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 实用控制台".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_practical_console_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 实用控制台", template)


if __name__ == "__main__":
    unittest.main()
