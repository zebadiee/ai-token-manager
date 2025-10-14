#!/usr/bin/env python3
"""
🤖 AUTONOMOUS AI CLI ROTATOR - SELF-MANAGING SYSTEM
Fully autonomous: self-test, self-diagnose, self-update, self-repair, self-heal

Usage: python autonomous_ai_cli.py
System will automatically prepare itself and become user-ready.
"""
import os
import sys
import json
import time
import asyncio
import cmd
import getpass
import subprocess
import webbrowser
import itertools
import re
import threading
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import signal
import platform
import shutil

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from providers import ProviderManager
from secure_env import SecureEnvManager

REQUIRED_PACKAGES = {
    'typer': 'typer>=0.9.0',
    'rich': 'rich>=13.0.0',
    'dotenv': 'python-dotenv>=1.0.0',
    'aiohttp': 'aiohttp>=3.9.0'
}

console = Console()

PIXEL_FRAMES = [
    "■□□□□□□□□□",
    "□■□□□□□□□□",
    "□□■□□□□□□□",
    "□□□■□□□□□□",
    "□□□□■□□□□□",
    "□□□□□■□□□□",
    "□□□□□□■□□□",
    "□□□□□□□■□□",
    "□□□□□□□□■□",
    "□□□□□□□□□■",
]

KNOWN_COMMANDS = {
    "chat",
    "quick",
    "start",
    "talk",
    "smart_chat",
    "hunt_models",
    "providers",
    "models",
    "status",
    "health",
    "repair",
    "setup_providers",
    "token_status",
    "setenv",
    "save",
    "run",
    "create",
    "scaffold",
    "help",
    "exit",
    "quit",
}

SHELL_COMMANDS = {
    "ls",
    "pwd",
    "mkdir",
    "touch",
    "rm",
    "cp",
    "mv",
    "cat",
    "echo",
    "find",
    "tree",
}

INTENT_KEYWORDS = [
    ("setup providers", "setup_providers"),
    ("configure providers", "setup_providers"),
    ("hunt models", "hunt_models"),
    ("refresh models", "hunt_models"),
    ("token status", "token_status"),
    ("usage", "token_status"),
    ("show providers", "providers"),
    ("list providers", "providers"),
    ("show models", "models"),
    ("list models", "models"),
    ("health", "health"),
    ("system status", "status"),
    ("status", "status"),
    ("repair", "repair"),
    ("fix", "repair"),
    ("smart chat", "smart_chat"),
    ("quick chat", "quick"),
    ("ask", "quick"),
    ("build me", "chat"),
    ("build script", "chat"),
    ("generate code", "chat"),
    ("create algorithm", "chat"),
    ("chat", "chat"),
    ("save it", "save"),
    ("save script", "save"),
    ("save output", "save"),
    ("save", "save"),
    ("run script", "run"),
    ("run the script", "run"),
    ("run the", "run"),
    ("run code", "run"),
    ("execute", "run"),
    ("create file", "create"),
    ("create script", "create"),
    ("generate script", "create"),
    ("create", "create"),
    ("scaffold", "scaffold"),
    ("create project", "scaffold"),
    ("new project", "scaffold"),
    ("help", "help"),
    ("exit", "exit"),
    ("quit", "quit"),
]

DEFAULT_STRUCTURE = {
    "src": [],
    "tests": [],
    "docs": [],
    "scripts": [],
}

TEMPLATES = {
    "README.md": (
        "# {PROJECT_NAME}\n\nGenerated on {DATE}\n\n"
        "## Description\n\nA new project scaffolded by Autonomous AI CLI.\n"
    ),
    "requirements.txt": "# Add your Python dependencies here\n",
    "setup.py": (
        "from setuptools import setup, find_packages\n\n"
        "setup(\n"
        "    name='{PROJECT_NAME}',\n"
        "    version='0.1.0',\n"
        "    packages=find_packages(where='src'),\n"
        "    package_dir={'': 'src'},\n"
        "    install_requires=[],\n"
        ")\n"
    ),
    ".gitignore": "__pycache__/\n.env\n.vscode/\n",
}


