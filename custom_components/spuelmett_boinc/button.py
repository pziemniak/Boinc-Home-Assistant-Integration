"""Button platform for Boinc Control integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BOINC_IP, DOMAIN
from .coordinator import BoincCoordinator


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


class BoincHardStopButton(CoordinatorEntity[BoincCoordinator], ButtonEntity):
    """Button to immediately halt all computations (hard stop)."""

    _attr_has_entity_name = True
    _attr_translation_key = "hard_stop"
    _attr_icon = "mdi:stop-circle"

    def __init__(self, coordinator: BoincCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.get_entry_name()}_hard_stop"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        entry = self.coordinator.config_entry
        name = self.coordinator.get_entry_name()
        ip = entry.data.get(BOINC_IP) if entry else None
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"BOINC {name}",
            manufacturer="BOINC",
            model="BOINC Client Host",
            sw_version=getattr(self.coordinator.boinc, "version", None),
            configuration_url=f"http://{ip}:31416" if ip else None,
        )

    async def async_press(self) -> None:
        """Execute hard stop immediately."""
        await self.coordinator.boinc.stop_boinc()
        await self.coordinator.async_request_refresh()
