"""Which of a brand's clips fit a video, and the director's search of them (Reed's PG brand:
about 985 clips in folders, most of no product: "clips of no product, the first 6" was any 6).
Free and in code, never an AI call. A clip's words are its description, its file name and its
folder path (a folder's name, "Church" or "Campus", counts FOLDER times); they are scored
against the video's script, goal and name by BM25, the usual word-search score: a rare word
both share counts most. The clips of a product the script names come first; an animated style
leans to clips whose words say animation (a soft lift, never a rule), a realistic one away
from them; a near copy of a clip already chosen is left out. The same words give the same
clips, so a video's <footage> stays put from step to step (its treatment isn't read: it is
rewritten during a run). The director finds any other clip by words (`find_footage`): the
ones it found go first in <footage> for the steps that follow."""

import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.files import MediaUpload, StoredFile
from app.models.projects import Project

STOP = frozenset(
    "a an and are as at be been but by can could did do does for from had has have he her "
    "here him his how i if in into is it its just me my no not of on or our out over she so "
    "than that the their them then there these they this those to too up us was we were what "
    "when where which who why will with would you your mp4 mov m4v img".split()
)  # fmt: skip
FOLDER = 2  # a folder name's words count this many times: "Church", "Campus", "PalaceGuard"
DRAWN = frozenset({"animation", "animated", "cartoon", "graphic", "2d", "3d", "cgi", "render",
                   "illustrated", "illustration", "anime"})  # fmt: skip
REAL = ("ugc", "movie")  # the photoreal styles; every other is drawn or animated
STYLE = 0.3  # a clip that fits the style gains this share of the best text score (or loses it)
SAME = 0.8  # description words this alike (Jaccard): one clip twice, the later one left out
FOUND, PINNED = 3, 4  # clips one search gives, and how many found ones <footage> keeps
K1, B = 1.2, 0.75  # BM25's usual constants


def words(text: str) -> list[str]:
    """Search words: "PalaceGuard_church-doors.MOV" -> palace, guard, church, door."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "").lower()
    out = []
    for w in re.findall(r"[a-z0-9]+", text):
        if w in STOP or w.isdigit():
            continue
        if w.endswith(("ies", "ied")) and len(w) > 4:  # studies, studied: study
            w = w[:-3] + "y"
        elif w.endswith("ing") and len(w) > 5:  # walking: walk
            w = w[:-3]
        elif w.endswith("ed") and len(w) > 4:  # prayed: pray
            w = w[:-2]
        elif w.endswith(("ches", "shes", "sses", "xes")):
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return out


def _texts(db: Session, rows: list[MediaUpload]) -> list[list[str]]:
    """Each clip's words: description, file name, folder path (FOLDER times)."""
    from app import folders

    names = dict(db.execute(select(StoredFile.id, StoredFile.filename).where(
        StoredFile.id.in_({r.file_id for r in rows}))).all())  # fmt: skip
    paths: dict[int | None, list[str]] = {}
    out = []
    for r in rows:
        where = r.live_folder_id
        if where not in paths:
            paths[where] = words(folders.path(db, where))
        out.append(words(r.description) + words(names.get(r.file_id, "")) + paths[where] * FOLDER)
    return out


def _bm25(docs: list[list[str]], query: list[str]) -> list[float]:
    """Each doc's BM25 score for the query; a word the query says often counts a little more."""
    if not docs or not query:
        return [0.0] * len(docs)
    n, avg = len(docs), (sum(map(len, docs)) / len(docs)) or 1
    df = Counter(w for d in docs for w in set(d))
    asked = Counter(query)
    scores = []
    for d in docs:
        tf, s = Counter(d), 0.0
        for w, q in asked.items():
            if f := tf.get(w):
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += (idf * f * (K1 + 1) / (f + K1 * (1 - B + B * len(d) / avg))
                      * (1 + math.log(q)))  # fmt: skip
        scores.append(s)
    return scores


