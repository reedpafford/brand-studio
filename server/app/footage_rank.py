"""Which of a brand's clips fit a video, and the director's search of them (Reed's PG brand:
about 985 clips in folders, most of no product: "clips of no product, the first 6" was any 6).
Free and in code, never an AI call. A drawn style (every one but UGC and Movie) is given the
brand's product clips only, as a reference for how each product looks and works (Reed): no
people or places footage, and so no other clip as a Seedance reference video. A real-looking
style is given the clips that fit best: those of a product the video names first (half the
list at most), then by the words a clip shares with the script, goal and name (BM25, the usual
word-search score: a rare word both share counts most), its words being its description, file
name and folder path (a folder's name, "Church" or "Campus", counts FOLDER times); with no
words shared, the brand's product clips, then one clip from each folder in turn, never just
the oldest. Clips whose folder or file name says animation are pushed down there (and are
never a real footage shot: `animated`). A competitor's clip is never given as the brand's
(`usable`); it is named, as what never to show as ours, only to a script that compares
(`rivals`). A near copy of a clip already chosen is left out. The same words give the same
clips, so a video's <footage> stays put from step to step (its treatment isn't read: it is
rewritten during a run). The director may find another clip by words (`find_footage`, when
none listed fits a shot): those go first. Folder paths and the ranking are worked out once a
transaction (`_cached`), not once a clip."""

import math
import re
from collections import Counter

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.files import MediaUpload, StoredFile
from app.models.folders import Folder
from app.models.projects import Project

STOP = frozenset(
    "a an and are as at be been but by can could did do does for from had has have he her "
    "here him his how i if in into is it its just me my no not of on or our out over she so "
    "than that the their them then there these they this those to too up us was we were what "
    "when where which who why will with would you your mp4 mov m4v img".split()
)  # fmt: skip
SHOT = frozenset("wide close closeup medium shot angle drone aerial timelapse time lapse slow pan "
                 "tilt zoom track handheld pov overhead static cu ws ms 4k hd broll b roll take "
                 "version alt".split())  # fmt: skip  # how it's filmed: not what it shows
FOLDER = 2  # a folder name's words count this many times: "Church", "Campus", "PalaceGuard"
REAL = ("ugc", "movie")  # the real-looking styles; every other is drawn
STYLE = 0.3  # in a real-looking style, a clip named as animation loses this share of the best
SAME, KIN = 0.8, 0.5  # alike past this (Jaccard of what it shows): a near copy; in one folder
FOUND, PINNED = 3, 4  # clips one search gives, and how many found ones <footage> keeps
K1, B = 1.2, 0.75  # BM25's usual constants
CACHE = "footage_rank"  # in a session's info: paths and rankings, until it commits


def words(text: str) -> list[str]:
    """Search words: "PalaceGuard_church-doors.MOV" -> palace, guard, church, door."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    text = re.sub(r"['’]s\b", "", text).lower()  # "competitor's", "it's": no stray "s"
    out = []
    for w in re.findall(r"[a-z0-9]+", text):
        if w in STOP or w.isdigit() or len(w) < 2:
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


DRAWN = frozenset(words("animation animated cartoon pixar graphic 2d 3d cgi render illustrated "
                        "illustration anime"))  # fmt: skip  # stemmed, as words() reads
ANIMATED = frozenset(words("animation animated pixar cartoon"))  # never a real footage shot
OTHER = frozenset(words("other another cheap cheaper cheapest generic ordinary regular typical "
                        "normal old knockoff"))  # fmt: skip  # "cheap alarms": it compares
RIVAL = frozenset(words("competitor rival knockoff amazon"))
KINDS = frozenset(words("brands ones products kinds models"))  # "other brands", "cheap ones"
NOT_THINGS = frozenset(words(
    "people person man men woman women guy girl boy kid child children friend family mom dad "
    "brother sister neighbour neighbor night day morning evening week month year time way thing "
    "place side hand world life"))  # fmt: skip  # "the other night", "my old friend"
RIVALS = "Competitor products (never show as ours): "  # the one line a comparing script gets


def _cached(db: Session, key: tuple, make):
    box = db.info.setdefault(CACHE, {})
    if key not in box:
        box[key] = make()
    return box[key]


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _forget(session, *_) -> None:
    session.info.pop(CACHE, None)


def paths(db: Session, brand_id: int) -> dict[int, str]:
    """Each footage folder's live path ("Church/Exterior"), in one query: a clip in a deleted
    folder reads as the first live one it's inside (Filed.live_folder_id), "" at the top."""

    def make() -> dict[int, str]:
        rows = {f.id: f for f in db.scalars(select(Folder).where(Folder.brand_id == brand_id,
                                                                 Folder.footage))}  # fmt: skip
        out = {}
        for fid in rows:
            at = rows.get(fid)
            while at is not None and at.deleted_at is not None:
                at = rows.get(at.parent_id)
            names = []
            while at is not None and at.deleted_at is None:
                names.append(at.name)
                at = rows.get(at.parent_id)
            out[fid] = "/".join(reversed(names))
        return out

    return _cached(db, ("paths", brand_id), make)


