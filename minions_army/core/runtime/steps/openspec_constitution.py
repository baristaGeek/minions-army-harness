"""Pipeline step implementation."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from minions_army.application.services.orchestration_service import (
    OrchestrationResult,
    PipelineContext,
)
from minions_army.core.runtime import agent_execution
from minions_army.core.runtime import orchestrator_runtime as runtime
from minions_army.core.runtime.logging import build_step_log_message, log_event

logger = logging.getLogger("minions_army.core.runtime.orchestrator_runtime")


@dataclass
class OpenspecConstitutionStep:
    name: str = "openspec-constitution"
    skip: bool = False

    def _config_path(self, result: OrchestrationResult) -> Path:
        return result.repository_path / "openspec" / "config.yaml"

    def _looks_like_default_config(self, text: str) -> bool:
        normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        default_candidates = {
            "",
            "{}",
            "---",
            "null",
            "openspec: {}",
            "config: {}",
        }
        if normalized in default_candidates:
            return True
        if "TODO" in normalized and "constitution" not in normalized.lower():
            return True
        return False

    def _has_expected_openspec_structure(self, text: str) -> bool:
        lowered = text.lower()
        if "schema:" not in lowered or "context:" not in lowered or "rules:" not in lowered:
            return False
        if "schema: spec-driven" not in lowered:
            return False
        rule_sections = (
            "proposal:",
            "design:",
            "tasks:",
            "implementation:",
            "testing:",
            "quality:",
            "security:",
            "deployment:",
            "documentation:",
            "database:",
        )
        present_sections = sum(1 for section in rule_sections if section in lowered)
        return present_sections >= 2

    def _has_repository_specific_context(self, text: str) -> bool:
        lowered = text.lower()
        repository_markers = (
            "tech stack",
            "architecture",
            "component boundaries",
            "engineering standards",
            "languages",
            "frameworks",
            "components",
            "testing",
            "security",
            "deployment",
            "backend",
            "frontend",
            "database",
            "api",
            "service",
            "worker",
            "library",
            "cli",
        )
        return any(marker in lowered for marker in repository_markers)

    def _is_prepared_config(self, config_path: Path) -> bool:
        if not config_path.exists() or not config_path.is_file():
            return False
        try:
            text = config_path.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        if not text or self._looks_like_default_config(text):
            return False
        substantive_lines = [
            line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        ]
        if len(substantive_lines) < 3:
            return False
        return self._has_expected_openspec_structure(
            text
        ) and self._has_repository_specific_context(text)

    def _build_skip_output(self, config_path: Path) -> str:
        payload = {
            "status": "skipped",
            "changed": False,
            "reason": "already_configured",
            "output_file": config_path.relative_to(config_path.parent.parent).as_posix(),
            "detected_context": {
                "languages": [],
                "frameworks": [],
                "tools": [],
                "components": [],
            },
            "message": "OpenSpec configuration already exists. No changes were required.",
        }
        return json.dumps(payload, ensure_ascii=False)

    def _read_json_file(self, path: Path) -> dict[str, object] | None:
        if not path.exists() or not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _ignored_directory_names(self) -> set[str]:
        return {
            ".git",
            ".venv",
            ".next",
            ".nuxt",
            "node_modules",
            "dist",
            "build",
            "coverage",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            "bin",
            "obj",
            "target",
            "vendor",
        }

    def _candidate_directories(self, repository_path: Path) -> list[Path]:
        ignored_names = self._ignored_directory_names()
        candidates: list[Path] = [repository_path]

        direct_children = [
            child
            for child in repository_path.iterdir()
            if child.is_dir() and child.name not in ignored_names
        ]
        candidates.extend(direct_children)

        common_containers = {"apps", "services", "packages", "projects", "src"}
        for child in direct_children:
            if child.name.lower() not in common_containers:
                continue
            for nested in child.iterdir():
                if nested.is_dir() and nested.name not in ignored_names:
                    candidates.append(nested)

        deduped: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            if path not in seen:
                deduped.append(path)
                seen.add(path)
        return deduped

    def _package_json_files(self, repository_path: Path) -> list[Path]:
        candidates = [
            path / "package.json" for path in self._candidate_directories(repository_path)
        ]
        deduped: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            if path.exists() and path.is_file() and path not in seen:
                deduped.append(path)
                seen.add(path)
        return deduped

    def _package_json_dependency_names(self, repository_path: Path) -> set[str]:
        names: set[str] = set()
        for package_json in self._package_json_files(repository_path):
            data = self._read_json_file(package_json) or {}
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                deps = data.get(key)
                if isinstance(deps, dict):
                    names.update(str(name).lower() for name in deps)
        return names

    def _read_text_if_exists(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _detect_languages(self, repository_path: Path) -> list[str]:
        languages: list[str] = []
        if (repository_path / "pyproject.toml").exists() or (
            repository_path / "requirements.txt"
        ).exists():
            languages.append("Python")
        package_dependencies = self._package_json_dependency_names(repository_path)
        if self._package_json_files(repository_path):
            has_typescript = any(
                marker in package_dependencies
                for marker in ("typescript", "ts-node", "@types/node")
            ) or any(
                (repository_path / filename).exists()
                for filename in ("tsconfig.json", "tsconfig.app.json", "tsconfig.base.json")
            )
            if has_typescript:
                languages.append("TypeScript")
            else:
                languages.append("JavaScript")
        if any(repository_path.glob("*.sln")) or any(repository_path.rglob("*.csproj")):
            languages.append("C#")
        if (repository_path / "go.mod").exists():
            languages.append("Go")
        return list(dict.fromkeys(languages))

    def _detect_frameworks(self, repository_path: Path) -> list[str]:
        frameworks: list[str] = []
        package_dependencies = self._package_json_dependency_names(repository_path)
        requirements_text = self._read_text_if_exists(repository_path / "requirements.txt").lower()
        pyproject_text = self._read_text_if_exists(repository_path / "pyproject.toml").lower()
        if "fastapi" in requirements_text or "fastapi" in pyproject_text:
            frameworks.append("FastAPI")
        if (
            any(
                (repository_path / filename).exists()
                for filename in ("next.config.js", "next.config.mjs", "next.config.ts")
            )
            or "next" in package_dependencies
        ):
            frameworks.append("Next.js")
        if "react" in package_dependencies:
            frameworks.append("React")
        if "@angular/core" in package_dependencies:
            frameworks.append("Angular")
        if any(repository_path.glob("*.sln")) or any(repository_path.rglob("*.csproj")):
            frameworks.append(".NET")
        if (repository_path / "go.mod").exists():
            frameworks.append("Go modules")
        return list(dict.fromkeys(frameworks))

    def _detect_tools(self, repository_path: Path) -> list[str]:
        tools: list[str] = []
        if (repository_path / "docker-compose.yml").exists():
            tools.append("Docker Compose")
        if (repository_path / "Dockerfile").exists() or (
            repository_path / "Dockerfile.minion"
        ).exists():
            tools.append("Docker")
        if (repository_path / "fly.toml").exists() or (
            repository_path / "fly.minion.toml"
        ).exists():
            tools.append("Fly.io")
        if (repository_path / "pyproject.toml").exists():
            tools.append("pyproject.toml")
        if (repository_path / "requirements.txt").exists():
            tools.append("requirements.txt")
        if self._package_json_files(repository_path):
            tools.append("package.json")
        if any(repository_path.glob("*.sln")):
            tools.append(".sln")
        if any(repository_path.rglob("*.csproj")):
            tools.append(".csproj")
        if (repository_path / "go.mod").exists():
            tools.append("go.mod")
        return list(dict.fromkeys(tools))

    def _component_type_from_path_tokens(self, relative: str, name: str) -> str | None:
        if any(token in relative for token in ("frontend", "web", "ui")):
            return "Frontend application"
        if "api" in relative or name == "api":
            return "API service"
        if "worker" in relative:
            return "Worker service"
        if "cli" in relative:
            return "CLI application"
        if "package" in relative or "lib" in relative or "shared" in relative:
            return "Library/package"
        return None

    def _component_type_from_dependencies(self, package_dependencies: set[str]) -> str | None:
        if "next" in package_dependencies or "react" in package_dependencies:
            return "Frontend application"
        if "@angular/core" in package_dependencies:
            return "Frontend application"
        return None

    def _component_type_from_manifests(self, path: Path) -> str | None:
        if (path / "go.mod").exists():
            return "Go service"
        if any(path.glob("*.csproj")):
            return ".NET service"
        if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
            return "Python service"
        if self._package_json_files(path):
            return "JavaScript/TypeScript package"
        return None

    def _component_type_for_path(self, path: Path, repository_path: Path) -> str:
        relative = path.relative_to(repository_path).as_posix().lower()
        name = path.name.lower()
        package_dependencies = self._package_json_dependency_names(path)
        path_type = self._component_type_from_path_tokens(relative, name)
        if path_type:
            return path_type
        dependency_type = self._component_type_from_dependencies(package_dependencies)
        if dependency_type:
            return dependency_type
        manifest_type = self._component_type_from_manifests(path)
        if manifest_type:
            return manifest_type
        return "Component"

    def _component_candidate_paths(self, repository_path: Path) -> list[Path]:
        candidates: list[Path] = []
        ignored_names = self._ignored_directory_names()
        for path in self._candidate_directories(repository_path):
            if path == repository_path or path.name in ignored_names:
                continue
            if any(
                (path / marker).exists()
                for marker in ("package.json", "pyproject.toml", "requirements.txt", "go.mod")
            ) or any(path.glob("*.csproj")):
                candidates.append(path)
                continue
            relative = path.relative_to(repository_path).as_posix().lower()
            if any(
                token in relative.split("/")
                for token in ("api", "worker", "web", "frontend", "cli")
            ):
                candidates.append(path)

        deduped: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            if path not in seen:
                deduped.append(path)
                seen.add(path)
        return deduped

    def _detect_components(self, repository_path: Path) -> list[str]:
        components: list[str] = []
        for path in self._component_candidate_paths(repository_path):
            relative_path = path.relative_to(repository_path).as_posix()
            label = self._component_type_for_path(path, repository_path)
            components.append(f"{label}: `{relative_path}`")
        return components

    def _relevant_paths(self, repository_path: Path) -> list[str]:
        paths: list[str] = []
        for path in self._component_candidate_paths(repository_path):
            paths.append(path.relative_to(repository_path).as_posix())
        for marker in (
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "go.mod",
            "docker-compose.yml",
            "Dockerfile",
            "alembic",
        ):
            candidate = repository_path / marker
            if candidate.exists():
                paths.append(marker)
        deduped = list(dict.fromkeys(paths))
        return deduped[:12]

    def _build_precomputed_repository_context(self, result: OrchestrationResult) -> str:
        repository_path = result.repository_path
        lines = [
            "Precomputed repository context:",
            f"- Repository root: `{repository_path}`",
            f"- OpenSpec config target: `{self._config_path(result)}`",
            f"- Constitution file: `{repository_path / 'CONSTITUTION.md'}`",
        ]
        languages = self._detect_languages(repository_path)
        frameworks = self._detect_frameworks(repository_path)
        tools = self._detect_tools(repository_path)
        components = self._detect_components(repository_path)
        relevant_paths = self._relevant_paths(repository_path)
        lines.append(
            "- Detected languages: " + (", ".join(languages) if languages else "none detected")
        )
        lines.append(
            "- Detected frameworks: " + (", ".join(frameworks) if frameworks else "none detected")
        )
        lines.append("- Detected tools: " + (", ".join(tools) if tools else "none detected"))
        if components:
            lines.append("- Candidate components:")
            lines.extend(f"  - {component}" for component in components)
        else:
            lines.append("- Candidate components: none detected")
        if relevant_paths:
            lines.append("- Relevant paths:")
            lines.extend(f"  - `{path}`" for path in relevant_paths)
        else:
            lines.append("- Relevant paths: none detected")
        lines.append(
            "- Trust level: treat every item above as precomputed evidence. Reuse it before opening more files."
        )
        return "\n".join(lines)

    def _try_short_circuit(self, context: PipelineContext, result: OrchestrationResult) -> bool:
        config_path = self._config_path(result)
        ready = self._is_prepared_config(config_path)
        log_event(
            logger,
            logging.INFO,
            "constitution.ready_check",
            config_path=config_path,
            ready=ready,
        )
        if not ready:
            return False
        (result.repository_path / ".agent-outputs").mkdir(parents=True, exist_ok=True)
        agent_execution._store_agent_output(
            context,
            result,
            "constitution",
            self._build_skip_output(config_path),
        )
        log_event(
            logger,
            logging.INFO,
            "constitution.short_circuit.skipped",
            config_path=config_path,
        )
        return True

    def _build_prompt(self, context: PipelineContext, result: OrchestrationResult) -> str:
        prompt = agent_execution._build_agent_prompt(context, result, "constitution")
        placeholder = "{{PRECOMPUTED_REPOSITORY_CONTEXT}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, self._build_precomputed_repository_context(result))
            prompt_output_file = (
                result.repository_path / ".agent_prompts" / "constitution.prompt.md"
            )
            prompt_output_file.write_text(prompt.rstrip() + "\n", encoding="utf-8")
            log_event(
                logger,
                logging.INFO,
                "constitution.precomputed_context.injected",
                prompt_path=prompt_output_file,
            )
        return prompt

    def execute(self, context: PipelineContext) -> None:
        context.step_seq += 1
        step_seq = context.step_seq
        execution_id = context.execution_id
        if self.skip:
            logger.log(
                logging.INFO,
                build_step_log_message(
                    self.name,
                    "SKIPPED",
                    0,
                    execution_id=execution_id,
                    step_seq=step_seq,
                ),
            )
            return

        logger.log(
            logging.INFO,
            build_step_log_message(
                self.name,
                "START",
                execution_id=execution_id,
                step_seq=step_seq,
            ),
        )
        started_at_ns = time.perf_counter_ns()
        try:
            result = context.require_result()
            if self._try_short_circuit(context, result):
                return
            prompt = self._build_prompt(context, result)
            session_id, resume_session = agent_execution._resolve_agent_session(
                context, "constitution"
            )
            raw_output = agent_execution._execute_agent_strategy(
                prompt=prompt,
                cwd=result.repository_path,
                stage_name="constitution",
                session_id=session_id,
                resume_session=resume_session,
            )
            agent_execution._store_agent_output(context, result, "constitution", raw_output)
        except BaseException:
            logger.log(
                logging.INFO,
                build_step_log_message(
                    self.name,
                    "FAILED",
                    runtime._duration_ms_since(started_at_ns),
                    execution_id=execution_id,
                    step_seq=step_seq,
                ),
            )
            raise
        finally:
            logger.log(
                logging.INFO,
                build_step_log_message(
                    self.name,
                    "END",
                    runtime._duration_ms_since(started_at_ns),
                    execution_id=execution_id,
                    step_seq=step_seq,
                ),
            )
