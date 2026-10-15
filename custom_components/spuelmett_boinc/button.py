"""Button platform for Boinc Control integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoincCoordinator
from .entity import BoincEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Boinc buttons."""
    coordinator: BoincCoordinator = entry.runtime_data
    async_add_entities(
        [
            BoincHardStopButton(coordinator),
        ],
        False,
    )


class BoincHardStopButton(BoincEntity, ButtonEntity):
    """Button to immediately halt all computations (hard stop)."""

    _attr_translation_key = "hard_stop"
    _attr_icon = "mdi:stop-circle"

    def __init__(self, coordinator: BoincCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.get_entry_name()}_hard_stop"

    async def async_press(self) -> None:
        """Execute hard stop immediately."""
        await self.coordinator.boinc.stop_boinc()
        await self.coordinator.async_request_refresh()
