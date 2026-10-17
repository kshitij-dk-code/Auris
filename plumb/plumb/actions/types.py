from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ActionType(Enum):
    CREATE_FILE = "create_file"
    EDIT_FILE = "edit_file"
    RUN_COMMAND = "run_command"
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"

@dataclass
class Action:
    type: ActionType
    path: Optional[str] = None
    content: Optional[str] = None
    command: Optional[str] = None
    cwd: str = "."
    query: Optional[str] = None
    url: Optional[str] = None

    def label(self) -> str:
        if self.type == ActionType.CREATE_FILE:
            return f"Create {self.path}"
        elif self.type == ActionType.EDIT_FILE:
            return f"Edit {self.path}"
        elif self.type == ActionType.RUN_COMMAND:
            return f"Run: {self.command}"
        elif self.type == ActionType.WEB_SEARCH:
            return f"Web search: {self.query}"
        elif self.type == ActionType.WEB_FETCH:
            return f"Fetch: {self.url}"
        return str(self.type.value)