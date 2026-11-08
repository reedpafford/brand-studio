"""Room sound for a talker's voice (UGC, Reed 3 Nov: "a much more realistic voice, with room
ambience"): a dry studio voice made to sound recorded on a phone in a real room. Free: ffmpeg
only, on the narration once its pauses are trimmed (narration.measure), so its length and its
words' times stay as measured. The chain and why each step (.context/team/research/
ugc-realism.md): a phone mic's band and presence, a light phone-style compressor, a short
small-room reflection (a synthetic 0.3 s impulse, convolved), a quiet room-tone bed (`BED`) under
every gap, then one loudness for the whole track."""

import subprocess
from pathlib import Path

LUFS, PEAK = -16, -1.5  # the finished voice: integrated loudness and true peak (dBFS)
WET, TONE = -15, -46  # the room's reflections and its tone bed, in dB against the voice
MIC = ("highpass=f=100,lowpass=f=12500,equalizer=f=220:t=q:w=1.0:g=1.5,"
       "equalizer=f=3000:t=q:w=1.2:g=2,acompressor=threshold=-21dB:ratio=2.5:attack=8:"
       "release=150")  # fmt: skip
IMPULSE = (
    "anoisesrc=d=0.32:c=pink:r=48000:a=1:seed=7,afade=t=out:st=0:d=0.32:curve=exp,"
    "highpass=f=250,lowpass=f=4500"
)  # a small room's decay, the same every time
# The room tone: a room's air across the band a phone plays (a phone's speaker drops most of
# what's under 200 Hz). Video 281's bed was a brown rumble under 350 Hz at about -57 dBFS above
# 200 Hz, 45 dB under the voice, so on a phone every gap was dead quiet; this one sits about
# -49 dBFS in the gaps, 37 dB under the voice.
BED = "anoisesrc=c=pink:r=48000:a=1:seed=3,highpass=f=150,lowpass=f=5000"


def graph() -> str:
    """The filter graph: input 0 is the voice; the output is [out]."""
    return ";".join([
        f"[0:a]aformat=sample_rates=48000:channel_layouts=mono,{MIC},asplit[dry][send]",
        f"{IMPULSE}[ir]",
        f"[send][ir]afir=dry=0:wet=1,volume={WET}dB[wet]",
        f"{BED},volume={TONE}dB[tone]",
        "[dry][wet][tone]amix=inputs=3:duration=first:normalize=0,"
        f"loudnorm=I={LUFS}:TP={PEAK}:LRA=11,aresample=44100[out]",
    ])  # fmt: skip


def finish(voice: Path, out: Path) -> Path:
    """The voice in a room, as an MP3 of the same length."""
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(voice), "-filter_complex", graph(),
               "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", str(out)]  # fmt: skip
    done = subprocess.run(command, capture_output=True, timeout=300)  # noqa: S603
    if done.returncode:
        raise ValueError("The voice's file can't be read.")
    return out
