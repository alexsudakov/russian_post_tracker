from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_LOGIN, CONF_PASSWORD, CONF_TRACKS
from .russian_post_client import RussianPostTracker
from .sensor import RPTrackerCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции при добавлении через UI."""
    login = entry.data[CONF_LOGIN]
    password = entry.data[CONF_PASSWORD]
    tracks = entry.options.get(CONF_TRACKS, [])

    tracker = RussianPostTracker(login, password)
    coordinator = RPTrackerCoordinator(hass, tracker, tracks)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.add_update_listener(_async_update_options)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Удаление интеграции: выгрузка платформы sensor, удаление сущностей и очистка данных."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        registry = er.async_get(hass)
        # Удаляем все сущности, привязанные к этому config_entry
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            registry.async_remove(entity.entity_id)
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """При изменении опций (списка треков) — перезагружаем запись конфигурации."""
    await hass.config_entries.async_reload(entry.entry_id)