def _alike(a: set[str], b: set[str]) -> bool:
    return bool(a and b) and len(a & b) / len(a | b) >= SAME


def _distinct(rows: list[MediaUpload], most: int, kept=()) -> list[MediaUpload]:
    """The first `most` of `rows` (in their order) that aren't near copies of one kept."""
    out, seen = list(kept), [set(words(r.description)) for r in kept]
    for r in rows:
        if len(out) >= most:
            break
        mine = set(words(r.description))
        if r not in out and not any(_alike(mine, s) for s in seen):
            out.append(r)
            seen.append(mine)
    return out


def _style(project: Project) -> int:
    """+1 for an animated or drawn style, -1 for a photoreal one."""
    from app import looks

    return -1 if looks.base(looks.drawn(project)) in REAL else 1


def usable(db: Session, project: Project) -> list[MediaUpload]:
    """The brand's described clips, of no product or one of its products now."""
    from app.footage import live, products

    have = {p.id for p in products(db, project.brand_id)}
    return [r for r in live(db, project.brand_id) if r.description.strip()
            and (r.product_id is None or r.product_id in have)]  # fmt: skip


def fit(db: Session, project: Project, most: int) -> list[MediaUpload]:
    """The `most` clips that fit this video best: the ones the director found, then those of a
    product its script, goal or name names (at most half, so places and actions keep room; a
    clip of another product isn't given), then by score."""
    from app.footage import products
    from app.routes.scripts import latest

    script = latest(db, project)
    query = " ".join((script.text if script else "", project.goal or "", project.name or ""))
    named = {p.id for p in products(db, project.brand_id)
             if p.name.strip().lower() in query.lower()}  # fmt: skip
    every = usable(db, project)
    rows = [r for r in every if not named or r.product_id in (None, *named)]
    docs = _texts(db, rows)
    score = _bm25(docs, words(query))
    lift, style = STYLE * (max(score, default=0) or 1), _style(project)
    for i, d in enumerate(docs):
        if DRAWN.intersection(d):
            score[i] += style * lift
    order = sorted(range(len(rows)), key=lambda i: (-score[i], rows[i].id))
    have = {r.id: r for r in every}
    pins = [have[i] for i in found(db, project) if i in have][:PINNED]
    mine = [rows[i] for i in order if rows[i].product_id in named]
    first = _distinct(mine, len(pins) + most // 2, pins) if mine else pins
    return _distinct([rows[i] for i in order], most, first)


def found(db: Session, project: Project) -> list[int]:
    """The clips the director found in this run (`find_footage`), newest search first."""
    from app.director import turns
    from app.footage import KEY

    out: list[int] = []
    for j in reversed(turns(db, project)):
        if (j.output or {}).get("tool") == "find_footage":
            for n in re.findall(rf"^- {KEY}(\d+) ", j.input.get("result") or "", re.M):
                if int(n) not in out:
                    out.append(int(n))
    return out


def search(db: Session, project: Project, asked: str) -> str:
    """`find_footage`: the brand's clips that best match the words, free; they join <footage>
    for the steps that follow. In plain words, as the director's log shows it."""
    from app.footage import line

    asked = " ".join(asked.split())[:200]
    if not words(asked):
        return "Refused: say what to find in a few words, e.g. 'church exterior at night'."
    rows = usable(db, project)
    score = _bm25(_texts(db, rows), words(asked))
    hits = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (-score[i], rows[i].id))
            if score[i] > 0]  # fmt: skip
    hits = _distinct(hits, FOUND)
    if not hits:
        return (f"Found none of the brand's {len(rows)} clips for “{asked}”: try other words "
                "(a place, an action, a folder's name).")  # fmt: skip
    return "\n".join([f"Found for “{asked}”, now in <footage> for the steps that follow:",
                      *(line(db, r) for r in hits)])  # fmt: skip
