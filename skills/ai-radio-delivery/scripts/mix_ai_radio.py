#!/usr/bin/env python3
"""Mix an AI radio show with a host track, optional bed, and optional song.

This script intentionally replaces the old PowerShell helper. It keeps fades on
source-local time before delaying tracks on the final timeline, then validates
the exported file with ffprobe and silencedetect.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def require_audio(path: Path, label: str) -> Path:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    if path.suffix.lower() not in AUDIO_SUFFIXES:
        raise ValueError(f"{label} is not a supported audio file: {path}")
    return path.resolve()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def ffprobe(path: Path) -> dict[str, Any]:
    completed = run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(completed.stdout).get("format", {})


def silence_detect(path: Path, out_path: Path, noise_db: float, min_duration: float) -> str:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_duration}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = (completed.stdout or "") + (completed.stderr or "")
    out_path.write_text(text, encoding="utf-8")
    return text


def seconds_to_delay_ms(value: float) -> int:
    return max(0, int(round(value * 1000)))


def build_filter(args: argparse.Namespace, has_bed: bool, has_song: bool) -> tuple[list[str], str]:
    duration = float(args.duration_sec)
    host_delay_ms = seconds_to_delay_ms(args.host_delay_sec)
    host_fade_out = max(0.0, duration - 1.0)

    filters = [
        (
            f"[0:a]volume={args.host_db}dB,"
            f"afade=t=in:st=0:d={args.host_fade_sec},"
            f"afade=t=out:st={host_fade_out}:d={args.host_fade_sec},"
            f"adelay={host_delay_ms}|{host_delay_ms},"
            f"apad,atrim=0:{duration}[host]"
        )
    ]
    mix_inputs: list[str] = []
    input_args: list[str] = ["-i", str(args.host_track)]

    next_index = 1
    if has_bed:
        bed_fade_out_start = max(0.0, duration - float(args.bed_fade_out_sec))
        input_args.extend(["-stream_loop", "-1", "-i", str(args.bed)])
        filters.append(
            (
                f"[{next_index}:a]atrim=0:{duration},asetpts=PTS-STARTPTS,"
                f"volume={args.bed_db}dB,"
                f"afade=t=in:st=0:d={args.bed_fade_in_sec},"
                f"afade=t=out:st={bed_fade_out_start}:d={args.bed_fade_out_sec}[bed]"
            )
        )
        mix_inputs.append("[bed]")
        next_index += 1

    if has_song:
        song_start = float(args.song_start_sec)
        song_duration = float(args.song_duration_sec)
        song_delay_ms = seconds_to_delay_ms(song_start)
        song_fade_out_start = max(0.0, song_duration - float(args.song_fade_out_sec))
        input_args.extend(["-i", str(args.song)])
        # Fade before delay: fade times are source-local, not final timeline time.
        filters.append(
            (
                f"[{next_index}:a]atrim=0:{song_duration},asetpts=PTS-STARTPTS,"
                f"volume={args.song_db}dB,"
                f"afade=t=in:st=0:d={args.song_fade_in_sec},"
                f"afade=t=out:st={song_fade_out_start}:d={args.song_fade_out_sec},"
                f"adelay={song_delay_ms}|{song_delay_ms}[song]"
            )
        )
        mix_inputs.append("[song]")

    if mix_inputs:
        filters.append(
            "".join(mix_inputs)
            + f"amix=inputs={len(mix_inputs)}:duration=longest:normalize=0[musicraw]"
        )
        filters.append(
            "[musicraw][host]sidechaincompress="
            f"threshold={args.duck_threshold}:ratio={args.duck_ratio}:"
            f"attack={args.duck_attack_ms}:release={args.duck_release_ms}:makeup=1.0[music]"
        )
        filters.append(
            f"[music][host]amix=inputs=2:duration=longest:normalize=0,"
            f"atrim=0:{duration},loudnorm=I={args.target_lufs}:TP=-1.5:LRA=11[out]"
        )
    else:
        filters.append(f"[host]atrim=0:{duration},loudnorm=I={args.target_lufs}:TP=-1.5:LRA=11[out]")

    return input_args, ";".join(filters)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mix a broadcast-ready AI radio program.")
    parser.add_argument("--host-track", required=True, type=Path, help="Host narration track.")
    parser.add_argument("--bed", type=Path, default=None, help="Instrumental background music bed.")
    parser.add_argument("--song", type=Path, default=None, help="Featured song or outro song.")
    parser.add_argument("--output", required=True, type=Path, help="Final MP3/WAV output.")
    parser.add_argument("--duration-sec", type=float, default=300.0)
    parser.add_argument("--min-duration-sec", type=float, default=295.0)
    parser.add_argument("--host-delay-sec", type=float, default=6.0)
    parser.add_argument("--song-start-sec", type=float, default=268.0)
    parser.add_argument("--song-duration-sec", type=float, default=30.0)
    parser.add_argument("--min-host-duration-sec", type=float, default=None)
    parser.add_argument("--max-host-gap-before-song-sec", type=float, default=15.0)
    parser.add_argument("--host-db", type=float, default=-3.0)
    parser.add_argument("--bed-db", type=float, default=-21.0)
    parser.add_argument("--song-db", type=float, default=-2.0)
    parser.add_argument("--host-fade-sec", type=float, default=0.5)
    parser.add_argument("--bed-fade-in-sec", type=float, default=5.0)
    parser.add_argument("--bed-fade-out-sec", type=float, default=5.0)
    parser.add_argument("--song-fade-in-sec", type=float, default=2.0)
    parser.add_argument("--song-fade-out-sec", type=float, default=3.0)
    parser.add_argument("--duck-threshold", type=float, default=0.035)
    parser.add_argument("--duck-ratio", type=float, default=6.0)
    parser.add_argument("--duck-attack-ms", type=float, default=80.0)
    parser.add_argument("--duck-release-ms", type=float, default=700.0)
    parser.add_argument("--target-lufs", type=float, default=-16.0)
    parser.add_argument("--bitrate", default="192k")
    parser.add_argument("--validation-out", type=Path, default=None)
    parser.add_argument("--silence-log-out", type=Path, default=None)
    parser.add_argument("--silence-noise-db", type=float, default=-45.0)
    parser.add_argument("--silence-min-duration", type=float, default=2.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.host_track = require_audio(args.host_track, "host track")
    has_bed = args.bed is not None
    has_song = args.song is not None
    if has_bed:
        args.bed = require_audio(args.bed, "background bed")
    if has_song:
        args.song = require_audio(args.song, "song")

    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    validation_out = (args.validation_out or args.output.with_suffix(".validation.json")).resolve()
    silence_log_out = (args.silence_log_out or args.output.with_suffix(".silencedetect.txt")).resolve()

    input_args, filter_complex = build_filter(args, has_bed, has_song)
    codec_args = ["-c:a", "libmp3lame", "-b:a", args.bitrate] if args.output.suffix.lower() == ".mp3" else ["-c:a", "pcm_s16le"]
    command = [
        "ffmpeg",
        "-y",
        *input_args,
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        *codec_args,
        str(args.output),
    ]
    subprocess.run(command, check=True)

    probe = ffprobe(args.output)
    host_probe = ffprobe(args.host_track)
    duration = float(probe.get("duration") or 0)
    host_duration = float(host_probe.get("duration") or 0)
    min_host_duration = (
        float(args.min_host_duration_sec)
        if args.min_host_duration_sec is not None
        else max(120.0, float(args.duration_sec) * 0.7)
    )
    host_end_sec = float(args.host_delay_sec) + host_duration
    expected_host_end_sec = float(args.song_start_sec) if has_song else float(args.duration_sec)
    host_gap_before_song_sec = max(0.0, expected_host_end_sec - host_end_sec)
    host_duration_ok = host_duration >= min_host_duration
    host_timeline_ok = host_gap_before_song_sec <= float(args.max_host_gap_before_song_sec)
    silence_text = silence_detect(args.output, silence_log_out, args.silence_noise_db, args.silence_min_duration)
    validation_ok = (
        duration >= float(args.min_duration_sec)
        and host_duration_ok
        and host_timeline_ok
    )
    validation = {
        "ok": validation_ok,
        "output": str(args.output),
        "duration_sec": duration,
        "min_duration_sec": float(args.min_duration_sec),
        "host_track": str(args.host_track),
        "host_duration_sec": host_duration,
        "min_host_duration_sec": min_host_duration,
        "host_end_sec": host_end_sec,
        "expected_host_end_sec": expected_host_end_sec,
        "host_gap_before_song_sec": host_gap_before_song_sec,
        "max_host_gap_before_song_sec": float(args.max_host_gap_before_song_sec),
        "host_duration_ok": host_duration_ok,
        "host_timeline_ok": host_timeline_ok,
        "bit_rate": probe.get("bit_rate"),
        "size_bytes": int(probe.get("size") or 0),
        "silence_log": str(silence_log_out),
        "silence_events": [line for line in silence_text.splitlines() if "silence_" in line],
        "command": command,
        "notes": [
            "Opening rule: no host speech before 5 seconds; first host line should enter around 6-10 seconds and must enter before 15 seconds.",
            "Host narration must be long enough for the requested program, not merely padded to target duration with background music.",
            "Host narration should continue close to the closing song or program ending; long empty gaps before the song fail validation.",
            "Verify the opening by listening, waveform inspection, ASR, or voice-activity detection before delivery.",
            "If validation ok is false, do not mark the radio show as complete.",
        ],
    }
    validation_out.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if validation["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
