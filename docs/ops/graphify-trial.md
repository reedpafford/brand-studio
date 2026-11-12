# Local code-navigation trial

Status: optional trial, not a replacement for the read schedule or QA. No application
code, prompts, models, paid providers or V6 design files change.

## Use

```sh
python3 scripts/graphify_local.py setup
python3 scripts/graphify_local.py build
python3 scripts/graphify_local.py query "nested folder move parent cycle"
```

The project skill `code-map` describes when this is useful. It loads on demand;
no global skill, hook, MCP server, search restriction or CLAUDE.md rewrite is installed.
Existing sessions need not restart to use the CLI. Other workspaces must first
receive this change and run their own setup/build; this trial does not change them.

Graphify 0.9.102 runs in an isolated environment. Code-only extraction uses local
parsers, with the model backend explicitly disabled. The wrapper copies only
current tracked and unignored Python, TypeScript, JavaScript and SQL under
server/app, server/tests, web/src and web/e2e. Generated schema.d.ts is excluded.
Markdown, design boards, documents, credentials and environment files are not inputs.

Each workspace owns its generated snapshot and graph under `.context/graphify-local/`.
The query checks workspace path, branch, commit and source-content hashes against
the build manifest. A changed source or revision requires a rebuild or ordinary
search. It also checks for changes during the build. All source locations refer
to the workspace's original relative paths, not an authority separate from source.

The query depth is one, its default requested budget is 1,200 estimated tokens,
and the wrapper additionally caps displayed text at four characters per requested
token, plus its omission notice. This character limit is not an exact tokenizer.
The upstream tool can exceed its requested budget when retaining edges.

## Observed trial, 4 November 2026

Indexed isolated checkouts, leaving active workspaces untouched:

| Revision | Source files | Nodes | Edges |
|---|---:|---:|---:|
| main, 95ed6ac0 | 401 | 4,838 | 20,575 |
| next, 2ebe1e69 | 705 | 9,849 | 41,609 |

No LLM extraction ran. Both builds reported partial parsing of AssetCard.tsx.
On next, 27 code files produced no symbols, including browser-test files. This is
an index limitation, not evidence that the application has syntax errors.

Three retrieval smoke questions on next, before adding the wrapper's output cap:

| Topic | Graph output characters | Source-search characters | Observation |
|---|---:|---:|---|
| Character sheet approval before storyboard | 4,265 | 881 for `frame_problems` | Found storyboard.py and sheet tests; graph truncated |
| Director run price and remake budget | 4,326 | 3,702 for `run_price` | Found director/estimate files; graph truncated |
| Nested folder move and parent cycle | 16,187 | 107,103 for broad `move` | Found folder routes/model/UI; graph exceeded its requested budget |

These are different retrieval methods, not an apples-to-apples task-token benchmark:
the exact-symbol searches assume a known name, and the broad `move` baseline is
deliberately unspecific. A better scoped search could be much shorter. Query wall
time was 0.58–0.71 seconds. File-location relevance was checked, but no completed
coding-task accuracy or total model-token savings is claimed.

Conclusion: retain ordinary search for exact symbols. Try the graph for unfamiliar
cross-file relationships. Read the actual source and tests afterward. If the result
is truncated, ambiguous or unhelpful, narrow it or switch to source search.

## Quality and rollout gates

- Keep #1336, #1337 and #1338 as separate changes with their preservation checks.
- Mandatory product rules, applicable approved V6 specifications, user decisions,
  prompts and QA remain authoritative and must still be read when required.
- A graph hit does not prove an implementation is correct or a requirement absent.
- Before wider adoption, compare the same representative tasks at the same revision,
  with the same model and acceptance criteria, with and without the graph. Include
  setup/query/source-read overhead, elapsed time, missed requirements and full results.
- Fresh-agent quality comparison and the efficiency PRs' semantic QA remain pending.
  Retrieval smoke tests do not satisfy those gates.

To stop using it, use normal source search; no service or hook needs disabling.
Reverting this PR removes the optional entry points. Generated local data is ignored
and may be retained. No product state depends on it.

Upstream: https://github.com/Graphify-Labs/graphify
