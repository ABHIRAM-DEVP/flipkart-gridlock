---
name: token-saver
description: Constraints to enforce extreme token-efficiency and stop autonomous looping. Use this always.
---

# Execution Guardrails

- **Zero Fluff:** Move directly to code generation. Do not generate introductory explanations, generic apologies, or pleasantries.
- **Strict File Bounds:** Do not read or scan files outside of those explicitly mentioned in the active user prompt. If a line range is provided, only inspect that range.
- **Single-File Changes:** Solve tasks in the single most relevant component first. Do not chain refactors across multiple files unless it is mathematically impossible to resolve the task without doing so.
- **No Mock Re-generation:** If test suites or UI states require mock data, use existing mock structures. Do not rewrite or expand dummy arrays.