"""Read-only AI Dashboard UX declutter and entry reorder center."""

from __future__ import annotations


class AIDashboardUXDeclutterService:
    """Build UX declutter suggestions without changing dashboard layout."""

    @classmethod
    def build_ux_declutter_entry_reorder_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        current_entry_map = cls._build_current_entry_map(dashboard)
        recommended_entry_order = cls._build_recommended_entry_order()
        high_frequency_entries = [
            item for item in recommended_entry_order if item.get("priority") in {"top", "high"}
        ]
        low_frequency_entries = [
            item for item in current_entry_map if item.get("priority") in {"low", "deep_dive"}
        ]
        hidden_or_collapsed_candidates = cls._build_hidden_candidates(current_entry_map)
        top_priority_cards = cls._filter_cards(recommended_entry_order, {"top", "high"})
        secondary_cards = cls._filter_cards(recommended_entry_order, {"medium"})
        deep_dive_cards = cls._filter_cards(current_entry_map, {"deep_dive"})
        duplicate_entries = cls._build_duplicate_entries(current_entry_map)
        overloaded_sections = cls._build_overloaded_sections(current_entry_map)
        navigation_friction_points = cls._build_navigation_friction_points(dashboard, current_entry_map)
        ux_status = cls._resolve_status(duplicate_entries, overloaded_sections, navigation_friction_points)

        return {
            "ux_status": ux_status,
            "summary": cls._build_summary(ux_status, current_entry_map, overloaded_sections, duplicate_entries),
            "current_entry_map": current_entry_map,
            "recommended_entry_order": recommended_entry_order,
            "high_frequency_entries": high_frequency_entries,
            "low_frequency_entries": low_frequency_entries,
            "hidden_or_collapsed_candidates": hidden_or_collapsed_candidates,
            "top_priority_cards": top_priority_cards,
            "secondary_cards": secondary_cards,
            "deep_dive_cards": deep_dive_cards,
            "duplicate_entries": duplicate_entries,
            "overloaded_sections": overloaded_sections,
            "navigation_friction_points": navigation_friction_points,
            "recommended_actions": cls._build_recommended_actions(ux_status),
        }

    @staticmethod
    def _entry(title: str, current: str, recommended: str, priority: str, status: str, suggestion: str) -> dict:
        return {
            "title": title,
            "current_position": current,
            "recommended_position": recommended,
            "priority": priority,
            "status": status,
            "suggestion": suggestion,
        }

    @classmethod
    def _build_current_entry_map(cls, dashboard: dict) -> list[dict]:
        entries = [
            cls._entry("AI Dashboard 导出中心", "总控区", "总控区第一层", "top", "normal", "保留为顶部常用入口。"),
            cls._entry("AI Dashboard 导出运营中心", "总控区", "导出中心下方", "high", "normal", "用于复核导出状态。"),
            cls._entry("AI Dashboard 运维健康中心", "总控区", "运维相关入口前置", "high", "normal", "用于快速识别 Dashboard 健康状态。"),
            cls._entry("AI Dashboard 运维维护计划中心", "总控区", "运维健康中心下方", "medium", "normal", "作为维护计划入口。"),
            cls._entry("AI Dashboard 系统架构地图中心", "总控区", "维护计划中心下方", "medium", "normal", "作为架构理解入口。"),
            cls._entry("AI Dashboard 文档中心", "总控区", "架构地图中心下方", "medium", "normal", "作为说明文档入口。"),
            cls._entry("AI Dashboard 导航与索引中心", "总控区", "文档中心下方", "high", "normal", "作为全局索引入口。"),
            cls._entry("AI Dashboard 管理首页中心", "总控区", "导航索引后", "top", "normal", "作为管理总览入口。"),
            cls._entry("AI Dashboard 工作台中心", "总控区", "管理首页后", "top", "normal", "作为角色化工作台入口。"),
            cls._entry("AI Dashboard 体验减负与入口重排", "总控区", "工作台后", "high", "normal", "提供只读入口优化建议。"),
            cls._entry("AI Runtime 任务指挥中心", "总控区", "体验减负中心后", "top", "normal", "作为 Runtime 今日任务入口。"),
            cls._entry("AI 运行时可观测中心", "总控区", "任务指挥后", "high", "normal", "保留核心观测入口。"),
            cls._entry("AI Command Center", "总控区", "Runtime 基础中心后", "medium", "normal", "保留指挥视图。"),
            cls._entry("AI AutoOps Control Tower", "总控区", "Command Center 后", "medium", "normal", "保留自动运营只读总览。"),
            cls._entry("AI 运行时模块显示自检", "总控区底部", "总控区底部", "deep_dive", "normal", "保留深度诊断位置。"),
        ]
        navigation = dashboard.get("ai_dashboard_navigation_index_center") or {}
        for item in navigation.get("quick_links") or []:
            title = item.get("title") or item.get("label") or "导航入口"
            entries.append(
                cls._entry(
                    title,
                    "导航中心",
                    "按导航索引保留",
                    "medium",
                    item.get("status") or "normal",
                    item.get("summary") or "导航入口。",
                )
            )
        return entries[:40]

    @classmethod
    def _build_recommended_entry_order(cls) -> list[dict]:
        titles = [
            ("AI Dashboard 导出中心", "1", "top", "保留在最前。"),
            ("AI Dashboard 导出运营中心", "2", "high", "导出状态紧跟导出入口。"),
            ("AI Dashboard 运维健康中心", "3", "high", "运维健康提前。"),
            ("AI Dashboard 运维维护计划中心", "4", "medium", "承接运维健康。"),
            ("AI Dashboard 系统架构地图中心", "5", "medium", "放在维护计划后。"),
            ("AI Dashboard 文档中心", "6", "medium", "放在架构地图后。"),
            ("AI Dashboard 导航与索引中心", "7", "high", "作为全局索引入口。"),
            ("AI Dashboard 管理首页中心", "8", "top", "管理总览放在索引之后。"),
            ("AI Dashboard 工作台中心", "9", "top", "作为日常操作入口。"),
            ("AI Dashboard 体验减负与入口重排", "10", "high", "提供只读入口优化建议。"),
            ("AI Runtime 任务指挥中心", "11", "top", "承接工作台任务。"),
            ("AI 运行时可观测中心", "12", "high", "保留核心运行状态。"),
        ]
        return [
            cls._entry(title, "总控区", position, priority, "normal", suggestion)
            for title, position, priority, suggestion in titles
        ]

    @staticmethod
    def _filter_cards(entries: list[dict], priorities: set[str]) -> list[dict]:
        return [item for item in entries if item.get("priority") in priorities]

    @staticmethod
    def _build_hidden_candidates(entries: list[dict]) -> list[dict]:
        return [
            {**item, "status": "attention", "suggestion": "建议默认折叠，仅保留标题与详情入口。"}
            for item in entries
            if item.get("priority") in {"low", "deep_dive"}
        ][:10]

    @staticmethod
    def _build_duplicate_entries(entries: list[dict]) -> list[dict]:
        seen = set()
        duplicates = []
        for item in entries:
            title = item.get("title")
            if title in seen:
                duplicates.append(
                    {**item, "status": "duplicated", "suggestion": "建议保留一个主入口，其他入口作为详情链接。"}
                )
            seen.add(title)
        return duplicates

    @staticmethod
    def _build_overloaded_sections(entries: list[dict]) -> list[dict]:
        total = len([item for item in entries if item.get("current_position") == "总控区"])
        if total <= 12:
            return []
        return [
            {
                "title": "① 总控区：今日指挥与决策",
                "current_position": "总控区",
                "recommended_position": "保留高频入口，低频入口默认折叠",
                "priority": "high",
                "status": "overloaded",
                "suggestion": f"总控区当前入口约 {total} 个，建议使用分层与折叠降低认知负担。",
            }
        ]

    @staticmethod
    def _build_navigation_friction_points(dashboard: dict, entries: list[dict]) -> list[dict]:
        points = []
        navigation = dashboard.get("ai_dashboard_navigation_index_center") or {}
        for item in navigation.get("missing_links") or []:
            points.append(
                {
                    "title": item.get("title") or item.get("path") or "缺失入口",
                    "current_position": "导航中心",
                    "recommended_position": "补充为详情入口",
                    "priority": "medium",
                    "status": "missing",
                    "suggestion": item.get("suggestion") or "只读标记缺失入口，不自动修复。",
                }
            )
        if len(entries) >= 25:
            points.append(
                {
                    "title": "入口数量较多",
                    "current_position": "总控区",
                    "recommended_position": "分层展示",
                    "priority": "medium",
                    "status": "attention",
                    "suggestion": "优先展示高频入口，深度分析入口放入详情页。",
                }
            )
        return points[:10]

    @staticmethod
    def _resolve_status(duplicates: list[dict], overloaded: list[dict], friction: list[dict]) -> str:
        if overloaded:
            return "overloaded"
        if duplicates:
            return "duplicated"
        if friction:
            return "attention"
        return "normal"

    @staticmethod
    def _build_summary(status: str, entries: list[dict], overloaded: list[dict], duplicates: list[dict]) -> str:
        if status == "overloaded":
            return f"当前 Dashboard 入口较多，已识别 {len(overloaded)} 个过载分区，建议按高频、次级、深度分析分层。"
        if status == "duplicated":
            return f"当前 Dashboard 存在 {len(duplicates)} 个重复入口，建议保留主入口并把重复入口转为详情链接。"
        return f"当前 Dashboard 入口结构可用，已生成 {len(entries)} 个入口的只读重排建议。"

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        actions = [
            "保留导出、管理首页、工作台、任务指挥作为高频入口。",
            "把深度分析模块默认折叠。",
            "把重复入口收敛为一个主入口和详情链接。",
            "把 Runtime 诊断类模块放在任务指挥之后。",
            "保持本中心只读，不自动修改页面布局。",
        ]
        if status in {"overloaded", "duplicated", "attention"}:
            actions.insert(0, "优先按推荐入口顺序复核总控区。")
        return actions[:8]

    @staticmethod
    def build_ux_declutter_text(center: dict | None = None) -> str:
        center = center or AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center({})
        lines = [
            "【AI Dashboard 体验减负与入口重排】",
            "",
            f"体验状态：{center.get('ux_status') or '-'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "推荐入口顺序：",
        ]
        for item in center.get("recommended_entry_order") or []:
            lines.append(f"- {item.get('title')}：{item.get('recommended_position')} / {item.get('suggestion')}")
        return "\n".join(lines)

    @staticmethod
    def build_ux_declutter_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardUXDeclutterService.build_ux_declutter_entry_reorder_center({})
        rows = []
        for category, key in [
            ("当前入口地图", "current_entry_map"),
            ("推荐入口顺序", "recommended_entry_order"),
            ("高频入口", "high_frequency_entries"),
            ("低频入口", "low_frequency_entries"),
            ("建议折叠", "hidden_or_collapsed_candidates"),
            ("第一优先级卡片", "top_priority_cards"),
            ("第二优先级卡片", "secondary_cards"),
            ("深度分析卡片", "deep_dive_cards"),
            ("重复入口", "duplicate_entries"),
            ("过载分区", "overloaded_sections"),
            ("导航摩擦点", "navigation_friction_points"),
        ]:
            for item in center.get(key) or []:
                rows.append(
                    {
                        "分类": category,
                        "标题": item.get("title") or "",
                        "当前位置": item.get("current_position") or "",
                        "推荐位置": item.get("recommended_position") or "",
                        "优先级": item.get("priority") or "",
                        "状态": item.get("status") or "",
                        "建议": item.get("suggestion") or "",
                    }
                )
        if not rows:
            rows.append(
                {
                    "分类": "体验减负",
                    "标题": "当前暂无 Dashboard 体验减负与入口重排数据。",
                    "当前位置": "",
                    "推荐位置": "",
                    "优先级": "",
                    "状态": "idle",
                    "建议": "",
                }
            )
        return rows
