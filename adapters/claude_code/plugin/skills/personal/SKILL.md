---
name: personal
description: Enter or leave the user's personal world for this session. `/personal` turns it on, `/personal off` turns it off.
disable-model-invocation: true
argument-hint: "[off]"
---

The user ran `/personal $ARGUMENTS`. The mode itself is switched by the plugin's hook, and what
it changed is in your context next to this message. Confirm it to the user in one short line —
in the personal world, or out of it — and carry on with whatever they ask next.
