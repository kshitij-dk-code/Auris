"""Terminal output: rich-colored status lines, banners, and panels."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Visuals go to stdout (rich strips ANSI automatically when piped/not a TTY)
out = Console(stderr=False)
# Status messages go to stderr so stdout stays clean for the prompt text
err = Console(stderr=True)


def status(icon: str, label: str, message: str = "", color: str = "cyan", bell: bool = False) -> None:
    style = {"dim": "grey50", "red": "bold red", "yellow": "bold yellow", "cyan": "bold cyan"}.get(color, color)
    line = Text()
    line.append(f"{icon} ", style=style)
    line.append(f"[{label}] ", style="bold")
    if message:
        line.append(message, style="dim")
    err.print(line)
    if bell:
        err.print("\a", end="")


def info(message: str) -> None:
    err.print(f"    [dim]{message}[/dim]")


def warn(message: str) -> None:
    err.print(f"  [yellow]![/yellow] {message}")


def error(message: str) -> None:
    err.print(f"  [bold red]✗[/bold red] {message}")


def banner(title: str) -> None:
    err.rule(f"[bold]{title}[/bold]", style="cyan")


def transcript_panel(text: str) -> None:
    """Dim panel showing the raw speech transcript."""
    out.print(Panel(
        Text(text, style="italic yellow"),
        title="[bold]Transcript[/bold]",
        subtitle="[dim]what you said[/dim]",
        border_style="dim yellow",
        expand=False,
    ))


def enhanced_panel(text: str) -> None:
    """Bright panel showing the enhanced prompt (also on the clipboard)."""
    out.print(Panel(
        Text(text, style="bold white"),
        title="[bold cyan]Enhanced Prompt[/bold cyan]",
        subtitle="[dim]also copied to clipboard[/dim]",
        border_style="bright_cyan",
        expand=False,
        padding=(1, 2),
    ))


def stdout(text: str) -> None:
    print(text, flush=True)
