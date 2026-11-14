"""Verify only the two completed-merge lists moved out of the handoff."""
from collections import Counter
from pathlib import Path
import subprocess

BASE = '95ed6ac0fd6d65bcc7646b4f4f7f77f55ae8ea71'
source = subprocess.check_output(['git', 'show', f'{BASE}:ops/HANDOFF.md'])
archive = Path('ops/archive/HANDOFF-2026-11-04.md').read_bytes()
current = Path('ops/HANDOFF.md').read_bytes()
assert archive == source, 'Original handoff changed'
removed = Counter(source.splitlines(keepends=True)) - Counter(current.splitlines(keepends=True))
assert not (removed - Counter(archive.splitlines(keepends=True)))
allowed = (b'- Latest merges (older ones are in LOG):', b'- Merged into `next` since the last refresh:')
assert sum(removed.values()) == 2
assert all(line.startswith(allowed) for line in removed), 'Active instruction removed'
assert len(current.splitlines()) < 60
assert b'archive/HANDOFF-2026-11-04.md' in current
print('PASS: exact archive, only two completed-merge lists removed, under 60 lines')
