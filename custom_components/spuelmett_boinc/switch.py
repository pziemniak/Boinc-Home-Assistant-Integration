"""Switch platform for Boinc Control integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BOINC_IP,
    BOINC_MODE_AUTO,
    BOINC_MODE_NEVER,
    DOMAIN,
    GPU_MODE,
    TASK_MODE,
)
from .coordinator import BoincCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Boinc switches."""
    coordinator: BoincCoordinator = entry.runtime_data
    async_add_entities(
        [
            BoincComputationsSwitch(coordinator),
            BoincGpuSwitch(coordinator),
        ],
        False,
    )


class BoincComputationsSwitch(CoordinatorEntity[BoincCoordinator], SwitchEntity):
    """Switch to turn BOINC computations on (start) or off (soft stop)."""

    _attr_has_entity_name = True
    _attr_translation_key = "computations"
    _attr_icon = "mdi:cpu-64-bit"

    def __init__(self, coordinator: BoincCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.get_entry_name()}_computations"

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return True if BOINC is active and not soft-stopping."""
        if not self.coordinator.data:
            return False
        task_mode = self.coordinator.data.get(TASK_MODE, BOINC_MODE_AUTO)
        return task_mode != BOINC_MODE_NEVER and not self.coordinator.boinc.soft_stop_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return switch state attributes."""
        return {
            "soft_stop_pending": self.coordinator.boinc.soft_stop_state,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on computations."""
        await self.coordinator.boinc.start_boinc()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Soft-stop computations."""
        await self.coordinator.boinc.soft_stop_boinc()
        await self.coordinator.async_request_refresh()


class BoincGpuSwitch(CoordinatorEntity[BoincCoordinator], SwitchEntity):
    """Switch to turn BOINC GPU usage on or off."""

    _attr_has_entity_name = True
    _attr_translation_key = "gpu"
    _attr_icon = "mdi:expansion-card"

    def __init__(self, coordinator: BoincCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.get_entry_name()}_gpu"

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return True if GPU mode is active."""
        if not self.coordinator.data:
            return False
        gpu_mode = self.coordinator.data.get(GPU_MODE, BOINC_MODE_AUTO)
        return gpu_mode != BOINC_MODE_NEVER

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start GPU computations."""
        await self.coordinator.boinc.start_gpu()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop GPU computations."""
        await self.coordinator.boinc.stop_gpu()
        await self.coordinator.async_request_refresh()
