from datetime import timedelta
import logging

from .const import (
    AVERAGE_PROGRESS_RATE,
    BOINC_MODE_AUTO,
    GPU_MODE,
    NAME,
    PROJECTS_DETAIL,
    RUNNING_TASK_COUNT,
    TASK_MODE,
    TOTAL_CREDIT,
    TOTAL_RAC,
    TOTAL_TASK_COUNT,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class BoincCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
        boinc,
    ):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Boinc sensor",
            config_entry=config_entry,
            update_interval=timedelta(seconds=60),
            always_update=True,
        )
        self._device: SensorDeviceClass | None = None
        self.boinc = boinc

    @property
    def entry_id(self) -> str:
        return self.config_entry.entry_id

    def get_entry_name(self) -> str:
        return self.config_entry.data.get(NAME, "default")

    async def _async_update_data(self):
        results = await self.boinc.get_results()
        projects = await self.boinc.get_projects()
        cc_status = await self.boinc.get_cc_status()

        data = {}
        data[RUNNING_TASK_COUNT] = self.boinc.get_running_task_count(results)
        data[TOTAL_TASK_COUNT] = self.boinc.get_total_task_count(results)
        data[AVERAGE_PROGRESS_RATE] = self.boinc.average_progress_rate(results)
        data[TOTAL_RAC] = self.boinc.get_total_rac(projects)
        data[TOTAL_CREDIT] = self.boinc.get_total_credit(projects)
        data[PROJECTS_DETAIL] = self.boinc.get_projects_detail(projects)

        data[TASK_MODE] = cc_status.get(TASK_MODE, BOINC_MODE_AUTO)
        data[GPU_MODE] = cc_status.get(GPU_MODE, BOINC_MODE_AUTO)

        return data
