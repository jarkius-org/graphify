# Context Layers

Graphify should reduce context confusion, not create another competing memory pile.

## Ownership Model

| Layer | Path | Owner | Write Rule |
| --- | --- | --- | --- |
| Project truth | `docs/wiki`, `README.md`, `ARCHITECTURE.md` | Project repo | Curated edits only |
| Generated graph context | `graphify-out/` | Graphify | Rebuildable output |
| Generated graph navigation | `graphify-out/wiki` | Graphify | Rebuilt by `graphify --wiki` |
| Local search cache | `.llmwiki/` | core-llmwiki | Rebuildable cache |
| Durable memory | `~/.oracle-vault` | Oracle Vault | Append curated digests, retrospectives, and lessons |
| Retrieval accelerator | Arra/Psi | Runtime memory tooling | Index promoted memory, never become the only copy |
| Legacy compatibility | repo-local `ψ/` | Project-specific | Use only when a project explicitly depends on it |

## Rules

- docs/wiki is curated project truth.
- graphify-out/wiki is generated graph navigation.
- `.llmwiki/` is disposable local cache and should be rebuilt per machine.
- `~/.oracle-vault` stores durable cross-session memory, not project source files.
- Arra/Psi may index or mirror promoted digests, but the markdown digest remains canonical.
- Do not make agents choose between multiple "wikis"; route by layer purpose.

## Promotion Flow

1. Maintain durable project facts in `docs/wiki`.
2. Run Graphify to produce `graphify-out/graph.json`, `GRAPH_REPORT.md`, and generated graph wiki.
3. Export a digest into `~/.oracle-vault/psi/memory/projects/<project>/`.
4. Optionally index the digest with Arra/Psi for faster retrieval.

## Non-Goals

- Do not move generated graph pages into `docs/wiki`.
- Do not commit `.llmwiki/` caches.
- Do not store application source, PRDs, or deployment runbooks in Oracle Vault unless they are intentionally cross-project.
