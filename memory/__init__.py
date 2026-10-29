"""The user's personal memory, an active one: it hears the conversation, keeps the user's words,
reads and structures them in the quiet, and answers the agent with facts.

    server.py    the two doors over MCP and HTTP: `say` (hooks pass every message) and `ask`
    listen.py    what the memory does with what it hears: keep, put beside, note an interest
    intake/      one message read with the agent's message before it (Nemotron, prompts/)
    journal.py   the journal of facts in the user's words, numbered and dated
    world.py     the world reads the journal in the quiet into things, values and links
    model.py     the structure those are kept in; search.py finds by structure, words, meaning
    solve.py     a task solved by a program the model writes or reuses (programs.py, tools.py)
    parse.py     reading a text into values and links, each checked by the decision model
    models.py    which Nemotron plays which role
    cleaner.py   what was found lives a TTL (ttl.py) from its last use
"""
