#!/usr/bin/env python3
"""
🤖 AUTONOMOUS AI CLI ROTATOR - SELF-MANAGING SYSTEM
Fully autonomous: self-test, self-diagnose, self-update, self-repair, self-heal
from model_loader import load_registry, get_default_model, verify_models

registry = load_registry()
if registry:
    default_model = get_default_model(registry)
    print(f"🚀 Default model set to: {default_model}")
    verify_models(registry)
else:
    print("⚠️ No registry detected — running without model catalog.")

Usage: python autonomous_ai_cli.py
System will automatically prepare itself and become user-ready.
"""
import os
import sys
import json
import io
import time
import asyncio
import cmd
import getpass
import subprocess
import webbrowser
import itertools
import re
import shlex
import threading
import textwrap
from pathlib import Path
from datetime import datetime, date
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import contextlib
from enum import Enum
import signal
import platform
import shutil

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:  # pragma: no cover
    Console = None
    Live = None
    Panel = None
    Text = None
    RICH_AVAILABLE = False

from providers import ProviderManager
from secure_env import SecureEnvManager

REQUIRED_PACKAGES = {
    'typer': 'typer>=0.9.0',
    'rich': 'rich>=13.0.0',
    'dotenv': 'python-dotenv>=1.0.0',
    'aiohttp': 'aiohttp>=3.9.0',
    'pyyaml': 'PyYAML>=6.0'
}

class SimpleConsole:
    def __init__(self):
        self.is_terminal = sys.stdout.isatty()

    def print(self, *values, **kwargs):
        print(*values, **kwargs)


console = Console() if RICH_AVAILABLE else SimpleConsole()

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
    "read",
    "diff",
    "git_status",
    "test",
    "sync_models",
    "pulse",
    "codex",
    "api",
    "guide",
    "settings",
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
    "nslookup",
    "curl",
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
    ("read file", "read"),
    ("view file", "read"),
    ("show file", "read"),
    ("diff", "diff"),
    ("git status", "git_status"),
    ("run tests", "test"),
    ("tests", "test"),
    ("sync models", "sync_models"),
    ("pulse", "pulse"),
    ("plan", "codex"),
    ("codex", "codex"),
    ("autonomous", "codex"),
    ("api", "api"),
    ("guide", "guide"),
    ("settings", "settings"),
    ("configure", "settings"),
    ("preferences", "settings"),
    ("disable openrouter", "settings"),
    ("only local", "settings"),
    ("turn off cloud", "settings"),
    ("get started", "guide"),
    ("how do i", "guide"),
    ("what can you do", "guide"),
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
        if RICH_AVAILABLE:
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
        else:
            while not self._stop_event.is_set():
                frame = next(frames)
                print(f"[Boot] {frame}", end="\r", flush=True)
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
        if not RICH_AVAILABLE:
            print()
        return False


class CodexAPIServer:
    def __init__(self, prompt: "AutonomousPrompt", host: str = "127.0.0.1", port: int = 8081):
        try:
            from aiohttp import web
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("aiohttp is required for API mode. Install with 'pip install aiohttp'.") from exc

        self.prompt = prompt
        self.host = host
        self.port = port
        self.web = web
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._shutdown = asyncio.Event()
        self.ready = asyncio.Event()

        self.app.add_routes(
            [
                web.get("/health", self._handle_health),
                web.get("/providers", self._handle_providers),
                web.post("/tools/{name}", self._handle_tool),
                web.post("/codex", self._handle_codex),
                web.post("/sync-models", self._handle_sync_models),
            ]
        )

    async def start(self):
        self.runner = self.web.AppRunner(self.app)
        await self.runner.setup()
        self.site = self.web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        self.ready.set()
        await self._shutdown.wait()
        await self.runner.cleanup()

    async def stop(self):
        self._shutdown.set()

    async def _handle_health(self, request):
        data = {
            "state": self.prompt.cli.state.value,
            "uptime": self.prompt.cli.health.uptime,
            "last_check": self.prompt.cli.health.last_check.isoformat() if self.prompt.cli.health.last_check else None,
        }
        return self.web.json_response(data)

    async def _handle_providers(self, request):
        report = self.prompt.cli.provider_manager.usage_report()
        return self.web.json_response(report)

    async def _handle_tool(self, request):
        payload = await request.json()
        args = payload.get("arguments", "")
        name = request.match_info["name"]
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            result = self.prompt._invoke_tool(name, args)
        response = {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
        }
        status = 200 if result.success else 400
        return self.web.json_response(response, status=status)

    async def _handle_codex(self, request):
        payload = await request.json()
        goal = payload.get("goal")
        if not goal:
            return self.web.json_response({"error": "Missing goal"}, status=400)
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            result = self.prompt._codex_execute(goal, verbose=False)
        response = {
            "success": result["success"],
            "message": result.get("message"),
            "data": result.get("data"),
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
        }
        status = 200 if result["success"] else 400
        return self.web.json_response(response, status=status)

    async def _handle_sync_models(self, request):
        try:
            summary = await self.prompt.cli.provider_manager.sync_free_models()
        except RuntimeError as exc:
            return self.web.json_response({"error": str(exc)}, status=400)
        return self.web.json_response(summary)
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


@dataclass
class ToolResult:
    success: bool
    message: str = ""
    data: Optional[Dict] = None
    replan: bool = False


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[["AutonomousPrompt", str], ToolResult]
    auto_confirm: bool = True


@dataclass
class CodexStep:
    description: str
    tool: str
    arguments: str


@dataclass
class CodexPlan:
    goal: str
    steps: List[CodexStep]
    rationale: str = ""

