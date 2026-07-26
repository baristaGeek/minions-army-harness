"""Minion execution launchers."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import uuid4

from minions_army.core.config.loader import config as settings
from minions_army.core.runtime.logging import format_command, log_event, log_exception
from minions_army.domain.models import SlackMessage, WebAPIMessage
from minions_army.infrastructure.agents.loader import load_agent_provider
from minions_army.infrastructure.integrations.slack.notifier import post_slack_message

logger = logging.getLogger(__name__)

MINION_COMMAND = ["minion-orchestrator"]
WebhookMessage = SlackMessage | WebAPIMessage


def _slack_bot_token() -> str | None:
    return settings.slack.bot_token or os.environ.get("SLACK_BOT_TOKEN")


class MinionTaskLauncher(ABC):
    """Launches a minion container for a webhook message."""

    def __init__(self, image: str | None = None) -> None:
        image = image or settings.launcher.image
        self.image = image

    @abstractmethod
    def run_for_message(self, message: WebhookMessage) -> None:
        """Start the minion workload for the message."""

    def _base_environment(self, message: WebhookMessage) -> dict[str, str]:
        environment = {
            "HOME": "/root",
            "MINION_INPUT_MESSAGE": message.text,
            "DATABASE_URL": settings.database.url,
        }
        environment.update(self._message_environment(message))
        environment.update(load_agent_provider(settings.agent.provider_class).environment(settings))
        if settings.launcher.fly_api_token:
            environment["FLY_API_TOKEN"] = settings.launcher.fly_api_token
        slack_bot_token = _slack_bot_token()
        if slack_bot_token:
            environment["SLACK_BOT_TOKEN"] = slack_bot_token
        if settings.repository.name:
            environment["REPOSITORY_NAME"] = settings.repository.name
        if settings.repository.base_branch:
            environment["REPOSITORY_BASE_BRANCH"] = settings.repository.base_branch
        if settings.repository.feature_branch:
            environment["REPOSITORY_FEATURE_BRANCH"] = settings.repository.feature_branch
        if settings.repository.github_token:
            environment["GITHUB_TOKEN"] = settings.repository.github_token
        return environment

    def _message_environment(self, message: WebhookMessage) -> dict[str, str]:
        if isinstance(message, SlackMessage):
            return self._slack_environment(message)
        if isinstance(message, WebAPIMessage):
            return self._webapi_environment(message)
        raise TypeError(f"Unsupported webhook message type: {type(message).__name__}")

    @staticmethod
    def _slack_environment(message: SlackMessage) -> dict[str, str]:
        environment = {
            "MINION_WEBHOOK_SOURCE": "slack",
            "SLACK_CHANNEL_ID": message.channel_id,
            "SLACK_MESSAGE_ID": str(message.id or ""),
        }
        if message.user_id:
            environment["SLACK_USER_ID"] = message.user_id
        if message.slack_event_ts:
            environment["SLACK_EVENT_TS"] = message.slack_event_ts
        return environment

    @staticmethod
    def _webapi_environment(message: WebAPIMessage) -> dict[str, str]:
        environment = {
            "MINION_WEBHOOK_SOURCE": "webapi",
            "WEBAPI_SESSION_ID": message.session_id,
            "WEBAPI_MESSAGE_ID": str(message.id or ""),
        }
        if message.user_id:
            environment["WEBAPI_USER_ID"] = message.user_id
        return environment

    def _container_name(self) -> str:
        return f"minion_{uuid4().hex[:12]}"

    def _notify_started(self, message: WebhookMessage) -> None:
        """Immediately acknowledge the request in the Slack thread (best-effort)."""
        if isinstance(message, WebAPIMessage):
            return
        slack_bot_token = _slack_bot_token()
        if not slack_bot_token:
            log_event(
                logger,
                logging.WARNING,
                "launcher.notify_started.skipped",
                reason="missing_slack_token",
                has_slack_bot_token=bool(os.environ.get("SLACK_BOT_TOKEN")),
                has_config_slack_bot_token=bool(settings.slack.bot_token),
            )
            return
        log_event(
            logger,
            logging.INFO,
            "launcher.notify_started.attempting",
            channel_id=message.channel_id,
            thread_ts=message.slack_event_ts,
        )
        post_slack_message(
            "On it - I'll propose a change, open a PR, and review it before shipping.",
            token=slack_bot_token,
            channel=message.channel_id,
            thread_ts=message.slack_event_ts,
        )

    def _cloud_run_environment(self, message: WebhookMessage) -> dict[str, str]:
        environment = self._base_environment(message)
        environment["MINION_CONTAINER_NAME"] = self._container_name()
        return environment


class DockerSiblingTaskRunner(MinionTaskLauncher):
    """Starts a Docker sibling container for each Slack message."""

    def run_for_message(self, message: WebhookMessage) -> None:
        """Start a detached Docker container and log whether it was created."""
        self._notify_started(message)
        try:
            import docker
        except ImportError:
            log_exception(logger, "launcher.docker.import_failed")
            return

        environment = self._base_environment(message)

        try:
            log_event(
                logger,
                logging.INFO,
                "launcher.docker.prepared",
                message_id=message.id,
                channel_id=getattr(message, "channel_id", None),
                image=self.image,
            )
            client = docker.from_env()
            container_name = self._container_name()
            environment["MINION_CONTAINER_NAME"] = container_name
            kwargs: dict[str, Any] = {
                "image": self.image,
                "detach": True,
                "name": container_name,
                "command": MINION_COMMAND,
                "environment": environment,
                "labels": {
                    "app": settings.app.name,
                    "source": self._source_label(message),
                },
            }
            if settings.launcher.codex_home:
                kwargs["volumes"] = {
                    settings.launcher.codex_home: {
                        "bind": "/root/.codex",
                        "mode": "rw",
                    }
                }
                environment["CODEX_HOME"] = "/root/.codex"
            log_event(
                logger,
                logging.INFO,
                "launcher.docker.starting",
                container_name=container_name,
                image=self.image,
                message_id=message.id,
            )
            container = client.containers.run(**kwargs)
            log_event(
                logger,
                logging.INFO,
                "launcher.docker.started",
                container_id=container.id,
                container_name=container_name,
                message_id=message.id,
            )
        except Exception:
            log_exception(
                logger,
                "launcher.docker.failed",
                message_id=message.id,
                image=self.image,
                channel_id=getattr(message, "channel_id", None),
            )

    @staticmethod
    def _source_label(message: WebhookMessage) -> str:
        if isinstance(message, SlackMessage):
            return "slack-webhook"
        if isinstance(message, WebAPIMessage):
            return "webapi-webhook"
        raise TypeError(f"Unsupported webhook message type: {type(message).__name__}")


class CloudJobsRunTaskRunner(MinionTaskLauncher):
    """Starts a Cloud Jobs Run job using the same image and env contract."""

    def run_for_message(self, message: WebhookMessage) -> None:
        self._notify_started(message)
        try:
            self._require_gcloud()
            environment = self._cloud_run_environment(message)
            job_name = settings.launcher.cloud_run_job_name
            self._validate_cloud_run_settings()
            with self._temp_env_file(environment) as env_file:
                create_or_update_command = self._create_or_update_command(job_name, env_file)
                log_event(
                    logger,
                    logging.INFO,
                    "launcher.cloud_run.prepared",
                    message_id=message.id,
                    channel_id=getattr(message, "channel_id", None),
                    image=self.image,
                    job_name=job_name,
                    command=format_command(create_or_update_command),
                )
                completed = subprocess.run(
                    create_or_update_command,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if completed.returncode != 0:
                    log_event(
                        logger,
                        logging.ERROR,
                        "launcher.cloud_run.command_failed",
                        message_id=message.id,
                        image=self.image,
                        job_name=job_name,
                        exit_code=completed.returncode,
                        error=self._format_gcloud_error(completed),
                    )
                    return
                log_event(
                    logger,
                    logging.INFO,
                    "launcher.cloud_run.started",
                    job_name=job_name,
                    message_id=message.id,
                    image=self.image,
                )
        except Exception:
            log_exception(
                logger,
                "launcher.cloud_run.failed",
                message_id=message.id,
                image=self.image,
                channel_id=getattr(message, "channel_id", None),
            )

    def _validate_cloud_run_settings(self) -> None:
        missing = []
        if not settings.launcher.cloud_run_project:
            missing.append("MINION_CLOUD_RUN_PROJECT")
        if not settings.launcher.cloud_run_region:
            missing.append("MINION_CLOUD_RUN_REGION")
        if missing:
            raise SystemExit(f"Missing required Cloud Run settings: {', '.join(missing)}")

    def _require_gcloud(self) -> None:
        if shutil.which("gcloud") is None:
            raise SystemExit("gcloud is required for Cloud Run execution but was not found")

    def _create_or_update_command(self, job_name: str, env_file: Path) -> list[str]:
        command = [
            "gcloud",
            "run",
            "jobs",
            "create",
            job_name,
            f"--image={self.image}",
            "--command=minion-orchestrator",
            f"--region={settings.launcher.cloud_run_region}",
            f"--project={settings.launcher.cloud_run_project}",
            f"--env-vars-file={env_file}",
            "--execute-now",
            "--wait",
        ]
        if self._job_exists(job_name):
            command[3] = "update"
        return command

    def _job_exists(self, job_name: str) -> bool:
        completed = subprocess.run(
            [
                "gcloud",
                "run",
                "jobs",
                "describe",
                job_name,
                f"--region={settings.launcher.cloud_run_region}",
                f"--project={settings.launcher.cloud_run_project}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0

    def _temp_env_file(self, environment: dict[str, str]):
        handle = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        try:
            for key, value in environment.items():
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                handle.write(f'{key}="{escaped}"\n')
        finally:
            handle.close()

        class _TempEnvFile:
            def __init__(self, path: Path) -> None:
                self.path = path

            def __enter__(self) -> Path:
                return self.path

            def __exit__(self, exc_type, exc, tb) -> None:
                self.path.unlink(missing_ok=True)

        return _TempEnvFile(Path(handle.name))

    def _format_gcloud_error(self, completed: subprocess.CompletedProcess[str]) -> str:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        details = stderr or stdout or "unknown error"
        return f"Cloud Run job command failed with exit code {completed.returncode}: {details}"


class FlyMachinesTaskRunner(MinionTaskLauncher):
    """Runs each minion as an ephemeral Fly Machine via `flyctl machine run`.

    This is the production backend on Fly.io, where the Docker socket is not
    available for sibling containers. The machine is removed on exit (`--rm`).
    """

    def run_for_message(self, message: WebhookMessage) -> None:
        self._notify_started(message)
        try:
            self._require_flyctl()
            self._validate_settings()
            environment = self._cloud_run_environment(message)
            command = self._machine_run_command(environment)
            log_event(
                logger,
                logging.INFO,
                "launcher.fly_machine.starting",
                message_id=message.id,
                channel_id=getattr(message, "channel_id", None),
                image=self.image,
                app=settings.launcher.fly_app,
                command=format_command(command),
            )
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=self._flyctl_env(),
            )
            if completed.returncode != 0:
                log_event(
                    logger,
                    logging.ERROR,
                    "launcher.fly_machine.command_failed",
                    message_id=message.id,
                    image=self.image,
                    exit_code=completed.returncode,
                    error=self._format_error(completed),
                )
                return
            log_event(
                logger,
                logging.INFO,
                "launcher.fly_machine.started",
                message_id=message.id,
                image=self.image,
            )
        except Exception:
            log_exception(
                logger,
                "launcher.fly_machine.failed",
                message_id=message.id,
                image=self.image,
                channel_id=getattr(message, "channel_id", None),
            )

    def _require_flyctl(self) -> None:
        if shutil.which("flyctl") is None and shutil.which("fly") is None:
            raise SystemExit("flyctl is required for fly_machines execution but was not found")

    def _validate_settings(self) -> None:
        missing = []
        if not settings.launcher.fly_machine_app:
            missing.append("MINION_FLY_MACHINE_APP")
        if not settings.launcher.fly_api_token:
            missing.append("FLY_API_TOKEN")
        if missing:
            raise SystemExit(f"Missing required Fly settings: {', '.join(missing)}")

    def _machine_run_command(self, environment: dict[str, str]) -> list[str]:
        binary = "flyctl" if shutil.which("flyctl") else "fly"
        command = [
            binary,
            "machine",
            "run",
            self.image,
            "--app",
            settings.launcher.fly_machine_app or "",
            "--region",
            settings.launcher.fly_region,
            "--vm-memory",
            str(settings.launcher.fly_vm_memory),
            "--vm-cpus",
            str(settings.launcher.fly_vm_cpus),
            "--rm",
            "--command",
            "minion-orchestrator",
        ]
        for key, value in environment.items():
            command.extend(["--env", f"{key}={value}"])
        return command

    def _flyctl_env(self) -> dict[str, str]:
        env = {**os.environ}
        if settings.launcher.fly_api_token:
            env["FLY_API_TOKEN"] = settings.launcher.fly_api_token
        return env

    def _format_error(self, completed: subprocess.CompletedProcess[str]) -> str:
        details = (completed.stderr or "").strip() or (completed.stdout or "").strip() or "unknown"
        return f"flyctl machine run failed with exit code {completed.returncode}: {details}"


def build_minion_task_runner() -> MinionTaskLauncher:
    backend = settings.launcher.backend.lower().strip()
    if backend == "docker":
        return DockerSiblingTaskRunner()
    if backend in {"cloud_jobs", "cloud-jobs", "cloud-jobs-run"}:
        return CloudJobsRunTaskRunner()
    if backend in {"fly_machines", "fly-machines", "fly"}:
        return FlyMachinesTaskRunner()
    raise SystemExit(
        "Unsupported MINION_EXECUTION_BACKEND "
        f"'{settings.launcher.backend}'. Expected 'docker', 'fly_machines', or 'cloud_jobs'."
    )
