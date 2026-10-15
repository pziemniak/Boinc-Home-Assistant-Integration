"""The Boinc Control integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from .coordinator import BoincCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .boinc_control import BoincControl
from .const import BOINC_IP, CHECKPOINTING, DOMAIN, NAME, PASSWORD

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # create object to manage boinc
    name = entry.data.get(
        NAME, "default"
    )  # use default value, when upgrading from a version with no name in the input
    ip = entry.data[BOINC_IP]
    password = entry.data[PASSWORD]
    checkpoint_time = entry.options.get(CHECKPOINTING, 120)

    boinc = BoincControl(ip, password, checkpoint_time)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = boinc

    # register update options callback
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # setup coordinator
    coordinator = BoincCoordinator(hass, entry, boinc)
    entry.runtime_data = coordinator

    # Refresh data asynchronously in the background so HA startup is never blocked
    # even when BOINC hosts are offline or powered down.
    if hasattr(entry, "async_create_background_task"):
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), f"boinc_refresh_{entry.entry_id}"
        )
    else:
        hass.async_create_task(coordinator.async_refresh())

    # Register Services that can be called from automations or scripts
    async def start_boinc(call: ServiceCall) -> None:
        await boinc.start_boinc()
        await asyncio.sleep(2)
        await coordinator.async_request_refresh()

    async def stop_boinc(call: ServiceCall) -> None:
        await boinc.stop_boinc()
        await coordinator.async_request_refresh()

    async def soft_stop_boinc(call: ServiceCall) -> None:
        await boinc.soft_stop_boinc()
        await coordinator.async_request_refresh()

    async def soft_stop_check(call: ServiceCall) -> None:
        await boinc.update()
        await coordinator.async_request_refresh()

    async def start_gpu(call: ServiceCall) -> None:
        await boinc.start_gpu()
        await asyncio.sleep(1)
        await coordinator.async_request_refresh()

    async def stop_gpu(call: ServiceCall) -> None:
        await boinc.stop_gpu()
        await coordinator.async_request_refresh()

    service_name_suffix = str(name).lower().replace("-", "_")
    services = [
        ("start_boinc_" + service_name_suffix, start_boinc),
        ("stop_boinc_" + service_name_suffix, stop_boinc),
        ("soft_stop_boinc_" + service_name_suffix, soft_stop_boinc),
        ("soft_stop_check_" + service_name_suffix, soft_stop_check),
        ("start_gpu_" + service_name_suffix, start_gpu),
        ("stop_gpu_" + service_name_suffix, stop_gpu),
    ]
    for service_name, service_func in services:
        hass.services.async_register(DOMAIN, service_name, service_func)
        entry.async_on_unload(
            lambda s=service_name: hass.services.async_remove(DOMAIN, s)
        )

    # Add Event listener to trigger soft stop every minute
    async def update_check(now):
        if boinc.soft_stop_state:
            try:
                await boinc.update()
                await coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.warning(
                    "Error during soft-stop background check for BOINC host %s: %s",
                    boinc.host,
                    err,
                )
                await boinc.disconnect()

    entry.async_on_unload(
        async_track_time_interval(
            hass, update_check, timedelta(minutes=1), cancel_on_shutdown=True
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        boinc = hass.data[DOMAIN].pop(entry.entry_id, None)
        if boinc:
            await boinc.disconnect()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    checkpoint_time = entry.options.get(CHECKPOINTING, 120)
    hass.data[DOMAIN][entry.entry_id].set_checkpoint_time(checkpoint_time)
