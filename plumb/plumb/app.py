import json
import uuid
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from rich.console import Console
from io import StringIO

from plumb.screens.splash import SplashScreen
from plumb.screens.main import MainScreen
from plumb.ollama.client import OllamaClient
from plumb.ollama.prompts import ResponseCache
from plumb.actions.executor import ActionExecutor
from plumb.web.search import WebSearch


class PlumbApp(App):
    CSS_PATH = "css/styles.tcss"
    TITLE = "Plumb"
    SUB_TITLE = ""

    SCREENS = {
        "splash": SplashScreen,
        "main": MainScreen,
    }

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def get_key_display(self, binding: Binding) -> str:
        if binding.key_display:
            return binding.key_display
        from textual.keys import format_key
        modifiers, key = binding.parse_key()
        key = format_key(key)
        return "+".join(modifiers + [key])

    def __init__(self):
        super().__init__()
        self.ollama = OllamaClient()
        self.executor: ActionExecutor | None = None
        self.conversation_history: list[str] = []
        self.working_dir = Path.cwd()
        self._last_prompt = ""
        self.sessions_dir = self.working_dir / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)
        self._session_id = None
        self._auto_confirm = False
        self._output_lines: list[str] = []
        self._rich_console = Console(file=StringIO(), width=200, no_color=True)
        self._heading = ""
        self._task_list: list[dict] = []
        self._thinking_level = "med"
        self.mistakes_file = self.working_dir / "plumb_mistakes.json"
        self.response_cache = ResponseCache(max_size=20)
        self.websearch = WebSearch()

    def on_mount(self):
        self.executor = ActionExecutor(self.working_dir)
        self.push_screen("splash")

    def generate_session_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def start_new_session(self):
        self._session_id = self.generate_session_id()
        self.conversation_history.clear()
        self._output_lines = []
        self._heading = "..."
        self._task_list = []

    def load_session(self, session_id: str) -> bool:
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return False
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._session_id = session_id
            self.conversation_history = data.get("messages", [])
            self._output_lines = data.get("output_lines", [])
            self._heading = data.get("heading", "")
            self._task_list = data.get("task_list", [])
            self._thinking_level = data.get("thinking_level", "med")
            return True
        except Exception:
            return False

    def save_session(self):
        if self._session_id is None:
            self._session_id = self.generate_session_id()
        session_file = self.sessions_dir / f"{self._session_id}.json"
        data = {
            "id": self._session_id,
            "messages": self.conversation_history,
            "output_lines": self._output_lines,
            "heading": self._heading,
            "task_list": self._task_list,
            "thinking_level": self._thinking_level,
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def render_to_markup(self, renderable) -> str:
        self._rich_console.file.truncate(0)
        self._rich_console.file.seek(0)
        self._rich_console.print(renderable)
        return self._rich_console.file.getvalue().rstrip("\n")

    def save_output_line(self, line: str):
        self._output_lines.append(line)

    def save_panel(self, content: str, title: str = "", border_style: str = "#333333"):
        self._output_lines.append({
            "type": "panel",
            "content": content,
            "title": title,
            "border_style": border_style,
        })