def _names(db: Session, rows: list[MediaUpload]) -> list[list[str]]:
    """Each clip's file name and folder path (FOLDER times): what the brand calls it."""
    names = dict(db.execute(select(StoredFile.id, StoredFile.filename).where(
        StoredFile.id.in_({r.file_id for r in rows}))).all())  # fmt: skip
    where = paths(db, rows[0].brand_id) if rows else {}
    told = {f: words(p) * FOLDER for f, p in where.items()}
    return [words(names.get(r.file_id, "")) + told.get(r.folder_id, []) for r in rows]


def _texts(db: Session, rows: list[MediaUpload], names=None) -> list[list[str]]:
    """Each clip's words: description, then its names."""
    names = names or _names(db, rows)
    return [words(r.description) + n for r, n in zip(rows, names, strict=True)]


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


def _shows(row: MediaUpload) -> set[str]:
    return set(words(row.description)) - SHOT


def _copy(a: MediaUpload, b: MediaUpload) -> bool:
    """What they show (how it's filmed aside) is more alike than SAME, or KIN in one folder."""
    x, y = _shows(a), _shows(b)
    most = KIN if a.folder_id and a.folder_id == b.folder_id else SAME
    return bool(x and y) and len(x & y) / len(x | y) > most


def _distinct(rows: list[MediaUpload], most: int, kept=()) -> list[MediaUpload]:
    """The first `most` of `rows` (in their order) that aren't near copies of one kept."""
    out = list(kept)
    for r in rows:
        if len(out) >= most:
            break
        if r not in out and not any(_copy(r, k) for k in out):
            out.append(r)
    return out


def drawn(project: Project) -> bool:
    """A drawn style (every one but UGC and Movie): its footage is product clips only."""
    from app import looks

    return looks.base(looks.drawn(project)) not in REAL


def _key(text: str) -> str:
    return "".join(words(text))


def named(db: Session, project: Project, query: str) -> set[int]:
    """The brand's products the words name, any case or spacing ("Palace Guard" names
    PalaceGuard); a brand of one product is also named by its own name or the initials of
    either ("PG")."""
    from app.footage import products
    from app.models.brands import Brand

    have, said = products(db, project.brand_id), words(query)
    runs = {"".join(said[i:j]) for i in range(len(said)) for j in range(i + 1, i + 5)}
    out = set()
    for p in have:
        names = {_key(p.name)}
        if len(have) == 1:
            brand = db.get(Brand, project.brand_id).name
            names |= {_key(brand), *("".join(w[0] for w in words(n)) for n in (brand, p.name)
                                     if len(words(n)) > 1)}  # fmt: skip
        if names & runs - {""}:
            out.add(p.id)
    return out


def usable(db: Session, project: Project) -> list[MediaUpload]:
    """The brand's described clips this video may be given: its own (never a competitor's), of
    no product or one of its products now; in a drawn style, product clips only."""
    from app.footage import live, products

    have, only = {p.id for p in products(db, project.brand_id)}, drawn(project)
    return [r for r in live(db, project.brand_id) if r.description.strip() and not r.competitor
            and (r.product_id in have or r.product_id is None and not only)]  # fmt: skip


