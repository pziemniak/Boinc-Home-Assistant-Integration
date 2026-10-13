from dataclasses import dataclass
import logging
from typing import Any

from .const import (
    AVERAGE_PROGRESS_RATE,
    BOINC_IP,
    DOMAIN,
    PROJECTS_DETAIL,
    RUNNING_TASK_COUNT,
    TOTAL_CREDIT,
    TOTAL_RAC,
    TOTAL_TASK_COUNT,
)
from .coordinator import BoincCoordinator
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RunningTaskEntityDescription(SensorEntityDescription):
    """Provide a description of the sensor."""

    # For backwards compat, allow description to override unique ID key to use
    unique_id: str | None = None


SENSORS: tuple[RunningTaskEntityDescription, ...] = (
    RunningTaskEntityDescription(
        key=RUNNING_TASK_COUNT,
        translation_key="task_running",
        unique_id="taskrunning",
        # No unit, it's extracted from response.
    ),
    RunningTaskEntityDescription(
        key=TOTAL_TASK_COUNT,
        translation_key="task_total",
        unique_id="tasktotal",
        # No unit, it's extracted from response.
    ),
    RunningTaskEntityDescription(
        key=AVERAGE_PROGRESS_RATE,
        translation_key="average_progress_rate",
        unique_id="average_progress_rate",
        # No unit, it's extracted from response.
    ),
    RunningTaskEntityDescription(
        key=TOTAL_RAC,
        name="Total RAC",
        translation_key="total_rac",
        unique_id="total_rac",
        native_unit_of_measurement="credits/day",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    RunningTaskEntityDescription(
        key=TOTAL_CREDIT,
        name="Total Credit",
        translation_key="total_credit",
        unique_id="total_credit",
        native_unit_of_measurement="credits",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor."""
    coordinator = entry.runtime_data

    async_add_entities(
        [BoincSensor(coordinator, description) for description in SENSORS], False
    )


class BoincSensor(CoordinatorEntity[BoincCoordinator], SensorEntity):
    """Implementation of the sensor."""

    entity_description: RunningTaskEntityDescription
    _attr_has_entity_name = True
    _attr_icon = "mdi:numeric"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = None
    _attr_device_class = None

    def __init__(
        self, coordinator: BoincCoordinator, description: RunningTaskEntityDescription
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.get_entry_name()}_{description.key}"
        if description.icon is not None:
            self._attr_icon = description.icon
        if description.state_class is not None:
            self._attr_state_class = description.state_class
        if description.native_unit_of_measurement is not None:
            self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        if description.suggested_display_precision is not None:
            self._attr_suggested_display_precision = description.suggested_display_precision

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this BOINC host."""
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
        return True

    @property
    def native_value(self) -> int | float | None:
        """Return sensor state."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.key in (TOTAL_RAC, TOTAL_CREDIT):
            projects = self.coordinator.data.get(PROJECTS_DETAIL, {}) if self.coordinator.data else {}
            return {
                "projects": projects,
                "project_count": len(projects),
            }
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
