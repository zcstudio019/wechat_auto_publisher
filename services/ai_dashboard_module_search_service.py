from __future__ import annotations

from services.ai_dashboard_documentation_service import AIDashboardDocumentationService
from services.ai_dashboard_navigation_service import AIDashboardNavigationService


class AIDashboardModuleSearchService:
    """Read-only module search index for AI Dashboard centers."""

    SUGGESTED_KEYWORDS = [
        "Runtime",
        "导出",
        "文档",
        "运维",
        "架构",
        "快照",
        "预测",
        "信任",
        "宪法",
        "工作台",
        "任务",
        "冒烟测试",
    ]

    QUICK_FILTERS = [
        {"label": "Runtime", "query": "Runtime"},
        {"label": "Ops", "query": "Ops"},
        {"label": "Export", "query": "Export"},
        {"label": "Documentation", "query": "Documentation"},
        {"label": "Architecture", "query": "Architecture"},
        {"label": "Governance", "query": "Governance"},
        {"label": "Workspace", "query": "Workspace"},
        {"label": "Test", "query": "Test"},
    ]

    FALLBACK_MODULES = [
        {
            "title": "Runtime Observability",
            "chinese_name": "AI 运行时可观测中心",
            "category": "Runtime",
            "dashboard_key": "ai_runtime_observability_center",
            "route": "/ai-dashboard",
            "export_route": "",
            "service_file": "services/article_health_service.py",
            "test_file": "tests/test_article_health_service.py",
            "summary": "Runtime health and observability overview.",
        },
        {
            "title": "Export Operations",
            "chinese_name": "AI Dashboard 导出运营中心",
            "category": "Export",
            "dashboard_key": "ai_dashboard_export_operations_center",
            "route": "/ai-dashboard/export-operations",
            "export_route": "/ai-dashboard/export-all-reports",
            "service_file": "services/ai_dashboard_export_operations_service.py",
            "test_file": "tests/test_ai_dashboard_export_operations_service.py",
            "summary": "Batch export, scheduler history, files and notification status.",
        },
        {
            "title": "Documentation Center",
            "chinese_name": "AI Dashboard 文档中心",
            "category": "Documentation",
            "dashboard_key": "ai_dashboard_documentation_center",
            "route": "/ai-dashboard/documentation",
            "export_route": "/ai-dashboard/documentation-export",
            "service_file": "services/ai_dashboard_documentation_service.py",
            "test_file": "tests/test_ai_dashboard_documentation_service.py",
            "summary": "Module catalog, routes, exports, services and readonly matrix.",
        },
    ]

    @classmethod
    def build_module_search_center(cls, query: str = "", dashboard: dict | None = None) -> dict:
        if isinstance(query, dict):
            dashboard = query
            query = ""
        query = (query or "").strip()
        search_index = cls._build_search_index()
        results = cls._search(search_index, query) if query else cls._recommended_results(search_index)
        if not search_index:
            status = "idle"
        elif query and not results:
            status = "attention"
        else:
            status = "normal"

        return {
            "search_status": status,
            "query": query,
            "summary": cls._build_summary(status, query, search_index, results),
            "search_entry": {
                "title": "AI Dashboard 模块搜索中心",
                "route": "/ai-dashboard/module-search",
                "export_txt": "/ai-dashboard/module-search-export?format=txt",
                "export_csv": "/ai-dashboard/module-search-export?format=csv",
                "status": status,
                "summary": "按模块名称、关键词、Dashboard key、路径和导出入口进行只读索引。",
            },
            "search_index": search_index,
            "module_keywords": cls._build_module_keywords(),
            "runtime_modules": cls._category_modules(search_index, {"Runtime", "Executive"}),
            "export_modules": cls._category_modules(search_index, {"Export"}),
            "ops_modules": cls._category_modules(search_index, {"Ops"}),
            "governance_modules": cls._category_modules(search_index, {"Governance"}),
            "documentation_modules": cls._category_modules(search_index, {"Documentation"}),
            "navigation_modules": cls._category_modules(search_index, {"Navigation", "Architecture", "General"}),
            "missing_search_targets": cls._build_missing_search_targets(search_index, dashboard or {}),
            "results": results,
            "suggested_keywords": cls.SUGGESTED_KEYWORDS,
            "quick_filters": cls.QUICK_FILTERS,
            "recommended_actions": cls._build_recommended_actions(status),
        }

    @classmethod
    def _build_module_keywords(cls) -> list[dict]:
        return [
            {"keyword": keyword, "type": "search", "status": "normal", "summary": f"可搜索 {keyword} 相关模块。"}
            for keyword in cls.SUGGESTED_KEYWORDS
        ]

    @staticmethod
    def _category_modules(search_index: list[dict], categories: set[str]) -> list[dict]:
        return [
            item
            for item in search_index
            if (item.get("category") or "General") in categories
        ][:30]

    @staticmethod
    def _build_missing_search_targets(search_index: list[dict], dashboard: dict) -> list[dict]:
        expected = {
            "ai_dashboard_module_search_center": "AI Dashboard 模块搜索中心",
            "ai_dashboard_ux_declutter_entry_reorder_center": "AI Dashboard 体验减负与入口重排",
            "ai_runtime_task_command_center": "AI Runtime 任务指挥中心",
        }
        indexed_keys = {item.get("dashboard_key") for item in search_index}
        missing = []
        for key, title in expected.items():
            if key not in indexed_keys and key not in dashboard:
                missing.append({
                    "title": title,
                    "dashboard_key": key,
                    "status": "missing",
                    "suggestion": "补充 Documentation / Navigation 索引中的模块目标。",
                })
        return missing

    @classmethod
    def _build_search_index(cls) -> list[dict]:
        items: dict[str, dict] = {}
        try:
            documentation = AIDashboardDocumentationService.build_documentation_center()
            for item in documentation.get("module_catalog") or []:
                normalized = cls._normalize_catalog_item(item)
                items[cls._identity(normalized)] = normalized
        except Exception:
            items = {}

        try:
            navigation = AIDashboardNavigationService.build_navigation_center()
            for item in navigation.get("module_index") or []:
                normalized = cls._normalize_navigation_item(item)
                key = cls._identity(normalized)
                if key in items:
                    items[key].update({k: v for k, v in normalized.items() if v})
                    items[key]["keywords"] = cls._merge_keywords(items[key], normalized)
                else:
                    items[key] = normalized
        except Exception:
            pass

        if not items:
            for item in cls.FALLBACK_MODULES:
                normalized = cls._with_keywords(dict(item))
                items[cls._identity(normalized)] = normalized

        return sorted(items.values(), key=lambda item: (item.get("category") or "", item.get("title") or ""))

    @classmethod
    def _normalize_catalog_item(cls, item: dict) -> dict:
        normalized = {
            "title": item.get("module_name") or item.get("title") or "",
            "chinese_name": item.get("chinese_name") or item.get("template_title") or "",
            "category": cls._category_from_layer(item.get("layer") or item.get("category") or ""),
            "dashboard_key": item.get("dashboard_key") or "",
            "route": item.get("route") or "",
            "export_route": item.get("export_route") or "",
            "service_file": item.get("service_file") or "",
            "test_file": item.get("test_file") or "",
            "summary": item.get("summary") or "",
        }
        return cls._with_keywords(normalized)

    @classmethod
    def _normalize_navigation_item(cls, item: dict) -> dict:
        normalized = {
            "title": item.get("module_name") or item.get("module") or item.get("title") or "",
            "chinese_name": item.get("chinese_name") or "",
            "category": item.get("category") or cls._category_from_layer(item.get("layer") or ""),
            "dashboard_key": item.get("dashboard_key") or "",
            "route": item.get("route") or "",
            "export_route": item.get("export_route") or "",
            "service_file": item.get("service_file") or "",
            "test_file": item.get("test_file") or "",
            "summary": item.get("summary") or "",
        }
        return cls._with_keywords(normalized)

    @staticmethod
    def _category_from_layer(layer: str) -> str:
        layer_lower = (layer or "").lower()
        if "export" in layer_lower:
            return "Export"
        if "ops" in layer_lower:
            return "Ops"
        if "documentation" in layer_lower:
            return "Documentation"
        if "architecture" in layer_lower:
            return "Architecture"
        if "governance" in layer_lower or "constitution" in layer_lower:
            return "Governance"
        if "trust" in layer_lower or "boundary" in layer_lower:
            return "Governance"
        if "forecast" in layer_lower or "snapshot" in layer_lower:
            return "Runtime"
        if "executive" in layer_lower:
            return "Executive"
        return "Runtime" if layer else "General"

    @classmethod
    def _with_keywords(cls, item: dict) -> dict:
        keywords = [
            item.get("title", ""),
            item.get("chinese_name", ""),
            item.get("category", ""),
            item.get("dashboard_key", ""),
            item.get("route", ""),
            item.get("export_route", ""),
            item.get("service_file", ""),
            item.get("test_file", ""),
        ]
        if "export" in " ".join(keywords).lower() or "导出" in item.get("chinese_name", ""):
            keywords.extend(["Export", "导出"])
        if "runtime" in " ".join(keywords).lower() or "运行时" in item.get("chinese_name", ""):
            keywords.extend(["Runtime", "运行时"])
        if "test" in " ".join(keywords).lower() or "测试" in item.get("chinese_name", ""):
            keywords.extend(["Test", "测试", "冒烟测试"])
        if "workspace" in " ".join(keywords).lower() or "工作台" in item.get("chinese_name", ""):
            keywords.extend(["Workspace", "工作台"])
        item["keywords"] = sorted({keyword for keyword in keywords if keyword})
        return item

    @staticmethod
    def _identity(item: dict) -> str:
        return item.get("dashboard_key") or item.get("title") or item.get("chinese_name") or item.get("route") or "unknown"

    @staticmethod
    def _merge_keywords(existing: dict, incoming: dict) -> list[str]:
        return sorted(set((existing.get("keywords") or []) + (incoming.get("keywords") or [])))

    @classmethod
    def _recommended_results(cls, search_index: list[dict]) -> list[dict]:
        preferred = [
            "Admin Home",
            "Workspace",
            "Mission Control",
            "Runtime Executive Dashboard",
            "Navigation Center",
            "Documentation Center",
            "Architecture Map",
            "Ops Health",
            "Export Operations",
            "Smoke Test",
        ]
        scored = []
        for item in search_index:
            title = item.get("title") or ""
            priority = next((index for index, name in enumerate(preferred) if name.lower() in title.lower()), len(preferred))
            scored.append((priority, cls._result_from_item(item, max(1, 100 - priority))))
        return [result for _, result in sorted(scored, key=lambda pair: (pair[0], pair[1]["title"]))[:20]]

    @classmethod
    def _search(cls, search_index: list[dict], query: str) -> list[dict]:
        query_lower = query.lower()
        tokens = [token for token in query_lower.split() if token]
        results = []
        for item in search_index:
            score = cls._score_item(item, query_lower, tokens)
            if score > 0:
                results.append(cls._result_from_item(item, score))
        return sorted(results, key=lambda item: (-item["score"], item["title"]))[:50]

    @staticmethod
    def _score_item(item: dict, query_lower: str, tokens: list[str]) -> int:
        fields = [
            ("title", 20),
            ("chinese_name", 20),
            ("category", 12),
            ("dashboard_key", 10),
            ("route", 10),
            ("export_route", 10),
            ("service_file", 8),
            ("test_file", 8),
            ("summary", 4),
        ]
        score = 0
        for field, weight in fields:
            value = str(item.get(field) or "").lower()
            if query_lower and query_lower in value:
                score += weight
            for token in tokens:
                if token in value:
                    score += max(1, weight // 2)
        keyword_text = " ".join(item.get("keywords") or []).lower()
        if query_lower in keyword_text:
            score += 12
        for token in tokens:
            if token in keyword_text:
                score += 6
        return score

    @staticmethod
    def _result_from_item(item: dict, score: int) -> dict:
        return {
            "title": item.get("title") or "",
            "chinese_name": item.get("chinese_name") or "",
            "category": item.get("category") or "",
            "route": item.get("route") or "",
            "export_route": item.get("export_route") or "",
            "dashboard_key": item.get("dashboard_key") or "",
            "summary": item.get("summary") or "",
            "score": score,
        }

    @staticmethod
    def _build_summary(status: str, query: str, search_index: list[dict], results: list[dict]) -> str:
        if status == "idle":
            return "AI Dashboard 模块搜索索引为空，请先检查 Documentation / Navigation Center。"
        if status == "attention":
            return f"未找到与“{query}”匹配的模块，可尝试 Runtime、导出、文档、运维等关键词。"
        if query:
            return f"已从 {len(search_index)} 个模块索引中找到 {len(results)} 条与“{query}”相关的结果。"
        return f"AI Dashboard 模块搜索中心已就绪，当前索引 {len(search_index)} 个模块，默认展示推荐模块。"

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        if status == "attention":
            return ["尝试使用推荐关键词重新搜索", "检查 Documentation Center 是否补齐模块信息", "使用 Navigation Center 按分类查找"]
        if status == "idle":
            return ["先恢复 Documentation / Navigation 索引", "检查模块目录和 Dashboard key 是否完整"]
        return ["优先搜索模块名称或 Dashboard key", "使用快速过滤定位 Runtime/Ops/Export 模块", "从结果进入独立页面或导出接口"]

    @classmethod
    def build_module_search_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_module_search_center()
        lines = [
            "【AI Dashboard 模块搜索中心】",
            f"查询词：{center.get('query') or '-'}",
            f"状态：{center.get('search_status') or '-'}",
            center.get("summary") or "",
            "",
            "搜索结果：",
        ]
        for item in center.get("results") or []:
            lines.append(
                f"- {item.get('title')} / {item.get('chinese_name')} [{item.get('category')}] "
                f"Route={item.get('route') or '-'} Export={item.get('export_route') or '-'}"
            )
        lines.append("")
        lines.append("推荐关键词：" + "、".join(center.get("suggested_keywords") or []))
        return "\n".join(lines)

    @classmethod
    def build_module_search_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_module_search_center()
        lines = [
            "# AI Dashboard 模块搜索中心",
            "",
            f"- 查询词：{center.get('query') or '-'}",
            f"- 搜索状态：{center.get('search_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 搜索结果",
        ]
        for item in center.get("results") or []:
            lines.append(
                f"- **{item.get('title')}**（{item.get('chinese_name') or '-'}）"
                f"：{item.get('summary') or '-'} Route: `{item.get('route') or '-'}`"
            )
        lines.extend([
            "",
            "## 推荐关键词",
            "、".join(center.get("suggested_keywords") or []),
            "",
            "## 快速过滤",
            "、".join(item.get("label", "") for item in center.get("quick_filters") or []),
        ])
        return "\n".join(lines)

    @classmethod
    def build_module_search_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_module_search_center()
        rows = []
        by_identity = {cls._identity(item): item for item in center.get("search_index") or []}
        by_title = {item.get("title"): item for item in center.get("search_index") or []}
        for result in center.get("results") or []:
            source = by_identity.get(result.get("dashboard_key")) or by_title.get(result.get("title")) or {}
            rows.append({
                "分类": result.get("category") or "",
                "模块名称": result.get("chinese_name") or result.get("title") or "",
                "关键词": "、".join(source.get("keywords") or []),
                "路径/锚点": result.get("route") or result.get("export_route") or "",
                "状态": center.get("search_status") or "",
                "说明": result.get("summary") or "",
                "建议": "从搜索结果进入对应详情页或导出入口。",
            })
        if not rows:
            rows.append({
                "分类": "搜索模块",
                "模块名称": "当前暂无 Dashboard 模块搜索数据。",
                "关键词": center.get("query") or "",
                "路径/锚点": "",
                "状态": center.get("search_status") or "idle",
                "说明": center.get("summary") or "当前暂无 Dashboard 模块搜索数据。",
                "建议": "尝试使用 Runtime、导出、文档、运维等关键词。",
            })
        return rows