def scaffold_project(base_path: str, project_name: str) -> Tuple[Path, bool]:
    """Create a new scaffolded project under base_path/project_name.

    Returns a tuple of (project_path, created_flag).
    """

    base = Path(base_path).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    root = base / project_name

    created = False
    if root.exists():
        if not root.is_dir():
            raise FileExistsError(f"Path '{root}' exists and is not a directory.")
    else:
        root.mkdir()
        created = True

    for folder in DEFAULT_STRUCTURE:
        folder_path = root / folder
        try:
            folder_path.mkdir(exist_ok=True)
        except PermissionError as exc:
            raise PermissionError(f"Cannot create folder '{folder_path}': {exc}") from exc

    today = date.today().isoformat()
    for filename, content in TEMPLATES.items():
        file_path = root / filename
        if not file_path.exists():
            try:
                rendered = (
                    content.replace("{PROJECT_NAME}", project_name)
                    .replace("{DATE}", today)
                )
                file_path.write_text(rendered)
            except PermissionError as exc:
                raise PermissionError(f"Cannot write template '{file_path}': {exc}") from exc

    init_file = root / "src" / "__init__.py"
    if not init_file.exists():
        try:
            init_file.write_text("")
        except PermissionError as exc:
            raise PermissionError(f"Cannot write file '{init_file}': {exc}") from exc

    return root.resolve(), created


def map_to_command(user_input: str) -> str:
    text = user_input.strip()
    if not text:
        return text

    # Strip common prompt markers like "(ai-cli)"
    if text.startswith("(ai-cli)"):
        text = text[len("(ai-cli)"):].lstrip()
        if not text:
            return text

    # Remove leading bullet/numbering markers (e.g., "1.", "-", "•")
    text = re.sub(r"^([\d]+[\).]?|[-•])\s+", "", text)

    lower = text.lower()
    tokens = lower.split()
    if tokens:
        first_token = tokens[0]
        if first_token in KNOWN_COMMANDS:
            return text
        # If the first token matches a known command with punctuation (e.g., "run", "create")
        for cmd in KNOWN_COMMANDS:
            if lower.startswith(f"{cmd} ") or lower == cmd:
                remainder = text[len(cmd):].strip()
                return f"{cmd} {remainder}".strip()

    for phrase, command in INTENT_KEYWORDS:
        if phrase in lower:
            idx = lower.find(phrase)
            remainder = text[idx + len(phrase):].strip()
            remainder = re.sub(r"^(for|of|the)\s+", "", remainder, flags=re.IGNORECASE).strip()

            if command in {"chat", "quick", "smart_chat"}:
                message = remainder or text
                return f"{command} {message}".strip()

            if command in {"save", "run", "scaffold", "create"}:
                return f"{command} {remainder}".strip() if remainder else command

            if command in {"models", "providers", "health", "status", "repair", "setup_providers", "token_status"}:
                return command if not remainder else f"{command} {remainder}".strip()

            return f"{command} {remainder}".strip()

    return text


class BootLoader:
    """Run an 8-bit boot animation until context exits."""

    def __init__(self, refresh: float = 0.05):
        self.refresh = max(refresh, 0.02)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._enabled = console.is_terminal

    def _animate(self) -> None:
        frames = itertools.cycle(PIXEL_FRAMES)
        refresh_per_second = max(1, int(1 / self.refresh))
        with Live(
            Panel("", title="Booting AI CLI", border_style="cyan"),
            console=console,
            refresh_per_second=refresh_per_second,
        ) as live:
            while not self._stop_event.is_set():
                frame = next(frames)
                live.update(
                    Panel(
                        f"[bold magenta]{frame}",
                        subtitle="Initializing...",
                        border_style="cyan",
                    )
                )
                if self._stop_event.wait(self.refresh):
                    break

    def __enter__(self):
        if not self._enabled:
            return self
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self._enabled:
            return False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        return False

