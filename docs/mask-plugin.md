# Mask Plugin

Replaces sensitive words with asterisks in TUI output. Useful for recordings, demos, or screen sharing.

## Setup

Add to your `tinyloom.yaml`:

```yaml
plugins:
  - tinyloom.plugins.mask

mask_words:
  - myusername
  - /Users/myusername
  - my-company
```

Any occurrence of these strings in text output, tool calls, or tool results will be replaced with `*` characters of the same length.

## Environment Variable

You can also set words via the `TINYLOOM_MASK` environment variable (comma-separated):

```bash
TINYLOOM_MASK="myusername,/Users/myusername" tinyloom
```

Both sources combine — env var words and config words are all masked.

## How It Works

The mask plugin registers a text filter on the TUI's generic `_tui_text_filters` pipeline. Any plugin can add filters to this pipeline — mask is just one example. Filters are `str -> str` callables that run in order on every piece of displayed text.

## Recording Demos

Combine with [VHS](https://github.com/charmbracelet/vhs) for clean terminal recordings:

```bash
TINYLOOM_MASK="$(whoami),$(echo $HOME)" vhs demo.tape
```
