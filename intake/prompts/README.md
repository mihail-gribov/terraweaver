# Intake prompts

Every prompt the intake (`intake/intake.py`) sends, one file each, read at import.

| file | to | shape |
|---|---|---|
| `conversation.txt` | both | the line above the numbered messages |
| `for_memory.txt` | decision model, `noul` | line 1 the question, line 2 the yes option, line 3 the no option |
| `resolve_system.txt`, `resolve.txt` | big Nemotron, `say` | the agent's message and the user's in `{conversation}`; out JSON: new topic, the message rewritten to stand alone, its questions |
| `same_question.txt` | decision model, `noul` | as `for_memory.txt` |
| `kinds.txt` | decision model, `choice` | line 1 the question, then `key: description` per option |
