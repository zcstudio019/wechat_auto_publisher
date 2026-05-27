import unittest
from unittest.mock import Mock, patch

from services.ai_dashboard_release_runbook_service import AIDashboardReleaseRunbookService


class AIDashboardReleaseRunbookServiceTest(unittest.TestCase):
    def _readiness(self, status="ready"):
        return {
            "release_status": status,
            "summary": "readiness ok",
            "warning_checks": [{"name": "warn"}] if status == "conditional" else [],
            "acceptable_risks": [{"risk": "accepted"}] if status == "conditional" else [],
            "blocking_checks": [{"name": "block", "summary": "blocked"}] if status == "blocked" else [],
        }

    def _package(self, status="complete"):
        return {
            "package_status": status,
            "summary": "package ok",
            "blocking_issues": [{"item": "block", "summary": "blocked"}] if status == "blocked" else [],
            "rollback_package": [{"item": "Git tag", "summary": "tag"}],
            "manual_confirmation_items": [] if status in {"complete", "packaged"} else [{"item": "manual"}],
        }

    def _hardening(self, status="safe"):
        return {"hardening_status": status, "summary": "hardening ok"}

    def _ops(self, status="healthy"):
        return {"ops_status": status, "summary": "ops ok"}

    def _smoke(self, status="passed", failed_count=0):
        return {"status": status, "failed_count": failed_count, "summary": "smoke ok"}

    def _patch_dependencies(self, readiness=None, release_package=None, hardening=None, ops=None, smoke=None):
        return patch.multiple(
            "services.ai_dashboard_release_runbook_service",
            AIDashboardReleaseReadinessService=Mock(
                build_release_readiness_center=Mock(return_value=readiness or self._readiness())
            ),
            AIDashboardReleasePackageService=Mock(
                build_release_package_center=Mock(return_value=release_package or self._package())
            ),
            AIDashboardProductionHardeningService=Mock(
                build_production_hardening_center=Mock(return_value=hardening or self._hardening())
            ),
            AIDashboardOpsHealthService=Mock(
                build_ops_health_center=Mock(return_value=ops or self._ops())
            ),
            AIDashboardSmokeTestService=Mock(
                run_smoke_test=Mock(return_value=smoke or self._smoke())
            ),
        )

    def test_build_release_runbook_center_returns_dict(self):
        with self._patch_dependencies():
            center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        self.assertIsInstance(center, dict)
        self.assertIn("runbook_status", center)

    def test_readiness_blocked_makes_runbook_blocked(self):
        with self._patch_dependencies(readiness=self._readiness("blocked")):
            center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        self.assertEqual(center["runbook_status"], "blocked")

    def test_package_blocked_makes_runbook_blocked(self):
        with self._patch_dependencies(release_package=self._package("blocked")):
            center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        self.assertEqual(center["runbook_status"], "blocked")

    def test_conditional_or_partial_makes_needs_review(self):
        with self._patch_dependencies(readiness=self._readiness("conditional"), release_package=self._package("partial")):
            center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        self.assertEqual(center["runbook_status"], "needs_review")

    def test_ready_and_complete_makes_ready(self):
        with self._patch_dependencies(readiness=self._readiness("ready"), release_package=self._package("complete")):
            center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        self.assertEqual(center["runbook_status"], "ready")

    def test_required_step_lists_are_not_empty(self):
        with self._patch_dependencies():
            center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        self.assertTrue(center["pre_release_steps"])
        self.assertTrue(center["release_steps"])
        self.assertTrue(center["rollback_steps"])
        self.assertTrue(center["verification_commands"])

    def test_markdown_export_contains_title(self):
        with self._patch_dependencies():
            markdown = AIDashboardReleaseRunbookService.build_release_runbook_markdown()
        self.assertIn("# AI Dashboard 上线执行手册中心", markdown)

    def test_routes_registered_and_page_title_exists(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/release-runbook", rules)
        self.assertIn("/ai-dashboard/release-runbook-export", rules)

        center = {
            "runbook_status": "ready",
            "summary": "ok",
            "pre_release_steps": [],
            "release_steps": [],
            "post_release_validation": [],
            "rollback_steps": [],
            "responsibility_matrix": [],
            "risk_playbooks": [],
            "verification_commands": [],
            "common_issues": [],
            "completion_checklist": [],
            "recommended_actions": [],
        }
        app.config["TESTING"] = True
        with patch("web_ui.app.AIDashboardReleaseRunbookService.build_release_runbook_center", return_value=center):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                response = client.get("/ai-dashboard/release-runbook")
                txt_response = client.get("/ai-dashboard/release-runbook-export?format=txt")
                csv_response = client.get("/ai-dashboard/release-runbook-export?format=csv")
                md_response = client.get("/ai-dashboard/release-runbook-export?format=md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Dashboard 上线执行手册中心".encode("utf-8"), response.data)
        self.assertEqual(txt_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)

    def test_dashboard_template_contains_release_runbook_entry(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Dashboard 上线执行手册中心", template)
        self.assertIn("查看上线执行手册详情", template)
        self.assertIn("导出 TXT", template)
        self.assertIn("导出 CSV", template)


if __name__ == "__main__":
    unittest.main()
