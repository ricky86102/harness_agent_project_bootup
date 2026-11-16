# Host Policies

## Current State

Owner of host selection and shared skill/MCP defaults. Read only the active host's policy.

| Host | Policy |
| --- | --- |
| Claude Code | [Claude](claude.md) |
| Codex | [Codex](codex.md) |

- Resolve shared roles from [Model Routing](../model-routing.md) through the selected policy.
- For an unlisted host, keep work in the session model until an explicit role mapping is supplied.
- Use task-relevant installed skills and connected MCP tools within the user's authorization and effective host permissions.
- Read the selected skill before using it; tool availability grants no additional action permission.
- This scaffold installs no MCP server or blanket approval rule.
- Register new host policies in this index and `tools/check_docs.py`; keep the AGENTS trigger unchanged.

## Records
