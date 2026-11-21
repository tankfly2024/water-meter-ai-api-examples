"""WaterMeter AI custom integration. No recognition is triggered during setup."""
from homeassistant.const import Platform

from .runtime import WaterMeterRuntime

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass, entry):
    runtime = WaterMeterRuntime(hass, entry)
    await runtime.initialize()
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    await entry.runtime_data.stop()
    if hasattr(hass.config_entries, "async_unload_platforms_or_raise"):
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
        return True
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
