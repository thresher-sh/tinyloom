from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from tinyloom.core.tools import Tool

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent

@dataclass
class TodoItem:
    id: int
    description: str
    status: str = "pending"

class TodoPlugin:
    def __init__(self):
        self.tasks: list[TodoItem] = []
        self._next_id = 1

    def handle_todo(self, inp: dict) -> str:
        action = inp.get("action", "list")
        if action == "create":
            desc = inp.get("description", "")
            if not desc: return "Error: description is required"
            item = TodoItem(id=self._next_id, description=desc)
            self.tasks.append(item)
            self._next_id += 1
            return f"Task {item.id} created: {desc}"
        elif action == "update_status":
            task_id = int(inp.get("task_id", 0))
            status = inp.get("status", "")
            if status not in ("pending", "in_progress", "done"):
                return f"Error: invalid status '{status}'. Use: pending, in_progress, done"
            for task in self.tasks:
                if task.id == task_id:
                    task.status = status
                    return f"Task {task_id} updated to {status}"
            return f"Error: task {task_id} not found"
        elif action == "list":
            if not self.tasks: return "No tasks."
            return "Tasks:\n" + "\n".join(f"  [{t.status}] {t.id}. {t.description}" for t in self.tasks)
        else:
            return f"Error: unknown action '{action}'. Use: create, update_status, list"

    def has_incomplete_tasks(self) -> bool:
        return any(t.status != "done" for t in self.tasks)

    def incomplete_summary(self) -> str:
        incomplete = [t for t in self.tasks if t.status != "done"]
        if not incomplete: return ""
        return "Incomplete tasks:\n" + "\n".join(f"  [{t.status}] {t.id}. {t.description}" for t in incomplete)

def activate(agent: Agent):
    plugin = TodoPlugin()
    agent._todo_plugin = plugin

    agent.tools.register(Tool(
        name="todo",
        description="Manage a task list. Actions:\n- create: new task (requires 'description')\n- update_status: change status (requires 'task_id', 'status': pending/in_progress/done)\n- list: show all tasks",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "update_status", "list"]},
                "description": {"type": "string"},
                "task_id": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
            },
            "required": ["action"],
        },
        function=plugin.handle_todo,
    ))

    async def on_response_complete(ctx):
        if plugin.has_incomplete_tasks():
            from tinyloom.core.types import Message
            agent.state.messages.append(Message(role="user", content=f"You still have incomplete tasks. Please finish them:\n{plugin.incomplete_summary()}"))
            ctx["continue"] = True

    agent.hooks.on("response_complete", on_response_complete)
