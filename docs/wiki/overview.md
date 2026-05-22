# Overview

Graphify turns project files into a queryable knowledge graph with report, JSON, dashboard, and optional generated wiki outputs.

The project should keep curated context in `docs/wiki` and generated context in `graphify-out`. This keeps human-maintained project truth separate from rebuildable analysis artifacts.

## Current Focus

- Make terminal-first graph generation reliable.
- Keep assistant integrations aligned with current agent runtimes.
- Bridge generated graph context into durable memory through explicit digest exports.
