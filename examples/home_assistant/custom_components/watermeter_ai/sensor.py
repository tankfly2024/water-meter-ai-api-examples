"""Cumulative reading, pending value, status, and account quota sensors."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_UNIT, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WaterMeterSensor(entry, kind) for kind in ["total", "candidate", "status", "daily_remaining"]])


class WaterMeterSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, kind):
        super().__init__(entry.runtime_data)
        self.kind = kind
        self._attr_unique_id = entry.entry_id + "_" + kind
        self._attr_translation_key = kind
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": entry.title, "manufacturer": "WaterMeter AI"}
        if kind in {"total", "candidate"}:
            self._attr_native_unit_of_measurement = entry.data[CONF_UNIT]
        if kind == "total":
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_state_class = SensorStateClass.TOTAL
        elif kind == "status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["idle", "submitting", "submission_unknown", "queued", "running", "waiting_ai", "pending", "review_required", "accepted", "backwards", "unreadable", "error"]
        elif kind == "daily_remaining":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self.kind == "daily_remaining":
            quota = data.get("quota", {})
            return quota.get("remaining") if quota.get("account_type") == "free" else None
        value = data.get(self.kind)
        if self.kind in {"total", "candidate"}:
            return float(value) if value is not None else None
        return value

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self.kind == "total":
            return {"raw_reading": data.get("total"), "last_ai_reading": data.get("last_ai_reading"), "updated_at": data.get("updated_at")}
        if self.kind == "daily_remaining":
            quota = data.get("quota", {})
            return {key: quota.get(key) for key in ["account_type", "daily_limit", "used"]}
        if self.kind == "status":
            return {"pending_task": bool(data.get("task_id")), "quota_refresh_failed": data.get("quota_error", False)}
        return {}