class AutonomousState(Enum):
    INITIALIZING = "initializing"
    SELF_TESTING = "self_testing"
    DIAGNOSING = "diagnosing"
    UPDATING = "updating"
    REPAIRING = "repairing"
    HEALING = "healing"
    USER_READY = "user_ready"
    ERROR_STATE = "error_state"

@dataclass
class SystemHealth:
    dependencies_ok: bool = False
    config_valid: bool = False
    providers_accessible: bool = False
    storage_writable: bool = False
    last_check: datetime = None
    error_count: int = 0
    repair_count: int = 0
    uptime: float = 0.0

class AutonomousPrompt(cmd.Cmd):
    intro = "Autonomous AI CLI is ready. Type help or ? to list commands."
    prompt = "(ai-cli) "

    def __init__(self, cli: "AutonomousCLI"):
        super().__init__()
        self.cli = cli
        self.last_provider: Optional[str] = None
        self.last_model: Optional[str] = None
        self._last_response: Optional[str] = None

    def precmd(self, line: str) -> str:
        mapped = map_to_command(line)
        return super().precmd(mapped)

    def do_status(self, arg):
        "Check system status."
        state = self.cli.state.value
        print(f"State: {state}")

    def do_health(self, arg):
        "Show latest health snapshot."
        health = self.cli.health
        print(
            json.dumps(
                {
                    "dependencies_ok": health.dependencies_ok,
                    "config_valid": health.config_valid,
                    "providers_accessible": health.providers_accessible,
                    "storage_writable": health.storage_writable,
                    "last_check": health.last_check.isoformat() if health.last_check else None,
                    "error_count": health.error_count,
                    "repair_count": health.repair_count,
                    "uptime": round(health.uptime, 2),
                },
                indent=2,
            )
        )

    def do_repair(self, arg):
        "Trigger simulated repair phase."
        asyncio.run(self.cli._phase_self_repair())

    def do_providers(self, arg):
        "List available AI providers."
        manager = self.cli.provider_manager
        report = manager.usage_report()
        for entry in report:
            status = "✅" if entry["active"] else "⚪️"
            meta = manager.catalog[entry["key"]]
            default_tag = " (last used)" if entry["key"] == self.last_provider else ""
            print(
                f"{status} {entry['provider']} ({entry['key']}): "
                f"{entry['requests']}/{entry['limit']} requests used today"
            )
            models_preview = ", ".join(meta.free_models[:3]) if meta.free_models else "No models"
            print(
                f"  Models: {models_preview}{'...' if len(meta.free_models) > 3 else ''}"
                f"{default_tag}"
            )
            if not entry["active"]:
                print(f"  Setup: use setenv {meta.env_var} or setup_providers")

    def do_models(self, arg):
        "List models for a provider: models <provider>."
        provider_name = arg.strip()
        if not provider_name:
            print("Usage: models <provider>")
            return

        meta = self.cli.provider_manager.catalog.get(provider_name)
        if not meta:
            print(f"❌ Provider '{provider_name}' not found")
            return

        print(f"📋 {meta.display_name} Models (free tier):")
        for model in meta.free_models:
            print(f"  • {model}")

    def do_chat(self, arg):
        "Chat with AI. Usage:\n  chat <message>\n  chat <provider> <message>\n  chat <provider> <model> <message>"
        arg = arg.strip()
        if not arg:
            print("Usage: chat <message> | chat <provider> <message> | chat <provider> <model> <message>")
            return

        parts = arg.split(" ", 2)
        provider_catalog = self.cli.provider_manager.catalog

        if parts[0] in provider_catalog and len(parts) == 3:
            provider_key, model, message = parts
            self._run_chat(provider_key, model, message)
        elif parts[0] in provider_catalog and len(parts) == 2:
            provider_key, message = parts
            model = self.cli.provider_manager.default_model_for(provider_key)
            if not model:
                print(f"No default model available for {provider_key}. Specify a model explicitly.")
                return
            self._run_chat(provider_key, model, message)
        else:
            message = arg
            self._chat_with_failover(message)

    def do_quick(self, arg):
        "Quick chat using best available provider: quick <message>."
        message = arg.strip()
        if not message:
            print("Usage: quick <message>")
            return

        sequence = self.cli.provider_manager.default_failover_sequence()
        if not sequence:
            print("No providers available. Run 'setup_providers' to add API keys.")
            return
        self._chat_with_failover(message, sequence)

    def do_start(self, arg):
        "Alias for quick <message>."
        self.do_quick(arg)

    def do_talk(self, arg):
        "Alias for quick <message>."
        self.do_quick(arg)

    def do_smart_chat(self, arg):
        "Smart chat with automatic failover: smart_chat <message>."
        self.do_quick(arg)

    def do_hunt_models(self, arg):
        "Reload provider configuration and display availability."
        self.cli.provider_manager.reload()
        print("🔁 Provider catalog refreshed.")
        self.do_providers("")

    def default(self, line: str):
        message = line.strip()
        if not message:
            return
        if self._maybe_run_shell(message):
            return
        self.do_quick(message)

    # ------------------------------------------------------------------
    # Helpers

    def _resolve_target_path(self, raw_path: str) -> Path:
        """Resolve a user-provided file path relative to the active project if set."""
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        if self.cli.active_project:
            return (self.cli.active_project / path).resolve()
        return (Path.cwd() / path).resolve()

    def _maybe_run_shell(self, command: str) -> bool:
        try:
            import shlex
        except ImportError:
            shlex = None

        tokens = []
        if shlex:
            try:
                tokens = shlex.split(command)
            except ValueError:
                pass
        if not tokens:
            tokens = command.split()
        if not tokens:
            return False

        if tokens[0] not in SHELL_COMMANDS:
            return False

        try:
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                capture_output=True,
                cwd=self.cli.active_project or Path.cwd(),
            )
        except Exception as exc:
            print(f"❌ Shell command failed: {exc}")
            return True

        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0 and not result.stderr:
            print(f"⚠️ Shell command exited with code {result.returncode}")
        return True

    def do_setenv(self, arg):
        "Set API key securely: setenv <provider|ENV_VAR>."
        target = arg.strip()
        if not target:
            print("Usage: setenv <provider|ENV_VAR>")
            return

        env_key = self.cli.provider_manager.env_var_for(target)
        if not env_key:
            env_key = target

        secret = self._collect_secret(env_key)
        if secret is None:
            return

        self.cli.env_manager.write_secret(env_key, secret)
        self.cli.provider_manager.reload()
        print(f"Stored secret for {env_key} in {self.cli.env_manager.path_str()}.")

    def do_save(self, arg):
        "Save last chat response to a file: save <filename.py>"
        if not self._last_response:
            print("❌ No chat response available to save. Run a chat command first.")
            return

        filename = arg.strip()
        if not filename:
            print("Usage: save <filename>")
            return

        target_path = self._resolve_target_path(filename)
        if not target_path.suffix:
            target_path = target_path.with_suffix(".py")

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(self._last_response)
        except OSError as exc:
            print(f"❌ Failed to save response: {exc}")
            return

        print(f"✅ Chat response saved to {target_path}")

    def do_run(self, arg):
        "Run a Python script saved from chat output: run <filename.py> [-- <args>]"
        text = arg.strip()
        if not text:
            print("Usage: run <filename.py> [-- <args>]")
            return

        parts = text.split(" -- ", 1)
        filename = parts[0].strip()
        extra_args = parts[1].strip().split() if len(parts) == 2 else []

        path = self._resolve_target_path(filename)
        if not path.suffix:
            path = path.with_suffix(".py")

        if not path.exists():
            print(f"❌ File '{path.name}' not found. Use `save <filename>` first.")
            return

        cmd_args = [sys.executable or "python3", str(path), *extra_args]
        print(f"▶️ Running {' '.join(cmd_args)}")
        try:
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                check=False,
            )
        except KeyboardInterrupt:
            print("⛔ Script interrupted by user.")
            return
        except OSError as exc:
            print(f"❌ Failed to run script: {exc}")
            return

        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0 and not result.stderr:
            print(f"⚠️ Script exited with code {result.returncode}")

    def do_create(self, arg):
        """Generate code from a prompt and save it to a file: create <filename> <prompt>"""
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: create <filename> <prompt>")
            print("Example: create src/core.py build me a function to validate JSON")
            return

        filename_str, prompt = parts
        target_path = self._resolve_target_path(filename_str)
        generation_prompt = (
            "Generate only runnable Python code (no markdown fences or explanations) for: "
            f"{prompt}"
        )

        content, provider_key, model = self._generate_code_response(
            generation_prompt,
            verbose=True,
        )

        if not content:
            print("❌ Generation failed. Check provider status and logs.")
            return

        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            if lines and lines[0].startswith("python"):
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(cleaned)
        except Exception as exc:
            print(f"❌ Error saving file: {exc}")
            return

        self._last_response = cleaned
        provider_label = provider_key or "unknown provider"
        model_label = model or "unknown model"
        print(f"✅ Code generated by {provider_label} ({model_label}) and saved to {target_path.resolve()}")

    def do_scaffold(self, arg):
        "Scaffold a new project directory: scaffold <base_path> <project_name>"
        parts = arg.split()
        if not parts:
            print("Usage: scaffold <base_path> <project_name> | scaffold <project_name>")
            return

        if len(parts) == 1:
            base_path = Path.cwd()
            project_name = parts[0]
        else:
            base_path = Path(parts[0]).expanduser()
            project_name = parts[1]

        try:
            root, created = scaffold_project(str(base_path), project_name)
        except FileExistsError as exc:
            print(f"❌ {exc}")
            return
        except Exception as exc:
            print(f"❌ Unable to scaffold project: {exc}")
            return

        self.cli.active_project = root
        if created:
            print(f"✅ Project '{project_name}' scaffolded at {root}")
        else:
            print(f"ℹ️ Project '{project_name}' already exists. Using existing scaffold at {root}")
        print("   You can now generate code and save files into this structure.")

    def do_setup_providers(self, arg):
        "Guided provider registration and key capture."
        manager = self.cli.provider_manager
        configured_any = False
        for meta in manager.catalog.values():
            print(f"\n=== {meta.display_name} ({meta.identifier}) ===")
            print(f"Free models: {', '.join(meta.free_models)}")
            usage = manager.get_usage(meta.identifier)
            print(f"Daily limit: {meta.daily_limit} requests | Used today: {usage.requests}")

            if meta.identifier in manager.providers:
                print("Already configured. Skipping.")
                continue

            choice = input("Configure this provider now? [y/N]: ").strip().lower()
            if choice != "y":
                continue

            open_choice = input("Open signup page in browser? [y/N]: ").strip().lower()
            if open_choice == "y":
                webbrowser.open(meta.signup_url)

            secret = self._collect_secret(meta.env_var)
            if secret is None:
                print("Skipped.")
                continue

            self.cli.env_manager.write_secret(meta.env_var, secret)
            configured_any = True

        if configured_any:
            manager.reload()
            print("Provider credentials captured. Current status:")
            self.do_providers("")
        else:
            print("No providers configured during this session.")

    def do_token_status(self, arg):
        "Show daily usage statistics for each provider."
        report = self.cli.provider_manager.usage_report()
        for entry in report:
            status = "✅" if entry["active"] else "⚪️"
            print(
                f"{status} {entry['provider']}: {entry['requests']}/{entry['limit']} requests | "
                f"{entry['tokens']} tokens (today {entry['date']})"
            )

    def do_exit(self, arg):
        "Exit the CLI."
        print("Goodbye!")
        return True

    def do_quit(self, arg):
        "Exit the CLI."
        return self.do_exit(arg)

    # Helpers -----------------------------------------------------------------
    def _collect_secret(self, env_key: str) -> Optional[str]:
        secret = getpass.getpass(f"Enter value for {env_key}: ")
        confirm = getpass.getpass("Re-enter to confirm: ")

        if not secret:
            print("No value entered. Aborted.")
            return None

        if secret != confirm:
            print("Values did not match. Aborted.")
            return None

        return secret

    def _run_chat(self, provider_key: str, model: str, message: str) -> None:
        if provider_key not in self.cli.provider_manager.providers:
            print(f"❌ Provider '{provider_key}' not configured")
            return

        self._chat_with_failover(message, [(provider_key, model)])

    def _chat_with_failover(self, message: str, sequence: Optional[List[Tuple[str, str]]] = None) -> bool:
        content, provider_key, model = self._generate_code_response(message, sequence, verbose=True)
        if content:
            print(f"🤖 {content}")
            self._last_response = content
            return True
        return False

    def _generate_code_response(
        self,
        message: str,
        sequence: Optional[List[Tuple[str, str]]] = None,
        verbose: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        sequence = sequence or self.cli.provider_manager.default_failover_sequence()
        if not sequence:
            if verbose:
                print("No providers available. Run 'setup_providers' to add API keys.")
            return None, None, None

        any_attempted = False
        last_error = None
        for provider_key, model in sequence:
            if provider_key not in self.cli.provider_manager.providers:
                continue
            if not self.cli.provider_manager.has_quota(provider_key):
                if verbose:
                    print(f"⏳ {provider_key} has reached its daily limit. Skipping.")
                continue

            if verbose:
                print(f"🎯 Using {provider_key} :: {model}")
            success, content, error = self._attempt_chat(provider_key, model, message)
            if success and content:
                self.last_provider, self.last_model = provider_key, model
                return content, provider_key, model

            any_attempted = True
            last_error = error
            if verbose and error:
                print(f"⚠️ {provider_key}/{model}: {error}. Trying next...")

        if verbose:
            if any_attempted:
                detail = f" Last error: {last_error}" if last_error else ""
                print(f"❌ All providers failed. Try again later or update API keys.{detail}")
            else:
                print("❌ All providers unavailable. Configure API keys or reset quotas.")
        return None, None, None

    def _attempt_chat(self, provider_key: str, model: str, message: str) -> Tuple[bool, Optional[str], Optional[str]]:
        payload = [{"role": "user", "content": message}]
        try:
            response = asyncio.run(
                self.cli.provider_manager.chat_completion(provider_key, model, payload)
            )
        except Exception as exc:
            return False, None, str(exc)

        if isinstance(response, dict):
            error = response.get("error")
            if error:
                if isinstance(error, dict):
                    msg = error.get("message") or error.get("error") or json.dumps(error)
                else:
                    msg = str(error)
                return False, None, msg

            choices = response.get("choices")
            if choices:
                content = choices[0].get("message", {}).get("content")
                if content:
                    return True, content, None
                return False, None, "Empty response"

        return False, None, str(response)

class AutonomousCLI:
    def __init__(self):
        self.state = AutonomousState.INITIALIZING
        self.health = SystemHealth()
        self.start_time = time.time()
        self.config_dir = Path.home() / ".ai_cli_autonomous"
        self.log_file = self.config_dir / "autonomous.log"
        self.health_file = self.config_dir / "health.json"
        self.project_root = Path(__file__).resolve().parent
        self.env_path = self.project_root / ".env"
        self.provider_usage_file = self.config_dir / "provider_usage.json"
        self.env_manager = SecureEnvManager(self.env_path)
        self.provider_manager = ProviderManager(self.env_path, self.provider_usage_file)
        self.active_project: Optional[Path] = None
        self.config_dir.mkdir(exist_ok=True)
        self._setup_logging()
        self.log("🤖 Autonomous AI CLI System starting...")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        print(entry)
        try:
            with open(self.log_file, "a") as f:
                f.write(entry + "\n")
        except:
            pass

    def _setup_logging(self):
        if not self.log_file.exists():
            with open(self.log_file, "w") as f:
                f.write(f"# Log started: {datetime.now()}\n\n")

    def _graceful_shutdown(self):
        self.log("🛑 Graceful shutdown...", "INFO")
        self.save_health_state()
        sys.exit(0)

    async def autonomous_startup(self):
        try:
            with BootLoader():
                self.log("🚀 Initializing...")
                await self._phase_self_initialize()
                await self._phase_self_test()
                await self._phase_self_diagnose()
                await self._phase_self_update()
                await self._phase_self_repair()
                await self._phase_self_heal()
            await self._phase_user_ready()
            await self._start_continuous_monitoring()
            self.log("🧭 Interactive prompt available. Type 'help' for commands.")
        except Exception as e:
            self.log(f"❌ Startup failed: {e}", "ERROR")
            self.state = AutonomousState.ERROR_STATE

    async def _phase_self_initialize(self):
        self.state = AutonomousState.INITIALIZING
        self.log("🔧 Phase 1: Initialize")
        await self._install_deps()
        await self._mk_dirs()
        await self._init_config()
        self.log("✅ Initialization complete")

    async def _install_deps(self):
        missing = []
        for pkg, req in REQUIRED_PACKAGES.items():
            try:
                __import__(pkg)
                self.log(f"✅ {pkg} OK")
            except ImportError:
                missing.append(req)
        if missing:
            self.log(f"Installing missing dependencies: {missing}")
            for req in missing:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", req],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    self.log(f"Successfully installed {req}")
                except subprocess.CalledProcessError as e:
                    self.log(f"Failed to install {req}. Error: {e.stderr}", "ERROR")
                    self.health.dependencies_ok = False
                    return
        self.health.dependencies_ok = True
        self.log("✅ Dependencies handled")

    async def _mk_dirs(self):
        for sub in ["providers", "backups", "logs", "cache"]:
            d = self.config_dir / sub
            d.mkdir(exist_ok=True)
            self.log(f"📁 {d}")

    async def _init_config(self):
        cfg = {
            "version":"2.0.0","autonomous":True,
            "created":datetime.now().isoformat(),
            "system": {
                "platform":platform.system(),
                "python":platform.python_version()
            }
        }
        cf = self.config_dir / "config.json"
        with open(cf,"w") as f: json.dump(cfg,f,indent=2)
        if os.name!="nt": os.chmod(cf,0o600)
        self.log("⚙️ Config written")

    async def _phase_self_test(self):
        self.state = AutonomousState.SELF_TESTING
        self.log("🧪 Phase 2: Self-Test")
        results = []
        results.append(await self._test_pyenv())
        results.append(await self._test_fs())
        results.append(await self._test_net())
        results.append(await self._test_cfg())
        provider_ready = await self._test_providers()
        results.append(provider_ready)
        self.health.dependencies_ok = results[0]
        self.health.storage_writable = results[1]
        self.health.providers_accessible = provider_ready
        self.health.config_valid = results[3]
        passed = sum(results)
        self.log(f"🧪 Tests passed {passed}/{len(results)}")

    async def _test_pyenv(self):
        return sys.version_info >= (3,7)
    async def _test_fs(self):
        try:
            tmp = self.config_dir/"tmp"; tmp.write_text("x"); tmp.unlink(); return True
        except: return False
    async def _test_net(self):
        hosts = [("8.8.8.8", 53), ("1.1.1.1", 53), ("google.com", 443)]
        for host, port in hosts:
            try:
                import socket
                socket.create_connection((host, port), 5)
                self.log(f"✅ Network connection to {host}:{port} successful.")
                return True
            except OSError:
                self.log(f"🟡 Failed to connect to {host}:{port}.")
        self.log("❌ Network connection failed.", "ERROR")
        return False
    async def _test_cfg(self):
        return (self.config_dir/"config.json").exists()

    async def _test_providers(self):
        ready = bool(self.provider_manager.providers)
        if ready:
            self.log("✅ Provider credentials detected.")
        else:
            self.log("ℹ️ No provider credentials found yet.")
        return ready

    async def _phase_self_diagnose(self):
        self.state = AutonomousState.DIAGNOSING
        self.log("🔍 Phase 3: Diagnose")
        issues=[]
        if not self.health.dependencies_ok: issues.append("deps")
        if not self.health.storage_writable: issues.append("fs")
        if not self.health.config_valid: issues.append("cfg")
        if not self.health.providers_accessible: issues.append("providers")
        self.log(f"Issues: {issues}")
        return issues

    async def _phase_self_update(self):
        self.state = AutonomousState.UPDATING
        self.log("🔄 Phase 4: Update – Checking for new version...")
        await asyncio.sleep(1.5)  # Simulate network check
        self.log("Downloading update...")
        await asyncio.sleep(2.0)  # Simulate download
        self.log("✅ Update complete (simulated).")

    async def _phase_self_repair(self):
        self.state = AutonomousState.REPAIRING
        self.log("🔧 Phase 5: Repair – Diagnosing system...")
        await asyncio.sleep(1.0)  # Simulate diagnosis
        self.log("Re-applying config and patching...")
        await asyncio.sleep(1.0)  # Simulate repair
        self.log("✅ Repair done (simulated).")

    async def _phase_self_heal(self):
        self.state = AutonomousState.HEALING
        self.log("💚 Phase 6: Heal")
        self.health.error_count=0
        self.health.last_check=datetime.now()
        self.log("✅ Heal complete")

    async def _phase_user_ready(self):
        self.state = AutonomousState.USER_READY
        self.log("🎯 Phase 7: User-Ready")
        ui = self.config_dir/"user_interface.py"
        (self.config_dir/"README.md").write_text("# Autonomous AI CLI Rotator\nSystem Ready!")
        ui.write_text("""#!/usr/bin/env python3
import typer
from rich.console import Console
app=typer.Typer()
console=Console()
@app.command()
def status():
    console.print("System Operational")
if __name__=="__main__":app()""")
        self.health.uptime=time.time()-self.start_time
        self.save_health_state()
        self.log("✅ Ready")

    async def _start_continuous_monitoring(self):
        self.log("👁️ Monitoring – Starting health checks...")
        for i in range(5):  # Simulated finite loop; promote to while True for production
            await self._health_check()
            self.log(f"Health check iteration {i+1} complete.")
            await asyncio.sleep(10)
        self.log("👁️ Monitoring – Loop ended.")

    async def _health_check(self):
        self.log("🩺 Running health check...")
        self.provider_manager.reload()
        dependency_ok = await self._test_pyenv()
        storage_ok = await self._test_fs()
        network_ok = await self._test_net()
        config_ok = await self._test_cfg()
        providers_ok = bool(self.provider_manager.available_providers())

        self.health.dependencies_ok = dependency_ok
        self.health.storage_writable = storage_ok
        self.health.providers_accessible = providers_ok
        self.health.config_valid = config_ok
        self.health.last_check = datetime.now()
        self.health.uptime = time.time() - self.start_time

        checks = {
            "dependencies": dependency_ok,
            "storage": storage_ok,
            "network": network_ok,
            "providers": providers_ok,
            "config": config_ok,
        }
        failed = [name for name, status in checks.items() if not status]
        if failed:
            self.health.error_count += 1
            self.log(f"⚠️ Issues detected: {', '.join(failed)}", "WARNING")
        else:
            self.log("✅ Health check passed.")

        self.save_health_state()

    def save_health_state(self):
        health_data = asdict(self.health)
        if health_data.get('last_check') is not None:
            health_data['last_check'] = health_data['last_check'].isoformat()
        
        data = {
            "state": self.state.value,
            "health": health_data,
            "time": datetime.now().isoformat()
        }
        with open(self.health_file, "w") as f:
            json.dump(data, f, indent=2)

async def main():
    cli = AutonomousCLI()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, cli._graceful_shutdown)
    await cli.autonomous_startup()
    return cli

if __name__=="__main__":
    cli_instance = None
    try:
        cli_instance = asyncio.run(main())
    except KeyboardInterrupt:
        pass

    if cli_instance and cli_instance.state != AutonomousState.ERROR_STATE:
        AutonomousPrompt(cli_instance).cmdloop()
