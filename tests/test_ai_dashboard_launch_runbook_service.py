import unittest
from unittest.mock import Mock, patch

from services.ai_dashboard_launch_runbook_service import AIDashboardLaunchRunbookService


class AIDashboardLaunchRunbookServiceTest(unittest.TestCase):
    def _source(self, status="ready"):
        return {
            "runbook_status": status,
            "summary": "runbook ok",
            "pre_release_steps": [{"step": "pre", "owner": "dev", "verification": "check", "notes": "notes"}],
            "release_steps": [{"step": "launch", "owner": "ops", "verification": "deploy", "notes": "notes"}],
            "post_release_validation": [{"step": "post", "owner": "qa", "verification": "200", "notes": "notes"}],
            "rollback_steps": [{"step": "rollback", "owner": "ops", "verification": "restore", "notes": "notes"}],
            "responsibility_matrix": [{"role": "dev", "responsibility": "tests", "checkpoints": ["unit"]}],
            "risk_playbooks": [{"risk": "route", "owner": "dev", "response": "fix"}],
            "verification_commands": [{"command": "python -m unittest", "purpose": "tests"}],
            "completion_checklist": [{"item": "confirm", "status": "manual", "summary": "manual"}],
            "recommended_actions": ["go"],
        }

    def test_build_launch_runbook_center_returns_required_fields(self):
        with patch(
            "services.ai_dashboard_launch_runbook_service.AIDashboardReleaseRunbookService.build_release_runbook_center",
            Mock(return_value=self._source()),
        ):
            center = AIDashboardLaunchRunbookService.build_launch_runbook_center()
        for key in [
            "runbook_status",
            "runbook_version",
            "summary",
            "launch_scope",
            "pre_launch_steps",
            "launch_steps",
            "post_launch_steps",
            "rollback_steps",
            "verification_steps",
            "manual_confirmation_items",
            "owner_checklist",
            "risk_checklist",
            "emergency_contacts",
            "recommended_actions",
        ]:
            self.assertIn(key, center)

    def test_needs_review_maps_to_draft(self):
        with patch(
            "services.ai_dashboard_launch_runbook_service.AIDashboardReleaseRunbookService.build_release_runbook_center",
            Mock(return_value=self._source("needs_review")),
        ):
            center = AIDashboardLaunchRunbookService.build_launch_runbook_center()
        self.assertEqual(center["runbook_status"], "draft")

    def test_text_and_rows_export(self):
        with patch(
            "services.ai_dashboard_launch_runbook_service.AIDashboardReleaseRunbookService.build_release_runbook_center",
            Mock(return_value=self._source()),
        ):
            center = AIDashboardLaunchRunbookService.build_launch_runbook_center()
        self.assertIn("【AI Dashboard 上线执行手册中心】", AIDashboardLaunchRunbookService.build_launch_runbook_text(center))
        rows = AIDashboardLaunchRunbookService.build_launch_runbook_rows(center)
        self.assertTrue(rows)
        self.assertIn("阶段", rows[0])
        self.assertIn("是否需要人工确认", rows[0])

    def test_routes_registered_and_accessible(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/launch-runbook", rules)
        self.assertIn("/ai-dashboard/launch-runbook-export", rules)

        center = {
            "runbook_status": "ready",
            "runbook_version": "test",
            "summary": "ok",
            "launch_scope": {},
            "pre_launch_steps": [],
            "launch_steps": [],
            "post_launch_steps": [],
            "rollback_steps": [],
            "verification_steps": [],
            "manual_confirmation_items": [],
            "owner_checklist": [],
            "risk_checklist": [],
            "emergency_contacts": [],
            "recommended_actions": [],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardLaunchRunbookService.build_launch_runbook_center", return_value=center):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                page = client.get("/ai-dashboard/launch-runbook")
                txt = client.get("/ai-dashboard/launch-runbook-export?format=txt")
                csv = client.get("/ai-dashboard/launch-runbook-export?format=csv")
        self.assertEqual(page.status_code, 200)
        self.assertIn("AI Dashboard 上线执行手册中心".encode("utf-8"), page.data)
        self.assertEqual(txt.status_code, 200)
        self.assertEqual(csv.status_code, 200)

    def test_dashboard_template_contains_launch_runbook_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 上线执行手册中心", template)
        self.assertIn("查看上线执行手册详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)
        self.assertIn("当前暂无 Dashboard 上线执行手册数据。", template)
        self.assertIn("ai_dashboard_launch_runbook_center", template)


if __name__ == "__main__":
    unittest.main()
