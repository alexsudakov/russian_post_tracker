from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_TRACKS, DEFAULT_SCAN_INTERVAL, EVENT_STATUS_CHANGED
from .russian_post_client import RussianPostTracker

_LOGGER = logging.getLogger(__name__)


class RPTrackerCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Координатор, собирающий данные по всем трекам раз в указанный интервал."""

    def __init__(
        self,
        hass: HomeAssistant,
        tracker: RussianPostTracker,
        tracks: list[dict],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.tracker = tracker
        self.tracks = tracks

    async def _async_update_data(self) -> dict[str, dict]:
        """Запрашиваем информацию по всем трекам за один проход."""
        result: dict[str, dict] = {}
        for track in self.tracks:
            info = await self.hass.async_add_executor_job(
                self.tracker.get_last_operation, track["barcode"]
            )
            if info:
                info["track_name"] = track["name"]
                result[track["barcode"]] = info
        return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт сенсоры для каждого трека, используя данные координатора."""
    coordinator: RPTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RPTrackerSensor(coordinator, track["barcode"])
        for track in coordinator.tracks
    ]
    async_add_entities(entities)


class RPTrackerSensor(CoordinatorEntity[RPTrackerCoordinator]):
    """Сенсор, отображающий статус одной посылки."""

    def __init__(self, coordinator: RPTrackerCoordinator, barcode: str) -> None:
        super().__init__(coordinator)
        self.barcode = barcode
        self._attr_name = coordinator.data.get(barcode, {}).get("track_name", barcode)
        self._last_status: str | None = None

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.barcode}"

    @property
    def state(self) -> str | None:
        data = self.coordinator.data.get(self.barcode)
        return data.get("status") if data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data.get(self.barcode, {})
        return {
            "Название": data.get("track_name"),
            "Последний статус": data.get("status"),
            "Тип операции": data.get("operation_type"),
            "Адрес места операции": data.get("location"),
            "Страна отправителя": data.get("country_from"),
            "Дата последней операции": data.get("operation_date"),
            "История обработки": data.get("history"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """
        Обрабатывает обновление от координатора.
        Если трек был удалён из настроек — удаляем сенсор.
        Иначе — генерим событие при изменении статуса.
        """
        # если трек удалён из конфига — удаляем эту сущность
        if self.barcode not in self.coordinator.data:
            _LOGGER.debug("Трек %s удалён из настроек — удаляем сенсор", self.barcode)
            self.async_remove()
            return

        new_status = self.coordinator.data[self.barcode].get("status")
        if new_status != self._last_status:
            self._last_status = new_status
            _LOGGER.debug(
                "Статус посылки %s изменился: %s → %s",
                self.barcode,
                self._last_status,
                new_status,
            )
            self.hass.bus.async_fire(
                EVENT_STATUS_CHANGED,
                {
                    "track_code": self.barcode,
                    "name": self._attr_name,
                    "new_status": new_status,
                    "location": self.coordinator.data[self.barcode].get("location"),
                },
            )
        super()._handle_coordinator_update()
