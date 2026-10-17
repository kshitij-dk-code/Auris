import json
from .types import Action, ActionType

class ParseError(Exception):
    pass

def parse_actions(json_str: str) -> list[Action]:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}")

    if "actions" not in data:
        raise ParseError("Missing 'actions' key")

    actions = []
    for item in data["actions"]:
        try:
            atype = ActionType(item["type"])
        except (KeyError, ValueError):
            raise ParseError(f"Invalid action type: {item.get('type')}")

        action = Action(type=atype)
        if atype in (ActionType.CREATE_FILE, ActionType.EDIT_FILE):
            action.path = item.get("path")
            action.content = item.get("content", "")
            if action.content:
                action.content = action.content.replace("\\n", "\n").replace("\\t", "\t")
            if not action.path:
                raise ParseError(f"Missing path for {atype.value}")
        elif atype == ActionType.RUN_COMMAND:
            action.command = item.get("command")
            action.cwd = item.get("cwd", ".")
            if not action.command:
                raise ParseError("Missing command for run_command")
        elif atype == ActionType.WEB_SEARCH:
            action.query = item.get("query")
            if not action.query:
                raise ParseError("Missing query for web_search")
        elif atype == ActionType.WEB_FETCH:
            action.url = item.get("url")
            if not action.url:
                raise ParseError("Missing url for web_fetch")
        actions.append(action)

    return actions


def parse_tasks(json_str: str) -> list[dict]:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return []
    raw_tasks = data.get("tasks", [])
    tasks = []
    for t in raw_tasks:
        if isinstance(t, str):
            tasks.append({"description": t, "done": False})
        elif isinstance(t, dict) and "description" in t:
            tasks.append({
                "description": t["description"],
                "done": t.get("done", False),
            })
    return tasks