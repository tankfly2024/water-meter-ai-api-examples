"""Manual recognition and explicit confirmation buttons."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WaterMeterButton(entry, kind) for kind in ["read_meter", "confirm_reading", "discard_reading"]])


class WaterMeterButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, kind):
        super().__init__(entry.runtime_data)
        self.kind = kind
        self._attr_unique_id = entry.entry_id + "_" + kind
        self._attr_translation_key = kind
        self._attr_icon = {"read_meter": "mdi:camera", "confirm_reading": "mdi:check", "discard_reading": "mdi:close"}[kind]
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": entry.title, "manufacturer": "WaterMeter AI"}

    @property
    def available(self):
        state = self.coordinator.data or {}
        busy = self.coordinator.action_lock.locked()
        if self.kind != "read_meter":
            return not busy and state.get("candidate") is not None
        return not busy and not state.get("submission_unknown") and state.get("candidate") is None

    async def async_press(self):
        if self.kind == "confirm_reading":
            await self.coordinator.confirm()
        elif self.kind == "discard_reading":
            await self.coordinator.discard()
        else:
            await self.coordinator.read_meter()
