"""Check archival coverage and verbatim preservation of hard requirements."""
from collections import Counter
from pathlib import Path
import subprocess

BASE = '95ed6ac0fd6d65bcc7646b4f4f7f77f55ae8ea71'
for name in ['CLAUDE.md', 'ops/AGENTS.md']:
    source = subprocess.check_output(['git', 'show', f'{BASE}:{name}'])
    archive = Path('ops/archive') / (Path(name).stem + '-before-context-2026-11-04.md')
    assert archive.read_bytes() == source, f'Archive changed: {name}'
    removed = Counter(source.splitlines(keepends=True)) - Counter(Path(name).read_bytes().splitlines(keepends=True))
    assert not (removed - Counter(archive.read_bytes().splitlines(keepends=True)))
old_claude = subprocess.check_output(['git', 'show', f'{BASE}:CLAUDE.md']).decode()
new_claude = Path('CLAUDE.md').read_text()
assert old_claude[old_claude.index('## Hard rules'):].strip() in new_claude
old_agents = subprocess.check_output(['git', 'show', f'{BASE}:ops/AGENTS.md']).decode()
new_agents = Path('ops/AGENTS.md').read_text()
for title in ['Flow', 'Size budgets (Steward enforces)', 'Limits']:
    start = old_agents.index('## ' + title)
    end = old_agents.find('\n## ', start + 1)
    section = old_agents[start:end if end != -1 else len(old_agents)].strip()
    assert section in new_claude
assert old_agents[:old_agents.index('## Context hygiene')] in new_agents
assert old_agents[old_agents.index('## Sessions (current)'):].strip() in new_agents
assert 'if RULES is absent' in new_agents
assert 'Until it exists' in new_claude
print('PASS: exact archives; hard rules, role/session tables and QA verbatim; independent fallback')