class AutonomousPrompt(cmd.Cmd):
    intro = "Autonomous AI CLI is ready. Type help or ? to list commands."
    prompt = "(ai-cli) "

    def __init__(self, cli: "AutonomousCLI"):
        super().__init__()
        self.cli = cli
        self.last_provider: Optional[str] = None
        self.last_model: Optional[str] = None
        self._last_response: Optional[str] = None
        self.tools: Dict[str, ToolSpec] = {}
        force_immersive = os.getenv("AI_CLI_FORCE_IMMERSIVE")
        if force_immersive is not None:
            self.immersive_mode = force_immersive.lower() in {"1", "true", "yes", "on"}
        else:
            self.immersive_mode = bool(RICH_AVAILABLE and getattr(console, "is_terminal", True))
        self.chat_history: List[Tuple[str, str]] = []
        self._immersive_intro_shown = False
        self._readline = None

        self._register_tool(
            ToolSpec(
                name="create",
                description="Generate code from a prompt and save it to a file.",
                handler=AutonomousPrompt._tool_create,
            )
        )
        self._register_tool(
            ToolSpec(
                name="run",
                description="Execute a Python script with optional arguments.",
                handler=AutonomousPrompt._tool_run,
            )
        )
        self._register_tool(
            ToolSpec(
                name="save",
                description="Persist the last chat response to disk.",
                handler=AutonomousPrompt._tool_save,
            )
        )
        self._register_tool(
            ToolSpec(
                name="scaffold",
                description="Create or reuse a project scaffold.",
                handler=AutonomousPrompt._tool_scaffold,
            )
        )
        self._register_tool(
            ToolSpec(
                name="read",
                description="Display the contents of a file.",
                handler=AutonomousPrompt._tool_read,
            )
        )
        self._register_tool(
            ToolSpec(
                name="diff",
                description="Show git diff (optionally for a path).",
                handler=AutonomousPrompt._tool_diff,
            )
        )
        self._register_tool(
            ToolSpec(
                name="git_status",
                description="Show concise git status.",
                handler=AutonomousPrompt._tool_git_status,
            )
        )
        self._register_tool(
            ToolSpec(
                name="test",
                description="Run the project's test command (default pytest).",
                handler=AutonomousPrompt._tool_test,
            )
        )
        self._register_tool(
            ToolSpec(
                name="sync_models",
                description="Fetch latest free model lists from configured providers.",
                handler=AutonomousPrompt._tool_sync_models,
            )
        )
        self._register_tool(
            ToolSpec(
                name="pulse",
                description="Check provider connectivity and update status LEDs.",
                handler=AutonomousPrompt._tool_pulse,
            )
        )
        self._update_prompt()

    def _ensure_immersive_intro(self) -> None:
        if not self.immersive_mode or self._immersive_intro_shown:
            return

        console.print(
            Panel(
                "Type `help` to explore commands or start chatting right away.",
                title="💬 Immersive Chat",
                subtitle="Autonomous AI CLI",
                border_style="purple",
                padding=(1, 2),
            )
        )
        self._immersive_intro_shown = True

    def _update_prompt(self) -> None:
        if self.immersive_mode:
            indicator = self._provider_prompt().strip()
            if indicator:
                self.prompt = f"{indicator}\n╭─ You\n╰─ "
            else:
                self.prompt = "╭─ You\n╰─ "
        else:
            self.prompt = f"{self._provider_prompt()}(ai-cli) "

    def _configure_history(self) -> None:
        if not self.use_rawinput or not self.immersive_mode:
            return
        try:
            import readline  # type: ignore
        except ImportError:
            return

        self._readline = readline
        try:
            readline.set_history_length(1000)
        except Exception:
            pass

    def _build_message_panel(
        self,
        title: str,
        message: str,
        border_style: str,
        subtitle: Optional[str] = None,
    ):
        if not (RICH_AVAILABLE and Panel and Text):
            header = f"{title}: "
            return f"{header}{message}"

        trimmed = message.rstrip()
        if trimmed:
            text = Text(trimmed)
        else:
            text = Text("…", style="dim")

        return Panel.fit(
            text,
            title=title,
            subtitle=subtitle,
            border_style=border_style,
            padding=(1, 2),
        )

    def _render_user_message(self, message: str) -> None:
        self.chat_history.append(("user", message))
        if not self.immersive_mode:
            print(f"🙂 You: {message}")
            return
        console.print(self._build_message_panel("You", message, "cyan"))

    def _render_ai_message(
        self,
        message: str,
        provider_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.chat_history.append(("assistant", message))
        if not self.immersive_mode:
            print(f"🤖 {message}")
            return

        subtitle = None
        if provider_key and model:
            subtitle = f"{provider_key} · {model}"
        elif provider_key:
            subtitle = provider_key
        console.print(self._build_message_panel("AI", message, "green", subtitle=subtitle))

    def _render_system_message(self, message: str, level: str = "info") -> None:
        if not message:
            return

        if not self.immersive_mode:
            print(message)
            return

        palette = {
            "info": ("System", "cyan"),
            "warn": ("Notice", "yellow"),
            "error": ("Alert", "red"),
        }
        title, border = palette.get(level, ("System", "cyan"))
        console.print(self._build_message_panel(title, message, border))

    def preloop(self) -> None:
        if self.immersive_mode:
            self._configure_history()
            self._ensure_immersive_intro()
        self._update_prompt()
        super().preloop()

    def precmd(self, line: str) -> str:
        if self.immersive_mode and not self._immersive_intro_shown:
            self._ensure_immersive_intro()
        if self.immersive_mode and self._readline and line.strip():
            try:
                length = self._readline.get_current_history_length()
                if length == 0 or self._readline.get_history_item(length) != line:
                    self._readline.add_history(line)
            except Exception:
                pass
        mapped = map_to_command(line)
        return mapped

    def postcmd(self, stop: bool, line: str) -> bool:
        self._update_prompt()
        return stop

    def emptyline(self):
        return

    # ------------------------------------------------------------------
    # Tool registration helpers

    def _register_tool(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def _invoke_tool(self, name: str, arg: str) -> ToolResult:
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(False, f"Unknown tool: {name}")
        result = tool.handler(self, arg)
        if result.message:
            print(result.message)
        return result

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
        status_map = manager.status
        allowed_env = os.getenv("AI_CLI_ALLOWED_PROVIDERS")
        if RICH_AVAILABLE:
            from rich.table import Table
            table = Table(title="Providers (Live Status)")
            table.add_column("Provider", style="cyan")
            table.add_column("Key", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Reason", style="yellow")
            table.add_column("Usage", justify="right")
            for entry in report:
                key = entry["key"]
                state = status_map.get(key, entry.get("status", "unknown"))
                reason = ""
                if "filtered" in state:
                    reason = "filtered"
                elif not entry["active"]:
                    reason = "not configured"
                usage = f"{entry['requests']}/{entry['limit']}"
                table.add_row(entry["provider"], key, state, reason, usage)
            if allowed_env:
                table.add_row("Filter", "-", allowed_env, "active", "")
            console.print(table)
        else:
            for entry in report:
                key = entry["key"]
                state = status_map.get(key, entry.get("status", "unknown"))
                reason = ""
                if "filtered" in state:
                    reason = " (filtered)"
                elif not entry["active"]:
                    reason = " (not configured)"
                print(f"- {entry['provider']} ({key}): {state}{reason}")
            if allowed_env:
                print(f"Filter active: {allowed_env}")

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
            self._render_system_message(
                "Usage: chat <message> | chat <provider> <message> | chat <provider> <model> <message>",
                level="warn",
            )
            return

        parts = arg.split(" ", 2)
        provider_catalog = self.cli.provider_manager.catalog

        if parts[0] in provider_catalog and len(parts) == 3:
            provider_key, model, message = parts
            self._render_user_message(message)
            self._run_chat(provider_key, model, message)
        elif parts[0] in provider_catalog and len(parts) == 2:
            provider_key, message = parts
            model = self.cli.provider_manager.default_model_for(provider_key)
            if not model:
                self._render_system_message(
                    f"No default model available for {provider_key}. Specify a model explicitly.",
                    level="warn",
                )
                return
            self._render_user_message(message)
            self._run_chat(provider_key, model, message)
        else:
            message = arg
            self._render_user_message(message)
            self._chat_with_failover(message)

    def do_quick(self, arg):
        "Quick chat using best available provider: quick <message>."
        message = arg.strip()
        if not message:
            self._render_system_message("Usage: quick <message>", level="warn")
            return

        sequence = self.cli.provider_manager.default_failover_sequence()
        if not sequence:
            self._render_system_message(
                "No providers available. Run 'setup_providers' to add API keys.", level="warn"
            )
            return
        self._render_user_message(message)
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

    def do_guide(self, arg):
        "Show a quick-start roadmap for using the autonomous CLI."
        if arg and arg.strip().lower() in {"settings", "config", "setup"}:
            self.do_settings("")
            return
        guide = textwrap.dedent(
            """
            🚀 **Autonomous AI CLI Builder’s Guide**

            1. **Connect providers (optional)**
               • `providers` — see who is active
               • `setup_providers` — launch guided key capture
               • `setenv PROVIDER_API_KEY sk-...` — paste keys inline
               • Offline only? Run `./scripts/failover_to_local.py` to lock the local Ollama models in.
               • Want to ignore global cloud keys? Add `AI_CLI_ALLOWED_PROVIDERS=local` to `.env` before launch.

            2. **Ideate and draft**
               • `quick <idea>` — fast chat on the best available model
               • `chat <provider> <model> <prompt>` — pin a specific stack when you need it
               • `smart_chat <brief>` — same as quick, but emphasises richer responses.

            3. **Plan before you build**
               • `codex <goal>` — generates a multi-step build plan you can iterate on
               • `guide` — you are here; re-run anytime for the playbook.

            4. **Create and run assets**
               • `create <path> <<<PROMPT>>>` — draft code/documents into files
               • `scaffold <project-name>` — spin up a project skeleton under `src/`
               • `run <script.py>` / `test` — execute or validate what you just generated.

            5. **Review and ship**
               • `read <file>` / `diff [path]` / `git_status` — inspect what changed
               • `save` — persist the last assistant response to disk
               • `pulse` / `sync_models` — refresh provider health & free-model catalogs.

            Need more? `help <command>` dives deeper, and the docs in `docs/offline_llm_deployment.md`
            cover the full SSD-based offline workflow.
            """
        ).strip()
        print(guide)

    def do_settings(self, arg):
        "Open interactive settings menu (live updates)."
        if not RICH_AVAILABLE:
            print("Rich is required for the interactive settings menu. Install 'rich' or edit .env manually.")
            return

        from rich.console import Console
        from rich.table import Table
        from rich.prompt import Prompt, Confirm

        console = Console()

        def current_providers() -> str:
            return self.cli.provider_filter_mode()

        def current_local_enabled() -> bool:
            return os.getenv("AI_CLI_LOCAL_ENABLED", "0").strip().lower() not in {"0", "false", "off", "no"}

        def current_health() -> bool:
            return self.cli.health_monitoring

        def current_bootstrap() -> bool:
            return not self.cli.skip_bootstrap

        def current_theme() -> str:
            return os.getenv("AI_CLI_THEME", "rich")

        settings = {
            "providers": {
                "desc": "Active Providers",
                "options": ["all", "local", "cloud", "none"],
                "getter": current_providers,
                "apply": self._update_providers,
            },
            "local_enabled": {
                "desc": "Local LLM Fallback",
                "options": [True, False],
                "getter": current_local_enabled,
                "apply": self._toggle_local,
            },
            "health_checks": {
                "desc": "Background Health Monitoring",
                "options": [True, False],
                "getter": current_health,
                "apply": self._toggle_health_checks,
            },
            "auto_bootstrap": {
                "desc": "Auto-Install Dependencies",
                "options": [True, False],
                "getter": current_bootstrap,
                "apply": self._toggle_bootstrap,
            },
            "theme": {
                "desc": "Console Theme",
                "options": ["rich", "plain", "dark"],
                "getter": current_theme,
                "apply": self._apply_theme,
            },
        }

        while True:
            table = Table(title="⚙️ Settings Menu")
            table.add_column("Feature", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Edit", style="magenta")

            for key, config in settings.items():
                status = config["getter"]()
                if isinstance(status, set):
                    status = ",".join(sorted(status))
                table.add_row(config["desc"], str(status), f"→ {key}")

            table.add_row("Exit", "", "→ q")
            console.print(table)

            choice = Prompt.ask("\nEdit or quit", choices=list(settings.keys()) + ["q"])
            if choice == "q":
                break

            config = settings[choice]
            current_value = config["getter"]()
            print(f"\n🔧 {config['desc']}")

            if set(config["options"]) == {True, False}:
                new_val = Confirm.ask(
                    f"Enable {config['desc']}?",
                    default=bool(current_value)
                )
            else:
                options_str = ", ".join(str(opt) for opt in config["options"])
                new_raw = Prompt.ask(
                    f"Choose ({options_str})",
                    default=str(current_value),
                    choices=[str(opt) for opt in config["options"]]
                )
                new_val = self._parse_setting_value(choice, new_raw)

            try:
                config["apply"](new_val)
                self._persist_setting(choice, new_val)
                if choice == "providers":
                    self.cli.reload_providers()
                print(f"✅ {config['desc']} → {new_val}")
            except Exception as exc:  # pragma: no cover - defensive
                print(f"❌ Error applying {config['desc']}: {exc}")

        print("💾 Settings saved. Changes applied live!")

    def _parse_setting_value(self, key: str, raw: str):
        value = raw.strip()
        if key == "providers":
            return value.lower()
        if key == "theme":
            return value.lower()
        return value

    def _update_providers(self, value: str) -> None:
        self.cli.set_provider_filter(value)

    def _toggle_local(self, enabled: bool) -> None:
        self.cli.set_local_enabled(enabled)

    def _toggle_health_checks(self, enabled: bool) -> None:
        self.cli.set_health_monitoring(enabled)

    def _toggle_bootstrap(self, enabled: bool) -> None:
        self.cli.set_auto_bootstrap(enabled)

    def _apply_theme(self, theme: str) -> None:
        self.cli.set_theme(theme)

    def _persist_setting(self, key: str, value) -> None:
        env_map = {
            "providers": "AI_CLI_ALLOWED_PROVIDERS",
            "local_enabled": "AI_CLI_LOCAL_ENABLED",
            "health_checks": "AI_CLI_HEALTH_CHECKS",
            "auto_bootstrap": "AI_CLI_SKIP_BOOTSTRAP",
            "theme": "AI_CLI_THEME",
        }

        env_key = env_map.get(key)
        if not env_key:
            return

        if key == "providers":
            if value == "all":
                self.cli.env_manager.remove_secret(env_key)
                os.environ.pop(env_key, None)
                return
            if value == "cloud":
                cloud_only = {k for k in self.cli.provider_manager.catalog.keys() if k != "local"}
                serialized = ",".join(sorted(cloud_only))
                self.cli.env_manager.write_secret(env_key, serialized)
                os.environ[env_key] = serialized
                return
            if value == "none":
                self.cli.env_manager.write_secret(env_key, "none")
                os.environ[env_key] = "none"
                return
            self.cli.env_manager.write_secret(env_key, value)
            os.environ[env_key] = value
            return

        if key == "local_enabled":
            serialized = "1" if value else "0"
            self.cli.env_manager.write_secret(env_key, serialized)
            os.environ[env_key] = serialized
            return

        if key == "health_checks":
            serialized = "1" if value else "0"
            self.cli.env_manager.write_secret(env_key, serialized)
            os.environ[env_key] = serialized
            return

        if key == "auto_bootstrap":
            serialized = "0" if value else "1"
            self.cli.env_manager.write_secret(env_key, serialized)
            os.environ[env_key] = serialized
            return

        if key == "theme":
            self.cli.env_manager.write_secret(env_key, value)
            os.environ[env_key] = value

    def do_read(self, arg):
        self._invoke_tool("read", arg)

    def do_diff(self, arg):
        self._invoke_tool("diff", arg)

    def do_git_status(self, arg):
        self._invoke_tool("git_status", arg)

    def do_test(self, arg):
        self._invoke_tool("test", arg)

    def do_sync_models(self, arg):
        self._invoke_tool("sync_models", arg)

    def do_pulse(self, arg):
        self._invoke_tool("pulse", arg)

    def do_codex(self, arg):
        goal = arg.strip()
        if not goal:
            print("Usage: codex <goal description>")
            return
        result = self._codex_execute(goal, verbose=True)
        if not result["success"]:
            print(result["message"])

    def do_api(self, arg):
        args = shlex.split(arg)
        host = "127.0.0.1"
        port = 8081
        stop = False

        idx = 0
        while idx < len(args):
            token = args[idx]
            if token in {"--stop", "stop"}:
                stop = True
            elif token.startswith("--host="):
                host = token.split("=", 1)[1]
            elif token == "--host" and idx + 1 < len(args):
                idx += 1
                host = args[idx]
            elif token.startswith("--port="):
                port = int(token.split("=", 1)[1])
            elif token == "--port" and idx + 1 < len(args):
                idx += 1
                port = int(args[idx])
            else:
                print(f"Unrecognized argument: {token}")
                return
            idx += 1

        try:
            if stop:
                message = asyncio.run(self.cli.stop_api_server())
            else:
                message = asyncio.run(self.cli.start_api_server(self, host, port))
            print(message)
        except Exception as exc:
            print(f"❌ API server error: {exc}")

    def do_pulse(self, arg):
        self._invoke_tool("pulse", arg)

    def _codex_execute(self, goal: str, verbose: bool = True) -> Dict[str, any]:
        transcript: List[str] = []

        def emit(line: str):
            transcript.append(line)
            if verbose:
                print(line)

        tools_summary = self._format_tool_catalog()
        context_block = self._codex_context()
        planning_prompt = (
            "You are Codex, an autonomous developer agent.\n"
            "Use the context below to reason about prerequisites.\n"
            "Return a JSON object with keys 'rationale' and 'steps'.\n"
            "Each step must include 'description', 'tool', and 'arguments'.\n"
            "Context:\n"
            f"{context_block}\n"
            "Available tools:\n"
            f"{tools_summary}\n"
            "Instructions: Ensure file operations reference relative paths when appropriate."
            " Always verify work (tests or diffs) when modifying code."
            " Return ONLY valid JSON without explanations.\n"
            f"Goal: {goal}"
        )

        plan_text, provider_key, model = self._generate_code_response(
            planning_prompt,
            verbose=True,
        )

        if not plan_text:
            message = "❌ Unable to generate plan."
            emit(message)
            self.cli.record_codex_run(
                {
                    "goal": goal,
                    "status": "failed",
                    "reason": "plan_generation_failed",
                    "provider": provider_key,
                    "model": model,
                    "raw_plan": plan_text,
                    "transcript": transcript,
                }
            )
            return {"success": False, "message": message}

        plan = self._parse_codex_plan(goal, plan_text)
        if not plan:
            message = "❌ Failed to parse plan response. Check logs."
            emit(message)
            self.cli.record_codex_run(
                {
                    "goal": goal,
                    "status": "failed",
                    "reason": "plan_parse_error",
                    "provider": provider_key,
                    "model": model,
                    "raw_plan": plan_text,
                    "transcript": transcript,
                }
            )
            return {"success": False, "message": message}

        emit("🧠 Codex Plan:")
        if plan.rationale:
            emit(f"  Rationale: {plan.rationale}")
        for idx, step in enumerate(plan.steps, start=1):
            emit(f"  {idx}. {step.description} [tool={step.tool}]")

        step_results = []
        for idx, step in enumerate(plan.steps, start=1):
            emit(f"⚙️ Step {idx}: {step.description}")
            if step.tool not in self.tools:
                message = f"❌ Tool '{step.tool}' is not available. Aborting."
                emit(message)
                run_payload = {
                    "goal": goal,
                    "status": "failed",
                    "reason": f"Tool '{step.tool}' unavailable",
                    "provider": provider_key,
                    "model": model,
                    "plan": [asdict(s) for s in plan.steps],
                    "raw_plan": plan_text,
                    "steps": step_results,
                    "rationale": plan.rationale,
                    "transcript": transcript,
                }
                self.cli.record_codex_run(run_payload)
                return {"success": False, "message": message, "data": run_payload}

            buffer_stdout = io.StringIO()
            buffer_stderr = io.StringIO()
            with contextlib.redirect_stdout(buffer_stdout), contextlib.redirect_stderr(buffer_stderr):
                result = self._invoke_tool(step.tool, step.arguments)
            out_text = buffer_stdout.getvalue().strip()
            err_text = buffer_stderr.getvalue().strip()
            if out_text:
                emit(out_text)
            if err_text:
                emit(err_text)

            step_result = {
                "index": idx,
                "description": step.description,
                "tool": step.tool,
                "arguments": step.arguments,
                "success": result.success,
                "message": result.message,
                "stdout": out_text,
                "stderr": err_text,
            }
            step_results.append(step_result)
            if not result.success:
                emit("⛔ Codex execution halted due to tool failure.")
                run_payload = {
                    "goal": goal,
                    "status": "failed",
                    "provider": provider_key,
                    "model": model,
                    "plan": [asdict(s) for s in plan.steps],
                    "steps": step_results,
                    "rationale": plan.rationale,
                    "raw_plan": plan_text,
                    "transcript": transcript,
                }
                self.cli.record_codex_run(run_payload)
                return {"success": False, "message": result.message, "data": run_payload}

        emit("✅ Codex execution complete.")
        run_payload = {
            "goal": goal,
            "status": "completed",
            "provider": provider_key,
            "model": model,
            "plan": [asdict(s) for s in plan.steps],
            "steps": step_results,
            "rationale": plan.rationale,
            "raw_plan": plan_text,
            "transcript": transcript,
        }
        self.cli.record_codex_run(run_payload)
        return {"success": True, "message": "Codex execution complete.", "data": run_payload}

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

    # ------------------------------------------------------------------
    # Tool handlers

    def _tool_save(self, arg: str) -> ToolResult:
        if not self._last_response:
            return ToolResult(False, "❌ No chat response available to save. Run a chat command first.")

        filename = arg.strip()
        if not filename:
            return ToolResult(False, "Usage: save <filename>")

        target_path = self._resolve_target_path(filename)
        if not target_path.suffix:
            target_path = target_path.with_suffix(".py")

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(self._last_response)
        except OSError as exc:
            return ToolResult(False, f"❌ Failed to save response: {exc}")

        return ToolResult(True, f"✅ Chat response saved to {target_path}")

    def _tool_run(self, arg: str) -> ToolResult:
        text = arg.strip()
        if not text:
            return ToolResult(False, "Usage: run <filename.py> [-- <args>]")

        parts = text.split(" -- ", 1)
        filename = parts[0].strip()
        extra_args = parts[1].strip().split() if len(parts) == 2 else []

        path = self._resolve_target_path(filename)
        if not path.suffix:
            path = path.with_suffix(".py")

        if not path.exists():
            return ToolResult(False, f"❌ File '{path.name}' not found. Use `save <filename>` first.")

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
            return ToolResult(False, "⛔ Script interrupted by user.")
        except OSError as exc:
            return ToolResult(False, f"❌ Failed to run script: {exc}")

        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0 and not result.stderr:
            return ToolResult(False, f"⚠️ Script exited with code {result.returncode}")
        return ToolResult(True)

    def _tool_create(self, arg: str) -> ToolResult:
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            return ToolResult(False, "Usage: create <filename> <prompt>\nExample: create src/core.py build me a function to validate JSON")

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
            return ToolResult(False, "❌ Generation failed. Check provider status and logs.")

        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            if lines and lines and lines[0].startswith("python"):
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(cleaned)
        except Exception as exc:
            return ToolResult(False, f"❌ Error saving file: {exc}")

        self._last_response = cleaned
        provider_label = provider_key or "unknown provider"
        model_label = model or "unknown model"
        return ToolResult(True, f"✅ Code generated by {provider_label} ({model_label}) and saved to {target_path.resolve()}")

    def _tool_scaffold(self, arg: str) -> ToolResult:
        parts = arg.split()
        if not parts:
            return ToolResult(False, "Usage: scaffold <base_path> <project_name> | scaffold <project_name>")

        if len(parts) == 1:
            base_path = Path.cwd()
            project_name = parts[0]
        else:
            base_path = Path(parts[0]).expanduser()
            project_name = parts[1]

        try:
            root, created = scaffold_project(str(base_path), project_name)
        except FileExistsError as exc:
            return ToolResult(False, f"❌ {exc}")
        except PermissionError as exc:
            return ToolResult(False, f"❌ Permission denied: {exc}")
        except Exception as exc:
            return ToolResult(False, f"❌ Unable to scaffold project: {exc}")

        self.cli.active_project = root
        if created:
            msg = f"✅ Project '{project_name}' scaffolded at {root}"
        else:
            msg = f"ℹ️ Project '{project_name}' already exists. Using existing scaffold at {root}"
        msg += "\n   You can now generate code and save files into this structure."
        return ToolResult(True, msg)

    def _tool_read(self, arg: str) -> ToolResult:
        if not arg.strip():
            return ToolResult(False, "Usage: read <path>")

        target_path = self._resolve_target_path(arg.strip())
        if not target_path.exists():
            return ToolResult(False, f"❌ File '{target_path}' not found")
        if target_path.is_dir():
            return ToolResult(False, f"❌ '{target_path}' is a directory")

        try:
            content = target_path.read_text()
        except UnicodeDecodeError:
            return ToolResult(False, f"❌ Unable to decode '{target_path}' as text")
        except OSError as exc:
            return ToolResult(False, f"❌ Failed to read '{target_path}': {exc}")

        print(f"----- {target_path} -----")
        print(content)
        print("----- end -----")
        return ToolResult(True)

    def _tool_diff(self, arg: str) -> ToolResult:
        args = shlex.split(arg) if arg.strip() else []
        cmd = ["git", "diff", *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cli.active_project or Path.cwd(),
            )
        except FileNotFoundError:
            return ToolResult(False, "❌ git not found in PATH")

        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0 and not result.stderr:
            return ToolResult(False, f"⚠️ git diff exited with code {result.returncode}")
        return ToolResult(True)

    def _tool_git_status(self, arg: str) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", "status", "-sb"],
                capture_output=True,
                text=True,
                cwd=self.cli.active_project or Path.cwd(),
            )
        except FileNotFoundError:
            return ToolResult(False, "❌ git not found in PATH")

        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0 and not result.stderr:
            return ToolResult(False, f"⚠️ git status exited with code {result.returncode}")
        return ToolResult(True)

    def _tool_test(self, arg: str) -> ToolResult:
        cmd = shlex.split(arg) if arg.strip() else [sys.executable or "python3", "-m", "pytest"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cli.active_project or Path.cwd(),
            )
        except FileNotFoundError as exc:
            return ToolResult(False, f"❌ Command not found: {cmd[0]}")

        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
        if result.returncode != 0:
            return ToolResult(False, f"⚠️ Tests exited with code {result.returncode}")
        return ToolResult(True, "✅ Tests passed")

    def _tool_sync_models(self, arg: str) -> ToolResult:
        try:
            summary = asyncio.run(self.cli.provider_manager.sync_free_models())
        except RuntimeError as exc:
            return ToolResult(False, f"❌ {exc}")
        except Exception as exc:  # pragma: no cover
            return ToolResult(False, f"❌ Sync failed: {exc}")

        for provider, info in summary.items():
            print(f"{provider}: {info}")
        return ToolResult(True, "✅ Model catalogs refreshed")

    def _tool_pulse(self, arg: str) -> ToolResult:
        try:
            summary = asyncio.run(self.cli.provider_manager.pulse_providers())
        except RuntimeError as exc:
            return ToolResult(False, f"❌ {exc}")
        except Exception as exc:  # pragma: no cover
            return ToolResult(False, f"❌ Pulse failed: {exc}")

        for provider, info in summary.items():
            print(f"{provider}: {info}")
        return ToolResult(True, "✅ Provider heartbeat complete")

    # ------------------------------------------------------------------
    # Codex helpers

    def _provider_prompt(self) -> str:
        manager = self.cli.provider_manager
        summary_parts = []
        order = ["groq", "openrouter", "huggingface", "together", "replicate"]
        for key in order:
            if key not in manager.catalog:
                continue
            state = manager.status.get(
                key, "unconfigured" if key not in manager.providers else "unknown"
            )
            symbol = {
                "healthy": "🟢",
                "connecting": "🟡",
                "error": "🔴",
                "unknown": "⚪️",
                "unconfigured": "⚪️",
            }.get(state, "⚪️")
            summary_parts.append(symbol)
        return "".join(summary_parts) + (" " if summary_parts else "")

    def _format_tool_catalog(self) -> str:
        lines = []
        for name, spec in sorted(self.tools.items()):
            lines.append(f"- {name}: {spec.description}")
        return "\n".join(lines)

    def _codex_context(self) -> str:
        ctx_lines = []
        ctx_lines.append(f"Active project: {self.cli.active_project or '(none)'}")
        available = self.cli.provider_manager.available_providers()
        if available:
            provider_lines = []
            for provider in available:
                provider_lines.append(
                    f"  - {provider.meta.display_name} ({provider.meta.identifier}) default={provider.meta.default_model}"
                )
            ctx_lines.append("Available providers:\n" + "\n".join(provider_lines))
        else:
            ctx_lines.append("Available providers: none (use local tools only)")

        if self.cli.active_project:
            files = list(self.cli.active_project.glob("*"))[:5]
            if files:
                preview = "\n".join(f"  - {p.name}" for p in files)
                ctx_lines.append("Project contents (preview):\n" + preview)

        return "\n".join(ctx_lines)

    def _parse_codex_plan(self, goal: str, plan_text: str) -> Optional[CodexPlan]:
        try:
            json_start = plan_text.find('{')
            json_end = plan_text.rfind('}')
            if json_start == -1 or json_end == -1:
                raise ValueError("No JSON object detected")
            payload = json.loads(plan_text[json_start:json_end + 1])
        except Exception as exc:
            print(f"❌ Plan parsing error: {exc}")
            print(plan_text)
            return None

        steps_payload = payload.get("steps") or []
        steps: List[CodexStep] = []
        for entry in steps_payload:
            try:
                steps.append(
                    CodexStep(
                        description=entry.get("description", "(no description)"),
                        tool=entry.get("tool", ""),
                        arguments=entry.get("arguments", ""),
                    )
                )
            except Exception:
                continue

        rationale = payload.get("rationale", "")
        return CodexPlan(goal=goal, steps=steps, rationale=rationale)

    def do_setenv(self, arg):
        "Set API key securely: setenv <provider|ENV_VAR> [value]."
        raw = arg.strip()
        if not raw:
            print("Usage: setenv <provider|ENV_VAR> [value]")
            return

        parts = shlex.split(raw)
        target = parts[0]
        inline_value = parts[1] if len(parts) > 1 else None

        env_key = self.cli.provider_manager.env_var_for(target) or target
        env_key = env_key.strip()

        if inline_value is None:
            secret = self._collect_secret(env_key)
            if secret is None:
                return
        else:
            secret = inline_value

        try:
            self.cli.env_manager.write_secret(env_key, secret)
        except RuntimeError as exc:
            print(f"❌ {exc}")
            return

        self.cli.provider_manager.reload()
        print(f"Stored secret for {env_key} in {self.cli.env_manager.path_str()}.")

    def do_save(self, arg):
        self._invoke_tool("save", arg)

    def do_run(self, arg):
        self._invoke_tool("run", arg)

    def do_create(self, arg):
        self._invoke_tool("create", arg)

    def do_scaffold(self, arg):
        self._invoke_tool("scaffold", arg)

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
        status_map = self.cli.provider_manager.status
        for entry in report:
            state = entry.get("status", "configured" if entry["active"] else "unconfigured")
            if entry["active"]:
                indicator = {
                    "healthy": "🟢",
                    "connecting": "🟡",
                    "error": "🔴",
                    "configured": "🟢" if status_map.get(entry["key"], "configured") != "error" else "🔴",
                    "unknown": "🟡",
                }.get(state, "🟢")
            else:
                indicator = "⚪️"
            print(
                f"{indicator} {entry['provider']}: {entry['requests']}/{entry['limit']} requests | "
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
            self._render_system_message(
                f"❌ Provider '{provider_key}' not configured",
                level="error",
            )
            return

        self._chat_with_failover(message, [(provider_key, model)])

    def _chat_with_failover(self, message: str, sequence: Optional[List[Tuple[str, str]]] = None) -> bool:
        content, provider_key, model = self._generate_code_response(
            message, sequence, verbose=True
        )
        if content:
            self._last_response = content
            self._render_ai_message(content, provider_key, model)
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
                self._render_system_message(
                    "No providers available. Run 'setup_providers' to add API keys.",
                    level="warn",
                )
            return None, None, None

        any_attempted = False
        last_error = None
        for provider_key, model in sequence:
            if provider_key not in self.cli.provider_manager.providers:
                continue
            if not self.cli.provider_manager.has_quota(provider_key):
                if verbose:
                    self._render_system_message(
                        f"⏳ {provider_key} has reached its daily limit. Skipping.",
                        level="warn",
                    )
                continue

            if verbose:
                self._render_system_message(
                    f"🎯 Using {provider_key} :: {model}",
                    level="info",
                )
            success, content, error = self._attempt_chat(provider_key, model, message)
            if success and content:
                self.last_provider, self.last_model = provider_key, model
                return content, provider_key, model

            any_attempted = True
            last_error = error
            if verbose and error:
                self._render_system_message(
                    f"⚠️ {provider_key}/{model}: {error}. Trying next...",
                    level="warn",
                )

        if verbose:
            if any_attempted:
                detail = f" Last error: {last_error}" if last_error else ""
                self._render_system_message(
                    f"❌ All providers failed. Try again later or update API keys.{detail}",
                    level="error",
                )
            else:
                self._render_system_message(
                    "❌ All providers unavailable. Configure API keys or reset quotas.",
                    level="error",
                )
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
        self.project_root = Path(__file__).resolve().parent
        preferred_config_dir = Path.home() / ".ai_cli_autonomous"
        fallback_config_dir = self.project_root / ".ai_cli_autonomous_local"
        self.config_dir = preferred_config_dir
        try:
            self.config_dir.mkdir(exist_ok=True)
            test_path = self.config_dir / ".write_test"
            with open(test_path, "w") as f:
                f.write("ok")
            test_path.unlink(missing_ok=True)
        except (PermissionError, OSError):
            self.config_dir = fallback_config_dir
            self.config_dir.mkdir(exist_ok=True)

        self.log_file = self.config_dir / "autonomous.log"
        self.health_file = self.config_dir / "health.json"
        self.env_path = self.project_root / ".env"
        self.provider_usage_file = self.config_dir / "provider_usage.json"
        self.env_manager = SecureEnvManager(self.env_path)
        self.provider_manager = ProviderManager(self.env_path, self.provider_usage_file)
        self.skip_bootstrap = os.getenv("AI_CLI_SKIP_BOOTSTRAP", "0").strip().lower() in {"1", "true", "on", "yes"}
        self.health_monitoring = os.getenv("AI_CLI_HEALTH_CHECKS", "1").strip().lower() not in {"0", "false", "off", "no"}
        self.active_project: Optional[Path] = None
        self.codex_state_file = self.config_dir / "codex_state.json"
        self._network_warned = False
        self.api_server: Optional[CodexAPIServer] = None
        self.api_server_task: Optional[asyncio.Task] = None
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

    def provider_filter_mode(self) -> str:
        allowed = self.provider_manager.allowed_providers
        if allowed is None:
            return "all"
        if not allowed:
            return "none"
        allowed_lower = {name.lower() for name in allowed}
        if allowed_lower == {"local"}:
            return "local"
        cloud_only = {key for key in self.provider_manager.catalog.keys() if key != "local"}
        if allowed_lower == cloud_only:
            return "cloud"
        return ",".join(sorted(allowed_lower))

    def set_provider_filter(self, mode: str) -> None:
        catalog_keys = {key for key in self.provider_manager.catalog.keys()}
        if mode == "all":
            self.provider_manager.allowed_providers = None
        elif mode == "local":
            self.provider_manager.allowed_providers = {"local"}
        elif mode == "cloud":
            self.provider_manager.allowed_providers = {key for key in catalog_keys if key != "local"}
        elif mode == "none":
            self.provider_manager.allowed_providers = set()
        else:
            selection = {part.strip().lower() for part in mode.split(",") if part.strip()}
            self.provider_manager.allowed_providers = selection or None
        self.reload_providers()

    def reload_providers(self, reread_env: bool = False) -> None:
        self.provider_manager.reload_providers(reread_env=reread_env)

    def set_local_enabled(self, enabled: bool) -> None:
        os.environ["AI_CLI_LOCAL_ENABLED"] = "1" if enabled else "0"
        self.reload_providers()

    def set_health_monitoring(self, enabled: bool) -> None:
        self.health_monitoring = bool(enabled)
        os.environ["AI_CLI_HEALTH_CHECKS"] = "1" if enabled else "0"

    def set_auto_bootstrap(self, enabled: bool) -> None:
        self.skip_bootstrap = not enabled
        os.environ["AI_CLI_SKIP_BOOTSTRAP"] = "0" if enabled else "1"

    def set_theme(self, theme: str) -> None:
        os.environ["AI_CLI_THEME"] = theme

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
        if self.skip_bootstrap:
            self.log("⏭️  Dependency bootstrap skipped (AI_CLI_SKIP_BOOTSTRAP=1).")
            self.health.dependencies_ok = True
            return
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
        try:
            with open(cf,"w") as f:
                json.dump(cfg,f,indent=2)
            if os.name!="nt":
                os.chmod(cf,0o600)
        except PermissionError:
            fallback_cf = self.project_root / "config.json"
            with open(fallback_cf, "w") as f:
                json.dump(cfg, f, indent=2)
            cf = fallback_cf
        self.log(f"⚙️ Config written to {cf}")

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
                self._network_warned = False
                return True
            except OSError:
                self.log(f"🟡 Failed to connect to {host}:{port}.")
        if not self._network_warned:
            self.log("❌ Network connection failed.", "ERROR")
            self._network_warned = True
        return False
    async def _test_cfg(self):
        return (self.config_dir/"config.json").exists()

    async def _test_providers(self):
        if not self.provider_manager.providers:
            self.log("ℹ️ No provider credentials found yet. Skipping provider check.")
            return True

        self.log("✅ Provider credentials detected.")
        return True

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
        target_dir = self.config_dir
        try:
            target_dir.mkdir(exist_ok=True)
        except PermissionError:
            target_dir = self.project_root / "ai_cli_output"
            target_dir.mkdir(exist_ok=True)

        try:
            (target_dir/"README.md").write_text("# Autonomous AI CLI Rotator\nSystem Ready!")
            ui = target_dir/"user_interface.py"
            ui.write_text("""#!/usr/bin/env python3
import typer
from rich.console import Console
app=typer.Typer()
console=Console()
@app.command()
def status():
    console.print("System Operational")
if __name__=="__main__":app()""")
        except PermissionError as exc:
            self.log(f"⚠️ Unable to write user-ready artifacts: {exc}", "WARNING")
        self.health.uptime=time.time()-self.start_time
        self.save_health_state()
        self.log("✅ Ready")

    async def _start_continuous_monitoring(self):
        if not self.health_monitoring:
            self.log("👁️ Monitoring disabled by configuration.")
            return
        self.log("👁️ Monitoring – Starting health checks...")
        iteration = 0
        while self.health_monitoring and iteration < 5:  # Simulated finite loop
            await self._health_check()
            iteration += 1
            self.log(f"Health check iteration {iteration} complete.")
            if not self.health_monitoring:
                break
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
        try:
            with open(self.health_file, "w") as f:
                json.dump(data, f, indent=2)
        except PermissionError:
            fallback = self.project_root / "health.json"
            with open(fallback, "w") as f:
                json.dump(data, f, indent=2)
            self.health_file = fallback

    def record_codex_run(self, entry: Dict) -> None:
        log = []
        if self.codex_state_file.exists():
            try:
                log = json.loads(self.codex_state_file.read_text())
            except json.JSONDecodeError:
                log = []

        timestamp = datetime.now().isoformat()
        entry.setdefault("timestamp", timestamp)
        log.append(entry)
        self.codex_state_file.write_text(json.dumps(log, indent=2))
        runs_dir = self.config_dir / "codex_runs"
        runs_dir.mkdir(exist_ok=True)
        safe_ts = timestamp.replace(":", "").replace("-", "").replace("T", "_")
        transcript_path = runs_dir / f"codex_{safe_ts}.json"
        transcript_path.write_text(json.dumps(entry, indent=2))
        self.log(f"Codex entry recorded for goal: {entry.get('goal','unknown')}\nStatus: {entry.get('status','unknown')} -> {transcript_path}")

    async def start_api_server(self, prompt: "AutonomousPrompt", host: str = "127.0.0.1", port: int = 8081) -> str:
        if self.api_server_task and not self.api_server_task.done():
            raise RuntimeError("API server already running")
        self.api_server = CodexAPIServer(prompt, host, port)
        loop = asyncio.get_running_loop()
        self.api_server_task = loop.create_task(self.api_server.start())
        await self.api_server.ready.wait()
        return f"API server running on http://{host}:{port}"

    async def stop_api_server(self) -> str:
        if not self.api_server or not self.api_server_task:
            return "API server is not running."
        await self.api_server.stop()
        await self.api_server_task
        self.api_server_task = None
        self.api_server = None
        return "API server stopped."

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
