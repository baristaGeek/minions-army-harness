"""Shared logging helpers for structured single-line application logs."""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from pathlib import Path

WELCOME_BANNER = r'''
 __        __  _____  _      ____  ___  __  __  _____
 \ \      / / | ____|| |    / ___|/ _ \|  \/  || ____|
  \ \ /\ / /  |  _|  | |   | |  _| | | | |\/| ||  _|
   \ V  V /   | |___ | |***| || | || | |  | || |***
    \_/\_/    |_____||_____|\____|\___/|*|  |*||_____|

 _____ ___    __  __ ___ _   _ ___ ___  _   _ ____
|_   */ \_ \\  |  \\/  |* *| \\ | |* _/ _ \| \ | / ___|
  | || | | | | |\/| || ||  \| || | | | |  \| \___ \
  | || |*| | | |  | || || |\\  || | |*| | |\  |___) |
  |*| \_\_\_/  |*|  |*|\_\_\_|*| \_|___\___/|_| \_|____/

     _    ____  __  __ __   __
    / \  |  _ \|  \/  |\ \ / /
   / _ \ | |_) | |\/| | \ V /
  / ___ \|  _ <| |  | |  | |
 /*/   \_\_| \_\_|  |*|  |_|

 __  __ ___ _   _ ___ ___  _   _
|  \/  |_ *| \\ | |* _/ _ \| \ | |
| |\/| || ||  \| || | | | |  \| |
| |  | || || |\  || | |_| | |\  |
|*|  |*|***|\_| \_|***\___/|_| \_|

  ___  ____  _____ _   _ ____   ___  _   _ ____   ____ _____
 / _ \|  _ \| ____| \ | / ___| / _ \| | | |  _ \ / ___| ____|
| | | | |_) |  *| |  \\| \_\_\_ \\| | | | | | | |*) | |   |  _|
| |*| |  \_\_/| |****| |\\  |****) | |*| | |_| |  _ <| |***| |***
 \___/|*|   |\_\_\_\_\_|*| \_|____/ \___/ \___/|_| \_\\____|_____|


                 .-"""""""-.
               .'           '.
              /   _________   \
             | .-'         '-. |
            /==|   .-----.   |==\
           |   |  /       \  |   |
           |   | |   (O)   | |   |
           |   |  \   ^   /  |   |
           |   |   '-----'   |   |
           |   |    \___/    |   |
            \  |             |  /
             '.|_____________|.'
              /|     | |     |\
             / |_____|_|_____| \
            |  |  ___   ___  |  |
            |  | |   | |   | |  |
            |  |*|\_\_\_|*|___|_|  |
             \____|     |____/
                 |     |
                /|     |\
               /*|     |*\
'''


def collapse_log_text(value: object, *, max_length: int = 400) -> str:
    text = " ".join(str(value).split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_log_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return collapse_log_text(value)
    if isinstance(value, (list, tuple, dict)):
        return collapse_log_text(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return str(value)


def build_log_message(event: str, **fields: object) -> str:
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={format_log_value(value)}")
    return f"[MINION][APP][{event}] " + " | ".join(parts)


def build_step_log_message(
    step_name: str,
    state: str,
    duration_ms: int | None = None,
    *,
    execution_id: str | None = None,
    step_seq: int | None = None,
) -> str:
    parts = [
        f"event=pipeline.step.{state}",
        f"step_name={step_name}",
        f"state={state}",
    ]
    if execution_id is not None:
        parts.append(f"execution_id={execution_id}")
    if step_seq is not None:
        parts.append(f"step_seq={step_seq}")
    if duration_ms is not None:
        parts.append(f"duration_ms={duration_ms}")
    banner = f"[MINION][STEP][{state}] {step_name}"
    return banner + " | " + " | ".join(parts)


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    logger.log(level, build_log_message(event, **fields))


def log_welcome_banner(logger: logging.Logger) -> None:
    logger.info(WELCOME_BANNER)


def log_exception(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.exception(build_log_message(event, **fields))


def format_command(command: list[str]) -> str:
    return shlex.join(command)


def log_subprocess_failure(
    logger: logging.Logger,
    event: str,
    *,
    command: list[str],
    cwd: Path,
    completed: subprocess.CompletedProcess[str],
) -> None:
    log_event(
        logger,
        logging.ERROR,
        event,
        command=format_command(command),
        cwd=cwd,
        exit_code=completed.returncode,
        stdout_tail=(completed.stdout or "")[-1200:],
        stderr_tail=(completed.stderr or "")[-1200:],
    )
