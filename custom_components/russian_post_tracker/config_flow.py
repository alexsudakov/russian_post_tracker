from __future__ import annotations

import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, CONF_LOGIN, CONF_PASSWORD, CONF_TRACKS

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class RussianPostConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Флоу настройки Russian Post Tracker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Первый шаг — ввод логина и пароля."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_LOGIN],
                data={
                    CONF_LOGIN: user_input[CONF_LOGIN],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
                options={CONF_TRACKS: []},  # начальный пустой список треков
            )

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Определяем класс для flow редактирования опций (треки)."""
        return RussianPostOptionsFlowHandler(config_entry)


class RussianPostOptionsFlowHandler(config_entries.OptionsFlow):
    """Обработка изменения списка треков после установки."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        # Инициализируем список треков из options (или пустой)
        self.tracks: list[dict[str, str]] = list(
            config_entry.options.get(CONF_TRACKS, [])
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Показ текущих треков и меню действий: добавить/удалить/сохранить."""
        if user_input is not None:
            action = user_input["action"]

            if action == "add":
                return await self.async_step_add_track()

            if action.startswith("remove:"):
                idx = int(action.split(":", 1)[1])
                if 0 <= idx < len(self.tracks):
                    self.tracks.pop(idx)
                return await self.async_step_init()

            if action == "save":
                return self.async_create_entry(
                    title="", data={CONF_TRACKS: self.tracks}
                )

        # Формируем список вариантов: add, save и remove:<index>
        options: dict[str, str] = {
            "add": "➕ Добавить трек",
            "save": "💾 Сохранить",
        }
        for i, t in enumerate(self.tracks):
            options[f"remove:{i}"] = f"🗑 Удалить {t['name']}"

        schema = vol.Schema({vol.Required("action"): vol.In(options)})

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"count": len(self.tracks)},
        )

    async def async_step_add_track(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Шаг добавления нового трека."""
        if user_input is not None:
            self.tracks.append(
                {"barcode": user_input["barcode"], "name": user_input["name"]}
            )
            return await self.async_step_init()

        schema = vol.Schema({vol.Required("barcode"): str, vol.Required("name"): str})
        return self.async_show_form(step_id="add_track", data_schema=schema)
