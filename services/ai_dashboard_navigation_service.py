"""Read-only AI Dashboard navigation and index center."""

from __future__ import annotations

from collections import defaultdict

from services.ai_dashboard_architecture_map_service import AIDashboardArchitectureMapService
from services.ai_dashboard_documentation_service import AIDashboardDocumentationService


class AIDashboardNavigationService:
    """Build navigation indexes from existing Dashboard documentation metadata."""

    CATEGORY_ORDER = [
        "Executive",
        "Runtime",
        "Forecast",
        "Trust & Boundary",
        "Governance",
        "Ops",
        "Export",
        "Architecture",
        "Documentation",
    ]
    MODULE_COMPLEX_THRESHOLD = 24
    MODULE_OVERLOADED_THRESHOLD = 45
    SINGLE_PAGE_OVERLOADED_THRESHOLD = 28
    RUNTIME_LAYER_OVERLOADED_THRESHOLD = 8

    @classmethod
    def build_navigation_center(cls) -> dict:
        documentation = AIDashboardDocumentationService.build_documentation_center()
        architecture = AIDashboardArchitectureMapService.build_architecture_map()
        module_index = cls._build_module_index(documentation.get("module_catalog") or [])
        category_navigation = cls._build_category_navigation(module_index)
        page_navigation = cls._build_page_navigation(module_index, documentation.get("route_docs") or [])
        export_navigation = cls._build_export_navigation(documentation.get("export_docs") or [])
        service_navigation = cls._build_service_navigation(module_index, documentation.get("service_docs") or [])
        route_navigation = cls._build_route_navigation(documentation.get("route_docs") or [])
        dashboard_key_navigation = cls._build_dashboard_key_navigation(module_index)
        recommended_paths = cls._build_recommended_paths()
        quick_actions = cls._build_quick_actions()
        raw_status = cls._resolve_navigation_status(module_index, category_navigation, architecture)
        navigation_status = cls._normalize_status(raw_status)
        quick_links = cls._build_quick_links(quick_actions)
        section_index = cls._build_section_index(category_navigation)
        runtime_index = cls._filter_index(module_index, "runtime")
        export_index = cls._build_export_index(export_navigation)
        ops_index = cls._filter_index(module_index, "ops")
        architecture_index = cls._filter_index(module_index, "architecture")
        documentation_index = cls._filter_index(module_index, "documentation")
        missing_links = cls._build_missing_links(module_index)
        broken_routes = cls._build_broken_routes(page_navigation, export_navigation)

        return {
            "navigation_status": navigation_status,
            "summary": cls._build_summary(navigation_status, module_index, category_navigation, route_navigation),
            "quick_links": quick_links,
            "section_index": section_index,
            "runtime_index": runtime_index,
            "export_index": export_index,
            "ops_index": ops_index,
            "architecture_index": architecture_index,
            "documentation_index": documentation_index,
            "missing_links": missing_links,
            "broken_routes": broken_routes,
            "recommended_actions": cls._build_recommended_actions(navigation_status),
            "category_navigation": category_navigation,
            "module_index": module_index,
            "page_navigation": page_navigation,
            "export_navigation": export_navigation,
            "service_navigation": service_navigation,
            "route_navigation": route_navigation,
            "dashboard_key_navigation": dashboard_key_navigation,
            "recommended_paths": recommended_paths,
            "quick_actions": quick_actions,
        }

    @classmethod
    def build_navigation_index_center(cls) -> dict:
        return cls.build_navigation_center()

    @staticmethod
    def _normalize_status(status: str) -> str:
        if status == "clear":
            return "normal"
        if status == "complex":
            return "attention"
        if status == "overloaded":
            return "warning"
        return status or "unknown"

    @staticmethod
    def _build_quick_links(quick_actions: list[dict]) -> list[dict]:
        return [
            {
                "type": "quick_link",
                "title": item.get("label") or "",
                "path": item.get("route") or "",
                "status": "normal" if item.get("route") else "missing",
                "summary": item.get("summary") or "",
                "suggestion": "保留快捷入口可用。",
            }
            for item in quick_actions
        ]

    @staticmethod
    def _build_section_index(category_navigation: list[dict]) -> list[dict]:
        return [
            {
                "type": "section",
                "title": item.get("category") or "",
                "path": "#overview-anchor",
                "status": "normal" if item.get("modules") else "idle",
                "summary": item.get("summary") or "",
                "suggestion": "按分区索引定位 Dashboard 模块。",
            }
            for item in category_navigation
        ]

    @classmethod
    def _filter_index(cls, module_index: list[dict], index_type: str) -> list[dict]:
        rows = []
        for item in module_index:
            category = item.get("category") or ""
            module_name = item.get("module_name") or ""
            if index_type == "runtime" and not module_name.startswith("Runtime"):
                continue
            if index_type == "ops" and category != "Ops":
                continue
            if index_type == "architecture" and category != "Architecture":
                continue
            if index_type == "documentation" and category != "Documentation":
                continue
            rows.append(cls._index_item(index_type, item.get("chinese_name") or module_name, item.get("route") or "", item.get("summary") or ""))
        return rows

    @classmethod
    def _build_export_index(cls, export_navigation: list[dict]) -> list[dict]:
        return [
            cls._index_item("export", item.get("module") or "", item.get("export_route") or "", item.get("summary") or "")
            for item in export_navigation
        ]

    @staticmethod
    def _index_item(index_type: str, title: str, path: str, summary: str) -> dict:
        return {
            "type": index_type,
            "title": title,
            "path": path,
            "status": "normal" if path else "missing",
            "summary": summary,
            "suggestion": "保持入口、路由和文档同步。",
        }

    @staticmethod
    def _build_missing_links(module_index: list[dict]) -> list[dict]:
        return [
            {
                "type": "route",
                "title": item.get("chinese_name") or item.get("module_name") or "",
                "path": item.get("route") or "",
                "status": "missing",
                "summary": "模块缺少可用页面入口。",
                "suggestion": "补齐只读页面入口或明确仅在主 Dashboard 展示。",
            }
            for item in module_index
            if not item.get("route")
        ]

    @staticmethod
    def _build_broken_routes(page_navigation: list[dict], export_navigation: list[dict]) -> list[dict]:
        broken = []
        for item in page_navigation:
            route = item.get("route") or ""
            if route and not route.startswith("/"):
                broken.append({"type": "route", "title": item.get("title") or "", "path": route, "status": "broken", "summary": "页面路由格式异常。", "suggestion": "检查路由是否以 / 开头。"})
        for item in export_navigation:
            route = item.get("export_route") or ""
            if route and not route.startswith("/"):
                broken.append({"type": "route", "title": item.get("module") or "", "path": route, "status": "broken", "summary": "导出路由格式异常。", "suggestion": "检查导出路由是否以 / 开头。"})
        return broken

    @classmethod
    def _build_module_index(cls, module_catalog: list[dict]) -> list[dict]:
        items = []
        for item in module_catalog:
            items.append({
                "module_name": item.get("module_name") or "",
                "chinese_name": item.get("chinese_name") or item.get("module_name") or "",
                "dashboard_key": item.get("dashboard_key") or "",
                "route": item.get("route") or "/ai-dashboard",
                "export_route": item.get("export_route") or "",
                "layer": item.get("layer") or "",
                "category": cls._category_for(item),
                "readonly": item.get("readonly", True),
                "service_file": item.get("service_file") or "",
                "has_standalone_page": bool(item.get("has_standalone_page")),
                "summary": item.get("summary") or "",
            })
        return items

    @classmethod
    def _build_category_navigation(cls, module_index: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in module_index:
            grouped[item.get("category") or "Runtime"].append(item)

        result = []
        for category in cls.CATEGORY_ORDER:
            modules = grouped.get(category, [])
            result.append({
                "category": category,
                "modules": [item.get("module_name") for item in modules],
                "summary": f"{category} 分类包含 {len(modules)} 个 Dashboard 模块。",
            })
        return result

    @staticmethod
    def _build_page_navigation(module_index: list[dict], route_docs: list[dict]) -> list[dict]:
        route_purpose = {item.get("route"): item.get("purpose") for item in route_docs}
        pages = []
        seen = set()
        for item in module_index:
            route = item.get("route") or ""
            if not route or route in seen:
                continue
            seen.add(route)
            title = item.get("chinese_name") or item.get("module_name") or route
            pages.append({
                "title": title,
                "route": route,
                "purpose": route_purpose.get(route) or item.get("summary") or "Dashboard 页面入口。",
            })
        return pages

    @staticmethod
    def _build_export_navigation(export_docs: list[dict]) -> list[dict]:
        result = []
        for item in export_docs:
            formats = [
                value.strip()
                for value in str(item.get("format") or "").replace(",", "/").split("/")
                if value.strip()
            ]
            result.append({
                "module": item.get("module") or item.get("title") or "",
                "export_route": item.get("export_route") or item.get("path") or "",
                "formats": formats,
                "summary": item.get("summary") or "",
            })
        return result

    @staticmethod
    def _build_service_navigation(module_index: list[dict], service_docs: list[dict]) -> list[dict]:
        modules_by_service: dict[str, list[str]] = defaultdict(list)
        for item in module_index:
            service_file = item.get("service_file") or ""
            if service_file:
                modules_by_service[service_file].append(item.get("module_name") or "")

        doc_by_service = {item.get("service_file"): item for item in service_docs}
        rows = []
        for service_file in sorted(modules_by_service):
            service_doc = doc_by_service.get(service_file) or {}
            rows.append({
                "service_file": service_file,
                "responsibility": service_doc.get("responsibility") or "Dashboard 模块索引服务。",
                "related_modules": modules_by_service[service_file],
            })
        return rows

    @staticmethod
    def _build_route_navigation(route_docs: list[dict]) -> list[dict]:
        return [
            {
                "route": item.get("route") or "",
                "method": item.get("method") or "GET",
                "summary": item.get("purpose") or item.get("summary") or "",
            }
            for item in route_docs
        ]

    @staticmethod
    def _build_dashboard_key_navigation(module_index: list[dict]) -> list[dict]:
        return [
            {
                "dashboard_key": item.get("dashboard_key") or "",
                "module": item.get("module_name") or "",
                "summary": item.get("summary") or "",
            }
            for item in module_index
            if item.get("dashboard_key")
        ]

    @staticmethod
    def _build_recommended_paths() -> list[dict]:
        return [
            {
                "name": "新手查看路径",
                "steps": ["Executive Dashboard", "Architecture Map", "Documentation", "Navigation"],
                "summary": "先看高管视图，再理解架构、文档和索引。",
            },
            {
                "name": "运维路径",
                "steps": ["Ops Health", "Ops Maintenance", "Export Operations", "Smoke Test"],
                "summary": "先定位健康风险，再查看维护计划、导出状态和冒烟测试。",
            },
            {
                "name": "Runtime 路径",
                "steps": ["Snapshot", "Timeline", "Forecast", "Predictive Action"],
                "summary": "从快照到时间线，再看预测和行动建议。",
            },
        ]

    @staticmethod
    def _build_quick_actions() -> list[dict]:
        return [
            {"label": "查看管理首页", "route": "/ai-dashboard/admin-home", "summary": "查看 AI Dashboard 管理首页中心。"},
            {"label": "查看 Executive Dashboard", "route": "/ai-dashboard", "summary": "返回 Dashboard 总控区。"},
            {"label": "查看 Architecture Map", "route": "/ai-dashboard/architecture-map", "summary": "查看系统架构地图。"},
            {"label": "查看 Documentation", "route": "/ai-dashboard/documentation", "summary": "查看文档中心。"},
            {"label": "查看 Ops Health", "route": "/ai-dashboard/ops-health", "summary": "查看运维健康中心。"},
            {"label": "查看 Export Operations", "route": "/ai-dashboard/export-operations", "summary": "查看导出运营中心。"},
            {"label": "查看 Smoke Test", "route": "/ai-dashboard/smoke-test", "summary": "查看冒烟测试中心。"},
            {"label": "查看导航与索引中心", "route": "/ai-dashboard/navigation-index", "summary": "查看导航与索引中心。"},
        ]

    @classmethod
    def _resolve_navigation_status(cls, module_index: list[dict], category_navigation: list[dict], architecture: dict) -> str:
        module_count = len(module_index)
        single_page_count = sum(1 for item in module_index if not item.get("has_standalone_page"))
        runtime_layers = architecture.get("runtime_layers") or []
        deepest_layer = max((len(item.get("modules") or []) for item in runtime_layers), default=0)

        if (
            module_count > cls.MODULE_OVERLOADED_THRESHOLD
            or single_page_count > cls.SINGLE_PAGE_OVERLOADED_THRESHOLD
            or deepest_layer > cls.RUNTIME_LAYER_OVERLOADED_THRESHOLD
        ):
            return "overloaded"
        if module_count > cls.MODULE_COMPLEX_THRESHOLD or len(category_navigation) > 7:
            return "complex"
        return "clear"

    @classmethod
    def _category_for(cls, item: dict) -> str:
        module_name = item.get("module_name") or ""
        layer = item.get("layer") or ""
        if "Executive" in module_name or layer == "Executive Layer":
            return "Executive"
        if "Architecture" in module_name:
            return "Architecture"
        if "Documentation" in module_name:
            return "Documentation"
        if "Export" in module_name or layer == "Export Layer":
            return "Export"
        if "Ops" in module_name or module_name == "Smoke Test" or layer == "Ops Layer":
            return "Ops"
        if "Trust" in layer or "Boundary" in layer or "Constitution" in module_name:
            return "Trust & Boundary"
        if "Governance" in layer or "Policy" in module_name or "Confidence" in module_name:
            return "Governance"
        if "Forecast" in layer or "Snapshot" in module_name or "Timeline" in module_name or "Forecast" in module_name or "Predictive" in module_name:
            return "Forecast"
        return "Runtime"

    @staticmethod
    def _build_summary(status: str, module_index: list[dict], category_navigation: list[dict], route_navigation: list[dict]) -> str:
        if status in {"warning", "overloaded"}:
            return f"AI Dashboard 已索引 {len(module_index)} 个模块，导航负载较高，建议优先使用分类和快速路径。"
        if status in {"attention", "complex"}:
            return f"AI Dashboard 已索引 {len(module_index)} 个模块、{len(route_navigation)} 条路由，分类导航可降低查找成本。"
        active_categories = sum(1 for item in category_navigation if item.get("modules"))
        return f"AI Dashboard 导航结构清晰，当前覆盖 {len(module_index)} 个模块和 {active_categories} 个有效分类。"

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        actions = [
            "新增 Dashboard 模块时同步加入文档中心和导航中心",
            "优先通过分类导航定位模块",
            "保留独立页面入口，减少总控页查找成本",
            "保持 Route / Service / Dashboard Key 索引一致",
            "为新增导出接口同步补充 Export 导航",
            "定期复查快速访问路径",
            "避免继续把所有信息堆叠到单一页面",
            "保持导航中心严格只读",
        ]
        if status in {"warning", "overloaded"}:
            actions.insert(0, "优先拆分高频模块入口，降低 Dashboard 单页导航负载")
        return actions[:8]

    @staticmethod
    def build_navigation_text(center: dict | None = None) -> str:
        center = center or AIDashboardNavigationService.build_navigation_center()
        lines = [
            "【AI Dashboard 导航与索引中心】",
            "",
            f"导航状态：{center.get('navigation_status') or '-'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "分类导航：",
        ]
        for item in center.get("section_index") or center.get("category_navigation") or []:
            if item.get("title"):
                lines.append(f"- {item.get('title')}：{item.get('summary') or '-'}")
                continue
            lines.append(f"- {item.get('category')}：{', '.join(item.get('modules') or []) or '-'}")
        lines.extend(["", "推荐访问路径："])
        for item in center.get("recommended_paths") or []:
            lines.append(f"- {item.get('name')}：{' -> '.join(item.get('steps') or [])}")
        return "\n".join(lines)

    @staticmethod
    def build_navigation_markdown(center: dict | None = None) -> str:
        center = center or AIDashboardNavigationService.build_navigation_center()
        lines = [
            "# AI Dashboard 导航与索引中心",
            "",
            f"- 导航状态：{center.get('navigation_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 分类导航",
        ]
        for item in center.get("category_navigation") or []:
            lines.append(f"- **{item.get('category')}**：{', '.join(item.get('modules') or []) or '-'}")
        lines.extend(["", "## 模块索引"])
        for item in center.get("module_index") or []:
            lines.append(f"- **{item.get('module_name')}**：`{item.get('dashboard_key')}` / `{item.get('route')}`")
        lines.extend(["", "## 页面导航"])
        for item in center.get("page_navigation") or []:
            lines.append(f"- `{item.get('route')}`：{item.get('title')}")
        lines.extend(["", "## Export 导航"])
        for item in center.get("export_navigation") or []:
            lines.append(f"- `{item.get('export_route')}`：{item.get('module')} / {', '.join(item.get('formats') or [])}")
        lines.extend(["", "## Route 导航"])
        for item in center.get("route_navigation") or []:
            lines.append(f"- `{item.get('route')}`：{item.get('method')} / {item.get('summary')}")
        lines.extend(["", "## Dashboard Key 索引"])
        for item in center.get("dashboard_key_navigation") or []:
            lines.append(f"- `{item.get('dashboard_key')}`：{item.get('module')}")
        return "\n".join(lines)

    @staticmethod
    def build_navigation_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardNavigationService.build_navigation_center()
        rows = []
        for item in (
            (center.get("quick_links") or [])
            + (center.get("section_index") or [])
            + (center.get("runtime_index") or [])
            + (center.get("export_index") or [])
            + (center.get("ops_index") or [])
            + (center.get("architecture_index") or [])
            + (center.get("documentation_index") or [])
            + (center.get("missing_links") or [])
            + (center.get("broken_routes") or [])
        ):
            rows.append({
                "分类": item.get("type") or "",
                "标题": item.get("title") or "",
                "路径/锚点": item.get("path") or "",
                "状态": item.get("status") or "normal",
                "说明": item.get("summary") or "",
                "建议": item.get("suggestion") or "",
            })
        return rows
