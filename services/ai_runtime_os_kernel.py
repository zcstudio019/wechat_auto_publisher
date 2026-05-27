"""AI Runtime OS kernel view builder for Dashboard integrity checks."""

from services.ai_runtime_layer_registry import get_runtime_center_manifests, get_runtime_layers
from services.ai_runtime_state_bus import AIRuntimeStateBus


class AIRuntimeOSKernel:
    """Build a read-only kernel view over existing Dashboard centers."""

    @classmethod
    def build_kernel_view(cls, dashboard: dict | None) -> dict:
        manifests = get_runtime_center_manifests()
        bus = AIRuntimeStateBus(dashboard or {}, manifests)
        missing_required = bus.validate_required_keys()
        route_coverage = cls._build_route_coverage(manifests)
        export_coverage = cls._build_export_coverage(manifests)
        title_coverage = cls._build_title_coverage(manifests)
        layers = cls._build_layers(manifests, bus)
        high_coupling_warnings = cls._build_high_coupling_warnings(layers, dashboard or {}, manifests)

        missing_core_titles = [item["key"] for item in title_coverage if item["status"] == "missing"]
        missing_core_routes = [item["key"] for item in route_coverage if item["required"] and item["status"] == "missing"]
        missing_exports = [item["key"] for item in export_coverage if item["required"] and item["status"] == "missing"]

        if missing_required or missing_core_titles or missing_core_routes:
            status = "critical"
        elif missing_exports or high_coupling_warnings:
            status = "warning"
        else:
            status = "healthy"

        return {
            "kernel_status": status,
            "summary": cls._summary(status, len(layers), missing_required, missing_exports),
            "layers": layers,
            "missing_required_keys": missing_required,
            "route_coverage": route_coverage,
            "export_coverage": export_coverage,
            "template_title_coverage": title_coverage,
            "high_coupling_warnings": high_coupling_warnings,
            "recommended_actions": cls._recommended_actions(status, missing_required, missing_exports, high_coupling_warnings),
        }

    @staticmethod
    def build_kernel_text(kernel_view: dict | None = None) -> str:
        kernel_view = kernel_view or {}
        lines = [
            "【AI Runtime 操作系统内核】",
            f"状态：{kernel_view.get('kernel_status') or 'unknown'}",
            f"摘要：{kernel_view.get('summary') or ''}",
            f"层级数量：{len(kernel_view.get('layers') or [])}",
            "",
            "缺失 required keys：",
        ]
        missing = kernel_view.get("missing_required_keys") or []
        lines.extend([f"- {key}" for key in missing] or ["- 无"])
        lines.append("")
        lines.append("建议：")
        lines.extend([f"- {item}" for item in (kernel_view.get("recommended_actions") or [])] or ["- 保持只读内核校验。"])
        return "\n".join(lines)

    @staticmethod
    def build_kernel_markdown(kernel_view: dict | None = None) -> str:
        kernel_view = kernel_view or {}
        lines = [
            "# AI Runtime 操作系统内核",
            "",
            f"- 状态：{kernel_view.get('kernel_status') or 'unknown'}",
            f"- 摘要：{kernel_view.get('summary') or ''}",
            f"- 层级数量：{len(kernel_view.get('layers') or [])}",
            "",
            "## 层级",
        ]
        for layer in kernel_view.get("layers") or []:
            lines.append(f"- {layer.get('layer')}：{layer.get('mounted_count')}/{layer.get('center_count')}")
        lines.extend(["", "## 建议"])
        lines.extend([f"- {item}" for item in (kernel_view.get("recommended_actions") or [])] or ["- 保持只读内核校验。"])
        return "\n".join(lines)

    @staticmethod
    def build_kernel_rows(kernel_view: dict | None = None) -> list[dict]:
        rows = []
        for layer in (kernel_view or {}).get("layers") or []:
            for center in layer.get("centers") or []:
                rows.append({
                    "层级": layer.get("layer") or "",
                    "Key": center.get("key") or "",
                    "标题": center.get("title") or "",
                    "Route": center.get("route") or "",
                    "Export": center.get("export_route") or "",
                    "状态": center.get("status") or "",
                    "建议": center.get("suggestion") or "",
                })
        return rows

    @staticmethod
    def _build_layers(manifests: list[dict], bus: AIRuntimeStateBus) -> list[dict]:
        layers = []
        for layer in get_runtime_layers():
            layer_manifests = [item for item in manifests if item.get("layer") == layer]
            centers = []
            for manifest in layer_manifests:
                key = manifest.get("key")
                mounted = bus.has_state(key)
                centers.append({
                    **manifest,
                    "status": "mounted" if mounted else "missing",
                    "suggestion": "保持只读接入。" if mounted else "补齐 Dashboard key 或调整 manifest required 标记。",
                })
            layers.append({
                "layer": layer,
                "center_count": len(centers),
                "mounted_count": len([item for item in centers if item["status"] == "mounted"]),
                "missing_count": len([item for item in centers if item["status"] == "missing"]),
                "centers": centers,
            })
        return layers

    @staticmethod
    def _build_route_coverage(manifests: list[dict]) -> list[dict]:
        return [
            {
                "key": item.get("key"),
                "title": item.get("title"),
                "route": item.get("route") or "",
                "required": bool(item.get("required")),
                "status": "ok" if item.get("route") else "missing",
            }
            for item in manifests
        ]

    @staticmethod
    def _build_export_coverage(manifests: list[dict]) -> list[dict]:
        return [
            {
                "key": item.get("key"),
                "title": item.get("title"),
                "export_route": item.get("export_route") or "",
                "required": bool(item.get("required")),
                "status": "ok" if item.get("export_route") else "missing",
            }
            for item in manifests
        ]

    @staticmethod
    def _build_title_coverage(manifests: list[dict]) -> list[dict]:
        return [
            {
                "key": item.get("key"),
                "title": item.get("title") or "",
                "status": "ok" if item.get("title") else "missing",
            }
            for item in manifests
        ]

    @staticmethod
    def _build_high_coupling_warnings(layers: list[dict], dashboard: dict, manifests: list[dict]) -> list[str]:
        warnings = []
        for layer in layers:
            if layer.get("center_count", 0) >= 12:
                warnings.append(f"{layer.get('layer')} 聚合 Center 较多，建议继续通过 manifest 分层观察。")

        manifest_keys = {item.get("key") for item in manifests}
        unknown_center_keys = [
            key for key in dashboard.keys()
            if key.startswith("ai_") and key not in manifest_keys and (key.endswith("_center") or "dashboard" in key)
        ]
        if unknown_center_keys:
            warnings.append(f"发现 {len(unknown_center_keys)} 个未进入 Runtime Layer Registry 的 Dashboard key。")
        return warnings

    @staticmethod
    def _summary(status: str, layer_count: int, missing_required: list[str], missing_exports: list[str]) -> str:
        if status == "critical":
            return f"Runtime 内核校验发现关键缺口：required={len(missing_required)}。"
        if status == "warning":
            return f"Runtime 内核 required key 完整，但存在导出或耦合提示：export={len(missing_exports)}。"
        return f"Runtime 内核 required key 完整，已收敛为 {layer_count} 个运行层。"

    @staticmethod
    def _recommended_actions(status: str, missing_required: list[str], missing_exports: list[str], warnings: list[str]) -> list[str]:
        actions = []
        if missing_required:
            actions.append("补齐缺失 required Dashboard key，或在 Registry 中明确降级为非必需。")
        if missing_exports:
            actions.append("为缺失 export_route 的 Center 补齐导出入口，或在 Registry 中记录只读说明。")
        if warnings:
            actions.append("继续用 Runtime Layer Registry 收敛高耦合 Center，避免新增功能中心。")
        if not actions:
            actions.append("保持只读内核校验，不触发审核、发布、Agent 或 worker。")
        if status == "critical":
            actions.append("优先处理 critical 后再扩大 Dashboard 接入范围。")
        return actions
