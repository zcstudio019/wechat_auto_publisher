"""Read-only state bus for AI Runtime Dashboard kernel checks."""

from services.ai_runtime_layer_registry import get_runtime_center_manifests


class AIRuntimeStateBus:
    """Expose dashboard state through a stable read-only access surface."""

    def __init__(self, dashboard: dict | None = None, manifests: list[dict] | None = None):
        self._dashboard = dashboard if isinstance(dashboard, dict) else {}
        self._state_overrides = {}
        self._manifests = list(manifests or get_runtime_center_manifests())

    def get_state(self, key, default=None):
        if key in self._state_overrides:
            return self._state_overrides[key]
        return self._dashboard.get(key, default)

    def set_state(self, key, value):
        self._state_overrides[key] = value
        return value

    def has_state(self, key):
        return key in self._state_overrides or key in self._dashboard

    def get_layer_states(self, layer):
        states = {}
        for manifest in self._manifests:
            if manifest.get("layer") == layer:
                key = manifest.get("key")
                states[key] = self.get_state(key)
        return states

    def validate_required_keys(self):
        missing = []
        for manifest in self._manifests:
            key = manifest.get("key")
            if manifest.get("required") and not self.has_state(key):
                missing.append(key)
        return missing

    def snapshot(self):
        data = dict(self._dashboard)
        data.update(self._state_overrides)
        return data
