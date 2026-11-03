"""The study kit's pure parts: cut list to shot table, pacing, sound parsing. No network."""

from scripts.study_example import gaps, loudness, pacing, shot_rows, shot_table, silences

TRANSCRIPT = [
    {
        "start": 0.1,
        "end": 1.6,
        "text": "I do. Hell no!",
        "words": [
            {"word": "I", "start": 0.1, "end": 0.2},
            {"word": "do.", "start": 0.2, "end": 0.4},
            {"word": "Hell", "start": 0.5, "end": 0.8},
            {"word": "no!", "start": 0.8, "end": 1.1},
        ],
    },
    {"start": 4.0, "end": 4.5, "text": "What?!", "words": []},
]


def test_cut_list_becomes_a_shot_table_with_lines_and_pacing():
    rows = shot_rows([0.45, 0.0, 2.0, 9.0], 5.0)  # unsorted, a cut at 0 and one past the end
    assert [(r["n"], r["start"], r["end"], r["dur"]) for r in rows] == [
        (1, 0.0, 0.45, 0.45),
        (2, 0.45, 2.0, 1.55),
        (3, 2.0, 5.0, 3.0),
    ]
    table = shot_table(rows, TRANSCRIPT).splitlines()
    assert table[2] == "| 1 | 0.00-0.45 | 0.45 | shot0.jpg | ? | ? | ? | I do. | ? |"
    assert "| Hell no! |" in table[3] and table[4].endswith("|  | ? |")  # "What?!" has no words
    p = pacing(rows, 5.0)
    assert p["cuts_per_10s"] == 4.0 and p["longest"] == {"shot": 3, "dur": 3.0}
    assert p["shortest"] == {"shot": 1, "dur": 0.45} and p["under_1s"] == 1


def test_sound_facts_from_ffmpeg_logs_and_speech_gaps():
    log = (
        "[silencedetect @ 0x1] silence_start: -0.01\n[silencedetect @ 0x1] silence_end: 0.6 |\n"
        "[Parsed_ebur128_1 @ 0x2] Summary:\n  Integrated loudness:\n    I:         -14.2 LUFS\n"
    )
    assert silences(log) == [[0, 0.6]]
    assert loudness(log) == -14.2 and loudness("") is None
    assert gaps(TRANSCRIPT, 8.0) == [[1.6, 4.0], [4.5, 8.0]]
