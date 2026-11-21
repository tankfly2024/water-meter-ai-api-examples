"""Home Assistant adapter for persistent, explicitly requested reads."""
import asyncio
import logging

from homeassistant.components.camera import async_get_image
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ApiError, WaterMeterApi
from .const import CONF_CAMERA, CONF_MAX_INCREASE, DOMAIN
from .engine import ReadEngine, ReadError

_LOGGER = logging.getLogger(__name__)


class WaterMeterRuntime(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.storage = Store(hass, 1, DOMAIN + "." + entry.entry_id)
        self.api = WaterMeterApi(entry.data["api_key"], executor=hass.async_add_executor_job)
        self.engine = None
        self.active_task = None
        self.action_lock = asyncio.Lock()

    async def initialize(self):
        state = await self.storage.async_load()
        self.engine = ReadEngine(self.api, self.save, state=state,
                                 max_increase=self.entry.data[CONF_MAX_INCREASE])
        await self.engine.persist()

    async def save(self, state):
        await self.storage.async_save(state)
        self.async_set_updated_data(dict(state))

    async def read_meter(self):
        if self.action_lock.locked():
            raise HomeAssistantError("Recognition is already running")
        async with self.action_lock:
            self.active_task = asyncio.current_task()
            try:
                state = self.engine.state
                if state["submission_unknown"] or state["candidate"] is not None:
                    await self.engine.read()
                    return
                image = None
                if not state["task_id"]:
                    snapshot = await async_get_image(self.hass, self.entry.data[CONF_CAMERA])
                    image = snapshot.content
                await self.engine.read(image)
            except ApiError as error:
                if error.status == 401:
                    self.entry.async_start_reauth(self.hass)
                raise HomeAssistantError(str(error)) from None
            except (ReadError, ValueError) as error:
                raise HomeAssistantError(str(error)) from None
            finally:
                self.active_task = None

    async def confirm(self):
        try:
            await self.engine.confirm()
        except ReadError as error:
            raise HomeAssistantError(str(error)) from None

    async def discard(self):
        try:
            await self.engine.discard()
        except ReadError as error:
            raise HomeAssistantError(str(error)) from None

    async def stop(self):
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()
            try:
                await self.active_task
            except asyncio.CancelledError:
                pass
