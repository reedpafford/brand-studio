"""A shot's figure written onto its real brand screen (Reed, 30 Oct): the breakdown gives the
shot's `screen_figure` (its balance and its gain or loss, from the story), and the screen
goes to the model with that figure drawn in, so the money on screen is the story's. Only
screens with a `figure_spot` (where their number sits) are drawn on; a product never is,
and a shot with no figure gets the plain screen. Drawn when the picture is sent (the job
carries the figure), so an edited breakdown shows on the next take. Free: PIL, no paid call."""

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).parent / "fonts" / "Inter-SemiBold.otf"
WHITE, GREEN, RED = (255, 255, 255), (87, 200, 96), (235, 77, 75)


def shot_figure(screen, shot: dict) -> dict | None:
    """What to draw on `screen` for this shot (a breakdown shot, as saved), or None: only on
    the first screen the shot shows, only on a real screen with a spot, only with a figure."""
    figure = shot.get("screen_figure") or {}
    if not (figure.get("balance") or figure.get("change")):
        return None
    if screen.product or not screen.figure_spot:
        return None
    if (shot.get("screen_ids") or [None])[0] != f"screen:{screen.id}":
        return None
    return {"spot": screen.figure_spot, "balance": figure.get("balance") or "",
            "change": figure.get("change") or ""}  # fmt: skip


def for_job(db, refs: list[str], shots: list[dict]) -> dict[str, dict]:
    """A job's `screen_figures`: for each screen it sends, by file id, the first of its shots'
    figures for that screen. The worker draws them as it sends the pictures."""
    from app.models.brands import BrandScreen

    out = {}
    for ref in refs:
        screen = ref.startswith("screen:") and db.get(BrandScreen, int(ref.split(":")[1]))
        figure = screen and next((f for s in shots if (f := shot_figure(screen, s))), None)
        if figure:
            out[str(screen.file_id)] = figure
    return out


def draw(data: bytes, figure: dict | None) -> bytes:
    """The screen with its number area cleared to its own background and the figure written
    in: the balance big, the gain line under it (green and rising, or red and falling for a
    loss), and a fresh chart going the same way when the spot has one. PNG out; no figure: the
    picture as it is."""
    if not figure:
        return data
    image = Image.open(io.BytesIO(data)).convert("RGB")
    spot, pen = figure["spot"], ImageDraw.Draw(image)
    x0, y0, x1, y1 = spot["box"]
    corner = (min(x0, image.width - 1), min(y0, image.height - 1))  # its own background
    pen.rectangle((x0, y0, x1 - 1, y1 - 1), fill=image.getpixel(corner))
    (x, y), size = spot["at"], spot["size"]
    if figure["balance"]:
        pen.text((x, y), figure["balance"], font=ImageFont.truetype(FONT, size), fill=WHITE)
    change = figure["change"].strip()
    loss = change.startswith(("-", "−"))
    if change:
        line = f"{'▼' if loss else '▲'} {change}"
        small = ImageFont.truetype(FONT, round(size * 0.43))
        pen.text((x + 2, y + round(size * 1.33)), line, font=small, fill=RED if loss else GREEN)
    if chart := spot.get("chart"):
        _chart(pen, chart, loss, f"{figure['balance']}{change}")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def _chart(pen: ImageDraw.ImageDraw, box: list[int], loss: bool, seed: str) -> None:
    """A stepped price line across the box, ending high (or low for a loss); the same figure
    always draws the same line."""
    x0, y0, x1, y1 = box
    rand, points, steps = random.Random(seed), [], 24  # noqa: S311 - a drawing, not a secret
    for i in range(steps + 1):
        rise = 1.0 if i == steps else min(max(i / steps + rand.uniform(-0.12, 0.12), 0.0), 1.0)
        level = rise if not loss else 1 - rise
        points.append((x0 + (x1 - x0) * i / steps, y1 - (y1 - y0) * (0.1 + 0.8 * level)))
    pen.line(points, fill=RED if loss else GREEN, width=4, joint="curve")
