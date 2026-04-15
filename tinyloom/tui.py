from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, Input, Static
from textual.binding import Binding
from textual import work

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent


SPINNER_FRAMES = ["|", "/", "-", "\\"]
THINKING_VERBS = [
    "thinking", "pondering", "reasoning", "analyzing",
    "processing", "considering", "evaluating", "computing",
    "deliberating", "contemplating", "synthesizing", "cogitating",
    "ruminating", "musing", "reflecting", "deducing",
]


class MessageWidget(Static):
    pass


class SpinnerWidget(Static):
    """Animated ASCII spinner with random verbs shown while agent works."""

    def __init__(self):
        super().__init__("")
        self._frame = 0
        self._verb = random.choice(THINKING_VERBS)
        self._timer = None

    def on_mount(self):
        self._tick()
        self._timer = self.set_interval(0.15, self._tick)

    def _tick(self):
        frame = SPINNER_FRAMES[self._frame]
        self.update(f"[dim]{frame} {self._verb}...[/dim]")
        self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
        if self._frame == 0:
            self._verb = random.choice(THINKING_VERBS)

    def stop(self):
        if self._timer:
            self._timer.stop()
            self._timer = None


class TinyloomApp(App):
    CSS = """
    VerticalScroll { height: 1fr; }
    #input { dock: bottom; margin-bottom: 1; }
    .tool-call { color: green; }
    .tool-result { color: $text-muted; }
    .error { color: red; }
    .compaction { color: yellow; text-style: dim; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("escape", "stop_agent", "Stop"),
    ]

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent
        self.title = f"tinyloom - {agent.config.model.model}"
        self._spinner: SpinnerWidget | None = None
        self._plugin_tui = getattr(agent, "_subagent_tui", None)

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="messages")
        yield Input(placeholder="Type a message...", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        if self._plugin_tui:
            scroll_end = lambda: self.query_one("#messages", VerticalScroll).scroll_end()
            self._plugin_tui["on_mount"](scroll_end)

    def _show_spinner(self) -> None:
        if self._spinner is not None:
            return
        self._spinner = SpinnerWidget()
        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(self._spinner)
        messages.scroll_end()

    def _hide_spinner(self) -> None:
        if self._spinner is None:
            return
        self._spinner.stop()
        self._spinner.remove()
        self._spinner = None

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
        messages.scroll_end()

        self.query_one("#input", Input).disabled = True
        self._stream_response(user_input)

    def action_stop_agent(self) -> None:
        self._hide_spinner()
        if self._plugin_tui:
            self._plugin_tui["on_stop"]()
        self.workers.cancel_group(self, "default")
        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(MessageWidget("[yellow dim]Stopped.[/yellow dim]"))
        messages.scroll_end()
        inp = self.query_one("#input", Input)
        inp.disabled = False
        inp.focus()

    @work
    async def _stream_response(self, user_input: str) -> None:
        messages = self.query_one("#messages", VerticalScroll)
        text_buffer = ""
        text_widget: MessageWidget | None = None

        self._show_spinner()

        try:
            async for evt in self.agent.step(user_input):
                if evt.type == "text_delta":
                    self._hide_spinner()
                    if text_widget is None:
                        text_widget = MessageWidget("")
                        messages.mount(text_widget)
                    text_buffer += evt.text
                    text_widget.update(text_buffer)
                else:
                    # Finalize current text block so the next event appears below it
                    text_widget = None
                    text_buffer = ""

                    if evt.type == "tool_call":
                        self._hide_spinner()
                        tc = evt.tool_call
                        preview = str(tc.input)[:100]
                        messages.mount(MessageWidget(f"[green]> {tc.name}[/green]({preview})", classes="tool-call"))
                        if self._plugin_tui:
                            self._plugin_tui["on_tool_call"](tc, messages.mount)
                        self._show_spinner()
                    elif evt.type == "tool_result":
                        self._hide_spinner()
                        if self._plugin_tui:
                            self._plugin_tui["on_tool_result"](evt, messages.mount)
                        preview = evt.result[:200] if evt.result else "(empty)"
                        messages.mount(MessageWidget(f"[dim]  <- {preview}[/dim]", classes="tool-result"))
                        self._show_spinner()
                    elif evt.type == "compaction":
                        messages.mount(MessageWidget("[yellow dim]Context compacted[/yellow dim]", classes="compaction"))
                    elif evt.type == "error":
                        self._hide_spinner()
                        messages.mount(MessageWidget(f"[red]Error: {evt.error}[/red]", classes="error"))
                messages.scroll_end()
        except asyncio.CancelledError:
            self._hide_spinner()
            if self._plugin_tui:
                self._plugin_tui["on_stop"]()
            return

        self._hide_spinner()
        self.query_one("#input", Input).disabled = False
        self.query_one("#input", Input).focus()

    async def _handle_command(self, cmd: str):
        messages = self.query_one("#messages", VerticalScroll)
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == "/help":
            messages.mount(MessageWidget(
                "[bold]Commands:[/bold]\n  /help - show this\n  /clear - clear conversation\n"
                "  /model - show model\n  /tokens - show usage\n  /quit|exit - exit\n\nStop any agent loop by pressing 'esc' key anytime."
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
        elif command == "/quit" or command == "/exit":
            self.exit()
        else:
            messages.mount(MessageWidget(f"[red]Unknown command: {command}[/red]"))

async def run_tui(agent: Agent):
    app = TinyloomApp(agent)
    await app.run_async()
