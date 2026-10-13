"""Boinc Control integration logic."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from .pyboinc.pyboinc import init_rpc_client
from .pyboinc.pyboinc.rpc_client import Mode

_LOGGER = logging.getLogger(__name__)


class BoincControl:
    def __init__(self, host: str, password: str, checkpoint_time: int) -> None:
        self.current_soft_stop_state = False
        self.soft_stop_start_time: datetime | None = None
        self.host = host
        self.password = password
        self.checkpoint_time = checkpoint_time
        self.rpc_client = None
        self.version = None

    async def connect(self):
        self.rpc_client = await init_rpc_client(self.host, self.password)
        await self.rpc_client.authorize()
        if self.version is None:
            self.version = await self.get_version()

    def set_checkpoint_time(self, checkpoint_time):
        self.checkpoint_time = checkpoint_time

    @property
    def soft_stop_state(self):
        return self.current_soft_stop_state

    async def start_boinc(self):
        await self.connect()
        self.current_soft_stop_state = False
        self.soft_stop_start_time = None
        await self.resume_all_task()
        await self.rpc_client.set_run_mode(Mode.AUTO, 0)

    async def stop_boinc(self):
        await self.connect()
        self.current_soft_stop_state = False
        self.soft_stop_start_time = None
        await self.rpc_client.set_run_mode(Mode.NEVER, 0)

    async def soft_stop_boinc(self):
        self.current_soft_stop_state = True
        self.soft_stop_start_time = datetime.now()
        await self.update()

    async def start_gpu(self):
        await self.connect()
        await self.rpc_client.set_gpu_mode(Mode.AUTO, 0)

    async def stop_gpu(self):
        await self.connect()
        await self.rpc_client.set_gpu_mode(Mode.NEVER, 0)

    async def update(self):
        await self.connect()

        # Do nothing if it should not stop
        if self.current_soft_stop_state is False:
            return

        # Check for max soft-stop timeout (10 minutes or 3 * checkpoint_time, whichever is larger)
        max_soft_stop_timeout = max(
            timedelta(seconds=self.checkpoint_time * 3), timedelta(minutes=10)
        )
        timed_out = (
            self.soft_stop_start_time is not None
            and (datetime.now() - self.soft_stop_start_time) > max_soft_stop_timeout
        )
        if timed_out:
            _LOGGER.info(
                "Soft stop timeout reached (%s); suspending remaining active tasks",
                max_soft_stop_timeout,
            )

        one_task_running = False  # Default

        results = await self.rpc_client.get_results()
        if results == "\n" or not isinstance(results, list):
            await self.rpc_client.set_run_mode(Mode.NEVER, 0)
            self.current_soft_stop_state = False
            self.soft_stop_start_time = None
            return

        for result in results:
            if "active_task" in result:
                active_task = result["active_task"]
                checkpoint_cpu_time = active_task.get(
                    "checkpoint_cpu_time", timedelta()
                )
                current_cpu_time = active_task.get(
                    "current_cpu_time", timedelta()
                )
                project_url = result.get("project_url", "")
                name = result.get("name", "")
                task_state = active_task.get("active_task_state")

                # If task is not actively executing (e.g. 0 waiting, 9 suspended),
                # suspend waiting tasks immediately and never count them as running.
                if task_state != 1:
                    if task_state == 0:
                        await self.rpc_client.suspend_result(project_url, name)
                    continue

                # For executing tasks (task_state == 1):
                # Suspend if checkpoint is recent OR if timeout has expired
                if timed_out or (
                    current_cpu_time - checkpoint_cpu_time
                    < timedelta(seconds=self.checkpoint_time)
                ):
                    await self.rpc_client.suspend_result(project_url, name)
                else:
                    one_task_running = True

        # if all tasks are suspended set run mode to NEVER
        if one_task_running is False:
            await self.rpc_client.set_run_mode(Mode.NEVER, 0)
            self.current_soft_stop_state = False
            self.soft_stop_start_time = None

    async def resume_all_task(self):
        results = await self.rpc_client.get_results()

        # if no task are there, results is a string
        if results == "\n":
            return

        for result in results:
            project_url = result["project_url"]
            name = result["name"]
            await self.rpc_client.resume_result(project_url, name)

    async def get_results(self):
        # make sure rpc client is available
        await self.connect()

        # get results
        return await self.rpc_client.get_results()

    def get_running_task_count(self, results):
        # if no task are there, results is a string
        if results == "\n":
            return 0

        count = 0
        for result in results:
            # check if running
            if "active_task" not in result:
                continue

            # active task is 1, otherwise it is 0
            activeState = result["active_task"]["active_task_state"]
            if activeState == 1:
                count += 1

        return count

    def get_total_task_count(self, results):
        # if no task are there, results is a string
        if results == "\n":
            return 0

        return len(results)

    def average_progress_rate(self, results) -> float:
        total_active_tasks = 0
        total_progress_rate = 0

        for result in results:
            if "active_task" not in result:
                continue

            if "progress_rate" not in result["active_task"]:
                continue

            total_progress_rate += result["active_task"]["progress_rate"]
            total_active_tasks += 1

        if total_active_tasks == 0:
            return 0.0

        # Progress rate is fraction per second. Convert to percentage per hour (%/h):
        # fraction * 100 (%/s) * 3600 (s/h) = %/h
        rate_per_hour = (total_progress_rate / total_active_tasks) * 3600 * 100
        return round(rate_per_hour, 2)

    async def get_projects(self):
        await self.connect()
        try:
            return await self.rpc_client.get_project_status()
        except Exception as err:
            _LOGGER.warning("Could not fetch project status from BOINC host %s: %s", self.host, err)
            return []

    def get_total_rac(self, projects) -> float:
        if not projects or not isinstance(projects, list):
            return 0.0
        total = 0.0
        for p in projects:
            rac = getattr(p, "host_expavg_credit", 0.0) or 0.0
            try:
                total += float(rac)
            except (ValueError, TypeError):
                pass
        return round(total, 1)

    def get_total_credit(self, projects) -> int:
        if not projects or not isinstance(projects, list):
            return 0
        total = 0.0
        for p in projects:
            credit = getattr(p, "host_total_credit", 0.0) or 0.0
            try:
                total += float(credit)
            except (ValueError, TypeError):
                pass
        return int(round(total))

    def get_projects_detail(self, projects) -> dict[str, dict[str, float]]:
        if not projects or not isinstance(projects, list):
            return {}
        details = {}
        for p in projects:
            name = (
                getattr(p, "project_name", None)
                or getattr(p, "name", None)
                or getattr(p, "master_url", None)
                or "Unknown"
            )
            rac = getattr(p, "host_expavg_credit", 0.0) or 0.0
            credit = getattr(p, "host_total_credit", 0.0) or 0.0
            try:
                rac_val = round(float(rac), 2)
            except (ValueError, TypeError):
                rac_val = 0.0
            try:
                credit_val = round(float(credit), 2)
            except (ValueError, TypeError):
                credit_val = 0.0
            details[str(name)] = {
                "rac": rac_val,
                "total_credit": credit_val,
            }
        return details

    async def get_version(self) -> str | None:
        if not self.rpc_client:
            return None
        try:
            v = await self.rpc_client.exchange_versions()
            if isinstance(v, dict):
                major = v.get("major")
                minor = v.get("minor")
                release = v.get("release")
                if major is not None and minor is not None:
                    return f"{major}.{minor}.{release}"
        except Exception as err:
            _LOGGER.debug("Could not fetch BOINC client version: %s", err)
        return None

    async def get_cc_status(self) -> dict:
        await self.connect()
        try:
            res = await self.rpc_client.get_cc_status()
            if isinstance(res, dict):
                return res
        except Exception as err:
            _LOGGER.debug("Could not fetch cc_status: %s", err)
        return {}
