# Boinc Control for Home Assistant

This Home Assistant integration lets you start and stop BOINC running on another machine on your network from Home Assistant, which means that it allows you to create automations that:
* Use excess solar to benefit science.
* Instead of using direct electric heating for a room, use the heat from your BOINC server to heat a room, and benefit science. 

If you are looking to run BOINC on your Home Assistant host, use the [BOINC add-on](https://github.com/hectorespert/boinc-addons).

Features:
* Start BOINC service
* Hard and soft stop
* Control the usage of GPU separately (if desired)
* Sensors for *total tasks*, *running tasks*, *completed tasks*, *failed tasks*, *average progress rate* (%/h), *Total RAC* (credits/day) and *Total Credit* (with native LTS hourly/daily/weekly tracking)
* Native switches for BOINC Computations (Start / Soft Stop) and GPU (Start / Stop)
* Native button for Immediate / Hard Stop
* Detailed project telemetry: per-project credit, RAC, completed tasks, and dedicated `failed_projects` breakdown on the Failed Tasks sensor
* Control multiple BOINC servers (grouped into dedicated Home Assistant devices)

# Installation

1. Configure Boinc to allow remote control. This typically includes editing ```remote_hosts.cfg``` and ```gui_rpc_auth.cfg``` and restarting BOINC.
1. Copy the ```/spuelmett_boinc``` folder from this project into your Home Assistant's folder ```config/custom_components```.
2. Restart Home Assistant
3. Add integration "Boinc Control"
4. Enter a name, the IP-adress (no port) and the password you have set in ```gui_rpc_auth.cfg```
1. If the connection was successful you'll get a message about it. If it was unsuccessful, then do some network troubleshooting 
2. Verify that the integration works. Open the new BOINC device and toggle the **Computations** switch to start and stop BOINC and see that BOINC is responding as expected.
1. Create your automations of choice using the BOINC switches, buttons and services available in your Home Assistant.

# Understanding the BOINC control services

The actions below can be triggered with the native entities (recommended) or with the per-host services (`spuelmett_boinc.<action>_<hostname>`), which are kept for backwards compatibility.

## Start BOINC
Sets the run mode of your remote BOINC machine to "run based on preferences".

You start BOINC by:
* Turning on the native **Computations** switch (`switch.boinc_<name>_computations`), or
* Calling the service ```spuelmett_boinc.start_boinc_<hostname>```.

## Stop BOINC (Hard stop)
Sets the run mode of your remote BOINC machine to "never". This stops all running tasks immediately without waiting for checkpoints, and cancels any pending soft stop.

You can trigger a hard stop by:
* Pressing the native **Stop immediately** button (`button.boinc_<name>_stop_immediately`), or
* Calling the service ```spuelmett_boinc.stop_boinc_<hostname>```.

## Soft stop BOINC
When different BOINC projects run, they will on a regular basis perform a *checkpoint*. A checkpoint is used to secure the data already computed. When the client is stopped, all compute done after a checkpoint will be lost, having to be re-computed next time BOINC resumes. The frequency of checkpoints varies by project and task. 

This integration implements a _soft stop_ by waiting until next checkpoint (a simplified description, see next chapter for details).

You soft stop BOINC by:
* Toggling the native **Computations** switch to off (`switch.boinc_<name>_computations`), or
* Calling the service ```spuelmett_boinc.soft_stop_boinc_<hostname>```.

Once checkpoints have been reached across all tasks, the run mode of your remote BOINC machine is set to "never".

## GPU control
The GPU can be started and stopped independently of the CPU computations:
* Toggling the native **GPU computations** switch (`switch.boinc_<name>_gpu_computations`), or
* Calling ```spuelmett_boinc.start_gpu_<hostname>``` / ```spuelmett_boinc.stop_gpu_<hostname>```.

### Optimizing soft stop
Since each BOINC project and task differs in how often checkpoints are made, there can be scenarios where you'd like to optimize the soft stop. To do so, you need to understand how the soft stop works in this integration:

* If the last checkpoint was made less than 120 seconds ago, the integration requests the host to suspend the task immediately (limiting computation loss to < 120 seconds). The 120 seconds is configurable in integration Options (`checkpoint_time`).
* If the last checkpoint was made longer ago, the integration leaves the task running and waits for the next checkpoint to be recorded (checked every 60 seconds).
* **Safety Timeout:** To prevent tasks with very long or broken checkpoint intervals from running indefinitely, the integration enforces a safety timeout (10 minutes or 3× `checkpoint_time`). If a task has not checkpointed within this timeout, it is suspended automatically.
* If you need to halt computations immediately while a soft stop is in progress, trigger a **Hard stop** (`button.boinc_<name>_stop_immediately`).

# Example configurations

## Automation
An example automation that starts BOINC if the energy consumption from grid is under -10 watts for 5 minutes, using the native computations switch.
```yaml
alias: Start BOINC on solar surplus
description: ''
triggers:
  - trigger: numeric_state
    entity_id: sensor.energymetermqtt_sml_curr_w
    below: -10
    for: "00:05:00"
conditions: []
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.boinc_<name>_computations
mode: single
```

And one that soft stops BOINC again when the grid consumption rises above 50 watts for 5 minutes (waits for checkpoints, so no work is wasted):
```yaml
alias: Soft stop BOINC when solar surplus ends
description: ''
triggers:
  - trigger: numeric_state
    entity_id: sensor.energymetermqtt_sml_curr_w
    above: 50
    for: "00:05:00"
conditions: []
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.boinc_<name>_computations
mode: single
```

> The entity IDs are generated by Home Assistant from the device name (`BOINC <name>`) and the entity name. Check the exact ID in the entity settings of your device.

## Native switches and buttons for controlling BOINC

This integration provides native Home Assistant entities to control BOINC directly from your dashboard or automations:

* **Computations Switch** (`switch.boinc_<name>_computations`):
  * **Turn on**: starts computations (`start_boinc`).
  * **Turn off**: requests a soft stop (`soft_stop_boinc`), waiting until the next checkpoint to avoid wasting completed work.
  * Note: when stopping, the switch waits for checkpoints before flipping to `off`.
* **GPU Switch** (`switch.boinc_<name>_gpu_computations`):
  * **Turn on**: resumes GPU processing (`start_gpu`).
  * **Turn off**: suspends GPU processing (`stop_gpu`).
  * The GPU is controlled independently of the computations switch.
* **Immediate / Hard Stop Button** (`button.boinc_<name>_stop_immediately`):
  * Instantly stops all computations and tasks without waiting for checkpoints (`stop_boinc`).

*(Manual template switch configuration in `configuration.yaml` is no longer required.)*

# Troubleshooting connectivity

* Double check ```remote_hosts.cfg``` and ```gui_rpc_auth.cfg```
* Can you connect from the HA host to the BOINC machine?
* Is there a firewall on the BOINC server blocking you?
* If you use Docker - have you allowed port 31416?

# Credit
This project uses [pyboinc](https://github.com/nielstron/pyboinc/tree/dev/pyboinc) from Nielstron.

# Changelog

## 0.0.11
* Added `Completed tasks` sensor (`sensor.<name>_completed_tasks`, unit `tasks`, state class `total_increasing` for Home Assistant LTS).
* Added `Failed tasks` sensor (`sensor.<name>_failed_tasks`, unit `tasks`, state class `total_increasing` for Home Assistant LTS).
* Added detailed failure breakdown to `Failed tasks` attributes (`failed_projects` listing only projects with errors, `failed_projects_count`, and `overall_success_rate`).
* Added `completed_tasks` breakdown and overall success rate to `Completed tasks` attributes.
* Extended `projects` telemetry dictionary with `completed_tasks` and `failed_tasks` counters.
* Pointed documentation and issue tracker URLs to repository fork (`pziemniak/Boinc-Home-Assistant-Integration`).
* Updated maintainers/codeowners to include both `@pziemniak` and `@SpuelMett`.

## 0.0.10
* Removed the redundant `strings.json`; `translations/en.json` is now the only string source.
* Documentation: automation examples now use the native switch; entity IDs and GPU control are documented.

## 0.0.9
* Added native `switch` entities for BOINC Computations (Start / Soft Stop) and GPU (Start / Stop).
* Added native `button` entity for Immediate / Hard Stop (`button.<instance>_stop_immediately`).
* Added automatic coordinator refresh to all services and switches for instant UI state updates.
* Improved Soft Stop: verify executing task state (`active_task_state == 1`), reset soft-stop state when tasks are halted or hard-stopped, and added safety timeout protection.

## 0.0.8
* Added `Total RAC` sensor (`credits/day`) reflecting host-wide recent credit gain rate.
* Added `Total Credit` sensor with `total_increasing` state class for native Home Assistant Long-Term Statistics (LTS) hourly, daily, and weekly tracking.
* Formatted sensor values and units: progress rate converted to human-readable percentage per hour (`%/h`), Total Credit formatted as integer credits, Total RAC formatted with integer precision.
* Added per-project telemetry breakdown in sensor attributes (`projects` dictionary with individual RAC and credit values).
* Added Home Assistant Device Registry support (`DeviceInfo`) grouping each BOINC host into a dedicated device card with hardware/software metadata, Area assignment, and configuration links.
* Automatically detect and report BOINC client software version via RPC.
* Allowed dashes (`-`) and underscores (`_`) in instance names with automatic service name sanitization.
* Added entity translations and icons.

## 0.0.7
* Added start and stop actions for GPU
* Improved Soft Stop feature to Stop all non-running task immediately to avoid starting them for a few seconds
* Minor bug fixes
* Tested with Home Assistant 2025.6.0

## 0.0.6
* Added basic sensor information about "total tasks", "running tasks" and "average progress rate"

## 0.0.5
* Add Input validation for Integration Name to prevent error due to service naming.
* You may need to delete and read your integration in case you used special characters

## 0.0.4
* Update deprecated stuff for Home Assistant 2025.6.0

# Roadmap
* Add Availability sensor to check if boinc is running and the remote access works
