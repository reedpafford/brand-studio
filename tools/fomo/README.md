# FOMO final-cut tools (fallback)

Local tools the FOMO-Producer used on the final cut. They're the **fallback if Reed's test shows phone inserts are still unreadable** after the Director's insert rule (#1192/#1193). They make no paid calls: Python 3 with OpenCV (SIFT), Pillow, numpy and ffmpeg. `watch6.py` also needs faster-whisper.

| Tool | What it does | Inputs |
|---|---|---|
| `insert_hold.py` | The readable insert. It finds a real brand screen on the phone in one frame (SIFT homography), pastes the exact screen over it, then holds about 1.5 s with a gentle push-in toward one spot (e.g. the @GHOSTMODE Spotlight card). It stops at about 1.75× so the phone edge and hand stay in frame, never full screen. This is how Ghostmode v2 made "@GHOSTMODE +$5,004,190" readable. | the clip, a time where the phone is large and upright, the screen PNG, the focus point in screen pixels, the output; optional seconds and max zoom. Splice the output into the clip with ffmpeg. |
| `onphone.py` | A moving screen on the phone. It tracks the real screen through a clip (SIFT per frame, corners smoothed over 3 frames) and warps animated chart pages (from `chart_anim.py`) or one still screen (`FULL=screen.png`) onto it, so the chart rises or dips with the story. | the input clip, the output, the reference screen (`assets/brands/fomo/screens/token-up.png`), and `start_frame:anim_dir` (or `start_frame:nframes` with `FULL`). |
| `chart_anim.py` | Renders animated fomo coin-chart pages from the real token screen with the fomo header (`climb`, `crash` or `rocket`), to feed `onphone.py`. | the kind, seconds and the output; the pages land next to it as `p####.png`. |
| `watch6.py` | Watch, don't skim. It makes 6 fps contact sheets with the spoken words (whisper word timestamps) under each frame, so a reviewer can check the words against the frames before delivery. Reed rejected 1 fps as too coarse. | the video, an output prefix, and seconds per sheet (default 10). |

The screens must be real brand screens with the beat's own figure (`assets/brands/fomo/screens/`, or a per-beat copy). Never invent a screen.
