import asyncio
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import AsyncGenerator
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text as RichText
from .types import Action, ActionType

COMMAND_TIMEOUT = 30

ANSI_SEQUENCE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
ANSI_MOUSE_SGR_RE = re.compile(r'\x1b\[<[\d;]*[Mm]')
ANSI_MOUSE_X10_RE = re.compile(r'\x1b\[M[\x00-\x7f]{2}')
ANSI_OSC_RE = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')


WIN_INTERACTIVE_FIXES = {
    "date": "date /t",
    "time": "time /t",
    "pause": "rem paused",
    "cls": "cls",
    "color": "rem color",
    "title": "rem title",
    "prompt": "rem prompt",
}


def _fix_command_for_windows(command: str) -> str:
    cmd = command.strip()
    if cmd.startswith("./") or cmd.startswith(".\\"):
        script = cmd[2:].strip()
        if script.endswith(".py"):
            return f"python {script}"
        elif script.endswith(".js"):
            return f"node {script}"
    if cmd.startswith("python3 "):
        cmd = "python " + cmd[8:]
    base_cmd = cmd.split()[0].lower() if cmd.split() else ""
    if base_cmd in WIN_INTERACTIVE_FIXES:
        replacement = WIN_INTERACTIVE_FIXES[base_cmd]
        cmd = cmd.replace(base_cmd, replacement, 1)
    return cmd


def _strip_ansi(text: str) -> str:
    text = ANSI_MOUSE_SGR_RE.sub('', text)
    text = ANSI_MOUSE_X10_RE.sub('', text)
    text = ANSI_OSC_RE.sub('', text)
    text = ANSI_SEQUENCE_RE.sub('', text)
    return text


def _detect_language(path: str) -> str:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "jsx", ".tsx": "tsx", ".html": "html", ".css": "css",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".sh": "bash", ".bash": "bash",
        ".rs": "rust", ".go": "go", ".java": "java", ".c": "c",
        ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".rb": "ruby",
        ".php": "php", ".sql": "sql", ".xml": "xml",
        ".toml": "toml", ".ini": "ini", ".cfg": "ini",
        ".txt": "text", ".log": "text",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return "text"


def _make_code_block(content: str, path: str, title: str = "") -> Panel:
    lang = _detect_language(path)
    syntax = Syntax(
        content,
        lang,
        theme="monokai",
        line_numbers=True,
        word_wrap=True,
        indent_guides=True,
        background_color="#141414",
    )
    return Panel(
        syntax,
        title=title or path,
        title_align="left",
        border_style="#30363d",
        padding=(0, 1),
    )


class ActionExecutor:
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir.resolve()
        self.output_width: int = 120

    async def execute(self, actions: list[Action]) -> AsyncGenerator[str, None]:
        for action in actions:
            if action.type == ActionType.CREATE_FILE:
                yield f"[info]Creating {action.path}...[/info]"
                try:
                    path = self.working_dir / action.path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    content = action.content or ""
                    path.write_text(content, encoding="utf8")

                    yield ""
                    yield _make_code_block(content, action.path, f"Contents of {action.path}")
                    yield ""
                    yield f"[success][OK] Created {action.path}[/success]"
                except Exception as e:
                    yield f"[error][ERR] Failed to create {action.path}: {e}[/error]"

            elif action.type == ActionType.EDIT_FILE:
                yield f"[info]Editing {action.path}...[/info]"
                try:
                    path = self.working_dir / action.path
                    if not path.exists():
                        yield f"[error][ERR] File not found: {action.path}[/error]"
                        continue
                    old_content = path.read_text(encoding="utf8") if path.exists() else ""
                    new_content = action.content or ""
                    path.write_text(new_content, encoding="utf8")

                    yield ""
                    yield _make_code_block(new_content, action.path, f"Updated {action.path}")
                    yield ""
                    yield f"[success][OK] Edited {action.path}[/success]"
                except Exception as e:
                    yield f"[error][ERR] Failed to edit {action.path}: {e}[/error]"

            elif action.type == ActionType.RUN_COMMAND:
                command = action.command
                if sys.platform == "win32":
                    command = _fix_command_for_windows(command)
                yield f"[info]Running: {command}[/info]"

                cwd_str = action.cwd if action.cwd else "."
                cwd = (self.working_dir / cwd_str).resolve()
                try:
                    cwd.relative_to(self.working_dir)
                except ValueError:
                    yield f"[error][ERR] Command cwd escapes working directory[/error]"
                    continue

                if not cwd.exists():
                    yield f"[error][ERR] Directory not found: {cwd_str}[/error]"
                    continue

                try:
                    if sys.platform == "win32":
                        cmd_parts = ["cmd.exe", "/c"] + command.split()
                    else:
                        cmd_parts = shlex.split(command)
                except ValueError as e:
                    yield f"[error][ERR] Failed to parse command: {e}[/error]"
                    continue

                try:
                    env = os.environ.copy()
                    env["TERM"] = "dumb"
                    env["NO_COLOR"] = "1"
                    env["TERMINFO"] = ""
                    proc = await asyncio.create_subprocess_exec(
                        *cmd_parts,
                        cwd=cwd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            proc.communicate(),
                            timeout=COMMAND_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                capture_output=True,
                                timeout=5,
                            )
                        else:
                            proc.kill()
                            await asyncio.wait_for(proc.wait(), timeout=5)
                        yield f"[error][ERR] Command timed out after {COMMAND_TIMEOUT}s[/error]"
                        continue

                    if stdout:
                        out = _strip_ansi(stdout.decode(errors="replace")).rstrip()
                        if out:
                            yield Panel(
                                out,
                                title="stdout",
                                title_align="left",
                                border_style="#e6edf3",
                                padding=(0, 1),
                            )
                    if stderr:
                        err = _strip_ansi(stderr.decode(errors="replace")).rstrip()
                        if err:
                            yield Panel(
                                err,
                                title="stderr",
                                title_align="left",
                                border_style="#d29922",
                                padding=(0, 1),
                            )
                    yield f"[info]Exit code: {proc.returncode}[/info]"

                except FileNotFoundError:
                    yield f"[error][ERR] Command not found: {cmd_parts[0]}[/error]"
                except PermissionError:
                    yield f"[error][ERR] Permission denied: {cmd_parts[0]}[/error]"
                except Exception as e:
                    yield f"[error][ERR] Failed to run command: {e}[/error]"
