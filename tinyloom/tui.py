from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, Input, Static
from textual.binding import Binding

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


class MessageWidget(Static):
    pass


class TinyloomApp(App):
    CSS = """
    VerticalScroll { height: 1fr; }
    #input { dock: bottom; }
    .tool-call { color: green; }
    .tool-result { color: $text-muted; }
    .error { color: red; }
    .compaction { color: yellow; text-style: dim; }
    """

    BINDINGS = [Binding("ctrl+c", "quit", "Quit")]

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent
        self.title = f"tinyloom - {agent.config.model.model}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="messages")
        yield Input(placeholder="Type a message...", id="input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return
        event.input.clear()

        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(MessageWidget(f"[bold]You:[/bold] {user_input}"))

        self.query_one("#input", Input).disabled = True
        text_buffer = ""
        text_widget = MessageWidget("")
        messages.mount(text_widget)

        async for evt in self.agent.step(user_input):
            if evt.type == "text_delta":
                text_buffer += evt.text
                text_widget.update(text_buffer)
            elif evt.type == "tool_call":
                tc = evt.tool_call
                preview = str(tc.input)[:100]
                messages.mount(MessageWidget(f"[green]> {tc.name}[/green]({preview})", classes="tool-call"))
            elif evt.type == "tool_result":
                preview = evt.result[:200] if evt.result else "(empty)"
                messages.mount(MessageWidget(f"[dim]  -> {preview}[/dim]", classes="tool-result"))
            elif evt.type == "compaction":
                messages.mount(MessageWidget("[yellow dim]Context compacted[/yellow dim]", classes="compaction"))
            elif evt.type == "error":
                messages.mount(MessageWidget(f"[red]Error: {evt.error}[/red]", classes="error"))

        messages.scroll_end()
        self.query_one("#input", Input).disabled = False
        self.query_one("#input", Input).focus()

    async def _handle_command(self, cmd: str):
        messages = self.query_one("#messages", VerticalScroll)
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == "/help":
            messages.mount(MessageWidget(
                "[bold]Commands:[/bold]\n  /help - show this\n  /clear - clear conversation\n"
                "  /model - show model\n  /tokens - show usage\n  /quit - exit"
            ))
        elif command == "/clear":
            self.agent.state.messages.clear()
            await messages.remove_children()
            messages.mount(MessageWidget("[dim]Conversation cleared.[/dim]"))
        elif command == "/model":
            messages.mount(MessageWidget(f"Model: {self.agent.config.model.model}"))
        elif command == "/tokens":
            from tinyloom.core.compact import estimate_tokens_heuristic
            tokens = estimate_tokens_heuristic(self.agent.state.messages)
            window = self.agent.config.model.context_window
            pct = tokens / window * 100 if window else 0
            messages.mount(MessageWidget(f"Tokens: ~{tokens:,} / {window:,} ({pct:.0f}%)"))
        elif command == "/quit":
            self.exit()
        else:
            messages.mount(MessageWidget(f"[red]Unknown command: {command}[/red]"))


async def run_tui(agent: Agent):
    app = TinyloomApp(agent)
    await app.run_async()
