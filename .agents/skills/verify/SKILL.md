---
name: verify
description: A compact, sequential workflow for applying code modifications and executing testing checks. Call this when you want to edit and test safely.
---

# Operational Steps

1. Review the targeted code section specified by the user.
2. Present a minimalist, raw Git diff plan of the change.
3. Pause and wait explicitly for user confirmation before writing files.
4. Apply modifications.
5. Execute `npm test` (or the workspace equivalent test framework command) exactly once.