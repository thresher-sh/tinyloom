# tinyloom

Extremely Tiny Agent...

## Why this exists

We needed an extremely tiny harness for https://github.com/thresher-sh/thresher and many harnesses just bring extra bloat we don't need. The harness bit is actually easy to implement, it's all the extra bells and whistles that take a lot.

If you are looking for a bigger client, take a look at one of these ones:

- https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent
- https://github.com/anomalyco/opencode

We added a bit of configuration just to make some tasks easier, but for the most part it's let the model drive given a good set of bash tools. I bet if we just gave it bash it could figure it out because it could cat for read, sed/awk/echo/touch etc... But we are giving a few tools just to make it easier.

We also wanted python, cause it's what we are most familiar with and can hold the AI and stuff accountable while building. And we can bring it in as a library into our own systems as an sdk vs just commandline execution.

## Extra features

Want extra features?

- Add tools via mcp
- Add extensions via plugin system
- Add logic via hooks

You can build what your heart desires... For us.. we just want tools, loop, no permissions, go to town boss agent.

## Models

We support anthropic and openai endpoints. Most model providers offer that.. Configure your stuff in `tinyloom.yaml`. Don't know how? Ask your coding agent how.