"""UI configuration and reauthentication; only a quota GET validates the key."""
try:
    import probatio as schema
except ModuleNotFoundError:
    import voluptuous as schema

from homeassistant import config_entries
from homeassistant.helpers import selector

from .api import ApiError, WaterMeterApi
from .const import CONF_CAMERA, CONF_MAX_INCREASE, CONF_UNIT, DOMAIN


def key_field():
    secret = getattr(schema, "Secret", lambda name: name)
    return schema.Required(secret("api_key"))


class WaterMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def validate_key(self, key):
        api = WaterMeterApi(key.strip(), executor=self.hass.async_add_executor_job)
        await api.quota()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self.validate_key(user_input["api_key"])
            except ApiError as error:
                errors["base"] = "invalid_auth" if error.status == 401 else "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(user_input[CONF_CAMERA])
                self._abort_if_unique_id_configured()
                user_input["api_key"] = user_input["api_key"].strip()
                return self.async_create_entry(title="WaterMeter AI · " + user_input[CONF_CAMERA], data=user_input)
        return self.async_show_form(step_id="user", errors=errors, data_schema=schema.Schema({
            key_field(): selector.selector({"text": {"type": "password"}}),
            schema.Required(CONF_CAMERA): selector.selector({"entity": {"domain": "camera"}}),
            schema.Required(CONF_UNIT, default="m³"): selector.selector({"select": {"options": ["m³", "L"]}}),
            schema.Required(CONF_MAX_INCREASE, default=10): selector.selector({"number": {"min": 0.001, "max": 1000000, "step": 0.001, "mode": "box"}}),
        }))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None:
            try:
                await self.validate_key(user_input["api_key"])
            except (ApiError, ValueError):
                errors["base"] = "invalid_auth"
            else:
                self.hass.config_entries.async_update_entry(entry, data={**entry.data, "api_key": user_input["api_key"].strip()})
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(step_id="reauth_confirm", errors=errors, data_schema=schema.Schema({
            key_field(): selector.selector({"text": {"type": "password"}}),
        }))
