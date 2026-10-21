"""Boinc Control integration logic."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from .pyboinc.pyboinc import init_rpc_client
from .pyboinc.pyboinc.rpc_client import BOINCClientError, Mode

_LOGGER = logging.getLogger(__name__)


def _extract_project_credit(project: Any) -> float:
    """Extract total credit for a project with fallback hierarchy."""
    val = (
        getattr(project, "host_total_credit", None)
        or getattr(project, "total_credit", None)
        or getattr(project, "user_total_credit", None)
        or 0.0
    )
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _extract_project_rac(project: Any) -> float:
    """Extract RAC (recent average credit) for a project with fallback hierarchy."""
    val = (
        getattr(project, "host_expavg_credit", None)
        or getattr(project, "expavg_credit", None)
        or getattr(project, "user_expavg_credit", None)
        or 0.0
    )
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


class BoincControl:
    def __init__(self, host: str, password: str, checkpoint_time: int) -> None:
        self.current_soft_stop_state = False
        self.soft_stop_start_time: datetime | None = None
        self.host = host
        self.password = password
        self.checkpoint_time = checkpoint_time
        self.rpc_client = None
        self.version = None
        self.model = None

    async def connect(self):
        if self.rpc_client is not None and getattr(self.rpc_client, "connected", False):
            return
        if self.rpc_client is not None:
            await self.disconnect()
        client = await init_rpc_client(self.host, self.password)
        try:
            if not await client.authorize():
                raise BOINCClientError(f"Authorization failed for BOINC host {self.host}")
        except Exception:
            await client.close()
            raise
        self.rpc_client = client
        if self.version is None:
            self.version = await self.get_version()
        if self.model is None:
            self.model = await self.get_model()

    async def disconnect(self):
        if self.rpc_client is not None:
            try:
                await self.rpc_client.close()
            except Exception:
                pass
            finally:
                self.rpc_client = None

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

        # if no tasks are there, results is a string or non-list
        if not isinstance(results, list):
            return

        for result in results:
            if not isinstance(result, dict):
                continue
            project_url = result.get("project_url")
            name = result.get("name")
            if project_url and name:
                await self.rpc_client.resume_result(project_url, name)

    async def get_results(self):
        # make sure rpc client is available
        await self.connect()

        # get results
        try:
            return await self.rpc_client.get_results()
        except Exception:
            await self.disconnect()
            raise

    def get_running_task_count(self, results):
        if not isinstance(results, list):
            return 0

        count = 0
        for result in results:
            active_task = result.get("active_task") if isinstance(result, dict) else None
            if active_task and active_task.get("active_task_state") == 1:
                count += 1

        return count

    def get_total_task_count(self, results):
        if not isinstance(results, list):
            return 0

        return len(results)

    def average_progress_rate(self, results) -> float:
        if not isinstance(results, list):
            return 0.0

        total_active_tasks = 0
        total_progress_rate = 0.0

        for result in results:
            active_task = result.get("active_task") if isinstance(result, dict) else None
            if active_task and "progress_rate" in active_task:
                try:
                    total_progress_rate += float(active_task["progress_rate"])
                    total_active_tasks += 1
                except (ValueError, TypeError):
                    pass

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
        except Exception:
            await self.disconnect()
            raise

    def get_total_rac(self, projects) -> float:
        if not projects or not isinstance(projects, list):
            return 0.0
        total = sum(_extract_project_rac(p) for p in projects)
        return round(total, 1)

    def get_total_credit(self, projects) -> int:
        if not projects or not isinstance(projects, list):
            return 0
        total = sum(_extract_project_credit(p) for p in projects)
        return int(round(total))

    def get_completed_tasks(self, projects) -> int:
        if not projects or not isinstance(projects, list):
            return 0
        total = 0
        for p in projects:
            njobs = getattr(p, "njobs_success", 0) or 0
            try:
                total += int(njobs)
            except (ValueError, TypeError):
                pass
        return total

    def get_failed_tasks(self, projects) -> int:
        if not projects or not isinstance(projects, list):
            return 0
        total = 0
        for p in projects:
            njobs = getattr(p, "njobs_error", 0) or 0
            try:
                total += int(njobs)
            except (ValueError, TypeError):
                pass
        return total

    def get_projects_detail(self, projects) -> dict[str, dict[str, Any]]:
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
            rac_val = round(_extract_project_rac(p), 2)
            credit_val = round(_extract_project_credit(p), 2)
            njobs_success = getattr(p, "njobs_success", 0) or 0
            njobs_error = getattr(p, "njobs_error", 0) or 0
            try:
                success_val = int(njobs_success)
            except (ValueError, TypeError):
                success_val = 0
            try:
                error_val = int(njobs_error)
            except (ValueError, TypeError):
                error_val = 0
            details[str(name)] = {
                "rac": rac_val,
                "total_credit": credit_val,
                "completed_tasks": success_val,
                "failed_tasks": error_val,
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

    async def get_host_info(self) -> dict | None:
        if not self.rpc_client:
            return None
        try:
            res = await self.rpc_client.get_host_info()
            if isinstance(res, dict):
                return res
        except Exception as err:
            _LOGGER.debug("Could not fetch BOINC host info: %s", err)
        return None

    @staticmethod
    def _extract_gpu_model(coprocs: Any) -> str | None:
        raw_names: list[str] = []
        if isinstance(coprocs, list):
            for item in coprocs:
                if isinstance(item, dict) and "name" in item and isinstance(item["name"], str):
                    raw_names.append(item["name"].strip())
                elif isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, dict) and "name" in v and isinstance(v["name"], str):
                            raw_names.append(v["name"].strip())
        elif isinstance(coprocs, dict):
            if "name" in coprocs and isinstance(coprocs["name"], str):
                raw_names.append(coprocs["name"].strip())
            for v in coprocs.values():
                if isinstance(v, dict) and "name" in v and isinstance(v["name"], str):
                    raw_names.append(v["name"].strip())
                elif isinstance(v, list):
                    for sub in v:
                        if isinstance(sub, dict) and "name" in sub and isinstance(sub["name"], str):
                            raw_names.append(sub["name"].strip())

        unique_names = list(dict.fromkeys(n for n in raw_names if n))
        return ", ".join(unique_names) if unique_names else None

    async def get_model(self) -> str | None:
        host_info = await self.get_host_info()
        if not host_info:
            return None

        cpu_model = host_info.get("p_model")
        if isinstance(cpu_model, str):
            cpu_model = " ".join(cpu_model.split()).strip()
            if not cpu_model:
                cpu_model = None
        else:
            cpu_model = None

        coprocs = host_info.get("coprocs")
        gpu_model = self._extract_gpu_model(coprocs)

        if cpu_model and gpu_model:
            return f"{cpu_model} | {gpu_model}"
        if cpu_model:
            return cpu_model
        if gpu_model:
            return gpu_model
        return None

    async def get_cc_status(self) -> dict:
        await self.connect()
        try:
            res = await self.rpc_client.get_cc_status()
            if isinstance(res, dict):
                return res
            return {}
        except Exception:
            await self.disconnect()
            raise
