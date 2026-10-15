"""Base entity for the Boinc Control integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BoincCoordinator


class BoincEntity(CoordinatorEntity[BoincCoordinator]):
    """Defines a base BOINC entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this BOINC host."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
