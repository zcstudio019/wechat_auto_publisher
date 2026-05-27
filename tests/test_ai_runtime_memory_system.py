import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_event_bus import AIRuntimeEventBus
from services.ai_runtime_memory_engine import AIRuntimeMemoryEngine
from services.ai_runtime_memory_service import AIRuntimeMemoryService
from services.ai_runtime_memory_store import AIRuntimeMemoryStore


class AIRuntimeMemorySystemTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.tmpdir.name) / "ai_runtime_memory.json"
        self.event_path = Path(self.tmpdir.name) / "ai_runtime_events.json"
        self.store = AIRuntimeMemoryStore(self.memory_path)
        self.bus = AIRuntimeEventBus(self.event_path)
        self.engine = AIRuntimeMemoryEngine()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _events(self):
        return [
            {"event_key": "JSON_CORRUPTED", "severity": "critical", "layer": "L7 Diagnostics Layer"},
            {"event_key": "JSON_CORRUPTED", "severity": "critical", "layer": "L7 Diagnostics Layer"},
            {"event_key": "EXPORT_FAILED", "severity": "warning", "layer": "L8 Export / Documentation Layer"},
            {"event_key": "TRUST_DECREASED", "severity": "warning", "layer": "L6 Governance Layer"},
            {"event_key": "BOUNDARY_RISK", "severity": "critical", "layer": "L6 Governance Layer"},
            {"event_key": "POLICY_GATE_BLOCKED", "severity": "critical", "layer": "L6 Governance Layer"},
        ]

    def _signals(self):
        return [
            {"signal_key": "TRUST_COLLAPSE_RISK", "severity": "critical", "summary": "trust risk"},
            {"signal_key": "POLICY_CONFLICT_PATTERN", "severity": "critical", "summary": "policy conflict"},
            {"signal_key": "EVENT_STORM", "severity": "warning", "summary": "storm"},
        ]

    def _causal_graph(self):
        return {
            "root_causes": [
                {"node_id": "JSON_CORRUPTED", "severity": "critical", "confidence": "high"}
            ],
            "critical_paths": [
                {"path": ["JSON_CORRUPTED", "SMOKE_TEST_FAILED", "OPS_CRITICAL", "RELEASE_BLOCKED"], "severity": "critical"}
            ],
        }

    def _strategy_center(self):
        return {
            "strategy_status": "critical",
            "technical_debt_risks": [
                {"title": "JSON coupling", "severity": "critical", "summary": "JSON risk"},
                {"title": "Runtime high coupling", "severity": "critical", "summary": "Runtime coupling"},
                {"title": "export bottlenecks", "severity": "medium", "summary": "export bottleneck"},
            ],
        }

    def _memory_result(self):
        return self.engine.build_memory(
            self._events(),
            self._signals(),
            [{"source": "JSON_CORRUPTED", "target": "OPS_CRITICAL"}],
            self._causal_graph(),
            self._strategy_center(),
        )

    def test_memory_store_can_append(self):
        item = self.store.append_memory({
            "memory_type": "test",
            "title": "JSON lesson",
            "summary": "remember JSON instability",
            "risks": ["critical"],
        })
        self.assertEqual(item["title"], "JSON lesson")
        self.assertTrue(self.memory_path.exists())

    def test_memory_store_can_read(self):
        self.store.append_memory({"title": "readable memory", "summary": "ok"})
        memories = self.store.read_memories()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["title"], "readable memory")
        self.assertTrue(self.store.search_memories("readable"))

    def test_build_memory_returns_dict(self):
        result = self.engine.build_memory([], [], [], {}, {})
        self.assertIsInstance(result, dict)
        self.assertIn("memory_status", result)
        self.assertIn("organizational_wisdom", result)

    def test_repeated_patterns_generated(self):
        result = self._memory_result()
        patterns = {item["title"] for item in result["repeated_patterns"]}
        self.assertIn("recurring instability", patterns)
        self.assertIn("recurring governance conflict", patterns)

    def test_governance_lessons_generated(self):
        result = self._memory_result()
        lessons = {item["title"] for item in result["governance_lessons"]}
        self.assertIn("boundary too weak", lessons)
        self.assertIn("policy gate should precede automation", lessons)

    def test_stability_lessons_generated(self):
        result = self._memory_result()
        lessons = {item["title"] for item in result["stability_lessons"]}
        self.assertIn("JSON dependency increases fragility", lessons)

    def test_strategic_lessons_generated(self):
        result = self._memory_result()
        lessons = {item["title"] for item in result["strategic_lessons"]}
        self.assertIn("stability before automation", lessons)
        self.assertIn("simulation before intervention", lessons)

    def test_organizational_wisdom_generated(self):
        result = self._memory_result()
        wisdom = {item["title"] for item in result["organizational_wisdom"]}
        self.assertIn("不要在低 trust 时扩大自动化", wisdom)
        self.assertIn("治理缺失比功能缺失更危险", wisdom)

    def test_build_memory_center_returns_dict(self):
        self.store.append_memory({
            "memory_type": "stored",
            "title": "stored memory",
            "summary": "existing wisdom",
            "risks": ["critical"],
            "confidence": "high",
        })
        for event in self._events():
            self.bus.publish(event["event_key"])
        dashboard = {
            "ai_runtime_signal_intelligence": {"signals": self._signals()},
            "ai_runtime_correlation_center": {"correlations": []},
            "ai_runtime_causal_graph_center": self._causal_graph(),
            "ai_runtime_strategy_center": self._strategy_center(),
        }
        center = AIRuntimeMemoryService.build_memory_center(dashboard, self.store, self.bus)
        self.assertIsInstance(center, dict)
        self.assertIn("memory_status", center)
        self.assertTrue(center["recent_memories"])
        self.assertTrue(center["critical_memories"])

    def test_runtime_memory_export_route_registered(self):
        from web_ui.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-memory-export", rules)

        for event in self._events():
            self.bus.publish(event["event_key"])
        app.config["TESTING"] = True
        with patch.object(AIRuntimeEventBus, "EVENT_FILE_PATH", self.event_path):
            with patch.object(AIRuntimeMemoryStore, "MEMORY_FILE_PATH", self.memory_path):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    txt_response = client.get("/ai-dashboard/runtime-memory-export?format=txt")
                    csv_response = client.get("/ai-dashboard/runtime-memory-export?format=csv")
                    md_response = client.get("/ai-dashboard/runtime-memory-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("【AI Runtime 记忆中心】".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 记忆中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_memory_center_title(self):
        with open("web_ui/templates/ai_dashboard.html", encoding="utf-8") as file:
            template = file.read()
        self.assertIn("AI Runtime 记忆中心", template)


if __name__ == "__main__":
    unittest.main()
