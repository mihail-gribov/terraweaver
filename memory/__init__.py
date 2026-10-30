"""The user's personal memory, an active one: it hears the conversation, keeps the user's words,
reads them into topics, portraits and the user's world in the quiet, and answers the agent with facts.

    server.py    the two doors over MCP and HTTP: `say` (hooks pass every message) and `ask`
    listen.py    what the memory does with what it hears: keep, put beside, note an interest
    intake/      one message read with the agent's message before it (Nemotron, prompts/)
    journal.py   the journal of facts in the user's words, numbered and dated
    graph.py     what the journal is read into: entities, links, topics, portraits, the user's world
    search.py    the entries a question needs, by words and by meaning
    models.py    which Nemotron plays which role; nemotron.py is the client, the decision model too
"""
