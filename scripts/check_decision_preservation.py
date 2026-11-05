"""Prove the history split preserves original bytes and every current-rule clause."""
from collections import Counter
from pathlib import Path
import re
import subprocess

BASE = '95ed6ac0fd6d65bcc7646b4f4f7f77f55ae8ea71'
source = subprocess.check_output(['git', 'show', f'{BASE}:ops/DECISIONS.md'])
archive = Path('ops/archive/DECISIONS-2026-11-04.md').read_bytes()
assert archive == source, 'Original DECISIONS bytes changed'
old = source.decode()
current = old[old.index('## Current rules'):old.index('## History')]
rules = Path('ops/RULES.md').read_text()
assert current in rules, 'Current-rule wording, exceptions or sub-bullets changed'
assert re.findall(r'^(\d+)\. ', current, re.M) == [str(i) for i in range(1, 36)]
removed = Counter(source.splitlines(keepends=True)) - Counter(Path('ops/DECISIONS.md').read_bytes().splitlines(keepends=True))
assert not (removed - Counter(archive.splitlines(keepends=True))), 'Removed lines missing from archive'
print('PASS: exact archive, all 35 rules verbatim, every removed line archived')