def animated(db: Session, row: MediaUpload) -> bool:
    """Its folder or file name says animation, Pixar or cartoon: never a real shot (its
    description doesn't count: "an animated crowd" is real)."""
    return bool(ANIMATED.intersection(_names(db, [row])[0]))


def rivals(db: Session, project: Project, most: int = 3) -> str:
    """One line of the competitor clips that best fit, in their words with no id (never a shot
    or a reference), only when the script, goal or name talks about others: a competitor, a
    knock-off, Amazon, or "other", "cheap" or "old" just before "brands", "ones" or a thing
    those clips say ("other alarms", never "the other night"). "" otherwise: left out."""
    from app.enhance import escape
    from app.footage import live
    from app.routes.scripts import latest

    rows = [r for r in live(db, project.brand_id) if r.competitor and r.description.strip()]
    script = latest(db, project)
    text = " ".join((script.text if script else "", project.goal or "", project.name or ""))
    said = words(re.sub(r"(?i)knock[\s-]+off", "knockoff", text))
    if not rows or not said:
        return ""
    docs = _texts(db, rows)
    things = KINDS | set().union(*docs) - SHOT - OTHER - NOT_THINGS
    near = any(w in OTHER and n in things for w, n in zip(said, said[1:], strict=False))
    if not (near or RIVAL.intersection(said)):
        return ""
    score = _bm25(docs, said)
    best = sorted(range(len(rows)), key=lambda i: (-score[i], rows[i].id))[:most]
    return RIVALS + "; ".join(escape(" ".join(rows[i].description.split()))[:160] for i in best)


def fit(db: Session, project: Project, most: int) -> list[MediaUpload]:
    """The `most` clips that fit this video best (the module's docstring), once a transaction
    for the same words and style."""
    from app import looks
    from app.routes.scripts import latest

    script = latest(db, project)
    query = " ".join((script.text if script else "", project.goal or "", project.name or ""))
    key = ("fit", project.id, looks.drawn(project), query, most)
    return _cached(db, key, lambda: _fit(db, project, query, most))


def _fit(db: Session, project: Project, query: str, most: int) -> list[MediaUpload]:
    mine = named(db, project, query)
    every = usable(db, project)
    rows = [r for r in every if not mine or r.product_id in (None, *mine)]
    names = _names(db, rows)
    docs = _texts(db, rows, names)
    score = _bm25(docs, words(query))
    lift = STYLE * (max(score, default=0) or 1)
    for i, n in enumerate(names):  # named as cartoon footage, in a real look
        if not drawn(project) and DRAWN.intersection(n):
            score[i] -= lift
    turn, seen = {}, Counter()  # no words shared: one clip from each folder in turn
    for i in sorted(range(len(rows)), key=lambda i: rows[i].id):
        turn[i] = seen[rows[i].folder_id]
        seen[rows[i].folder_id] += 1
    tier = [0 if s > 0 else 1 if r.product_id else 2 if s == 0 else 3
            for s, r in zip(score, rows, strict=True)]  # fmt: skip
    ranks = sorted(range(len(rows)), key=lambda i: (tier[i], -score[i], turn[i], rows[i].id))
    order = [rows[i] for i in ranks]
    have = {r.id: r for r in every}
    pins = [have[i] for i in found(db, project) if i in have][:PINNED]
    first = _distinct([r for r in order if r.product_id in mine], len(pins) + most // 2, pins)
    return _distinct(order, most, first)


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
    """`find_footage`: the clips this video may be given that best match the words, free; they
    join <footage> for the steps that follow. In plain words, as the director's log shows it."""
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
        of = "product clips" if drawn(project) else "clips"
        return (f"Found none of the brand's {len(rows)} {of} for “{asked}”: try other words "
                "(a place, an action, a folder's name).")  # fmt: skip
    return "\n".join([f"Found for “{asked}”, now in <footage> for the steps that follow:",
                      *(line(db, r) for r in hits)])  # fmt: skip
