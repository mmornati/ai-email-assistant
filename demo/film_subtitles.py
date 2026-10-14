#!/usr/bin/env python3
"""Write WebVTT subtitles for the landing-page film from the narration timing (docs/video/film/timing.js).

    python3 demo/film_subtitles.py      # writes docs/assets/video/film.<lang>.vtt
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILM = ROOT / "docs" / "video" / "film"
OUT = ROOT / "docs" / "assets" / "video"


def stamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def main():
    source = (FILM / "timing.js").read_text(encoding="utf-8")
    timing = json.loads(source[source.index("{"):source.rindex("}") + 1])
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, plan in timing.items():
        cues = [(sc["start"] + c["s"], sc["start"] + c["e"] + 0.25, c["text"]) for sc in plan["scenes"] for c in sc["cues"]]
        lines = ["WEBVTT", ""]
        for i, (start, end, text) in enumerate(cues, 1):
            lines += [str(i), f"{stamp(start)} --> {stamp(end)}", text, ""]
        (OUT / f"film.{lang}.vtt").write_text("\n".join(lines), encoding="utf-8")
        print(f"film.{lang}.vtt: {len(cues)} cues")


if __name__ == "__main__":
    main()
