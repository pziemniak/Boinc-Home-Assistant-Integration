"""Constants for the Boinc Control integration."""

DOMAIN = "spuelmett_boinc"
NAME = "name"
BOINC_IP = "remote_ip"
PASSWORD = "password"
CHECKPOINTING = "checkpoint_time"
LISTENER = "remove_listener"

RUNNING_TASK_COUNT = "running_task"
TOTAL_TASK_COUNT = "total_task"
AVERAGE_PROGRESS_RATE = "average_progess_rate"
TOTAL_RAC = "total_rac"
TOTAL_CREDIT = "total_credit"
COMPLETED_TASK_COUNT = "completed_tasks"
FAILED_TASK_COUNT = "failed_tasks"
PROJECTS_DETAIL = "projects_detail"
TASK_MODE = "task_mode"
GPU_MODE = "gpu_mode"

# BOINC run modes
BOINC_MODE_ALWAYS = 1
BOINC_MODE_AUTO = 2
BOINC_MODE_NEVER = 3
BOINC_MODE_RESTORE = 4
