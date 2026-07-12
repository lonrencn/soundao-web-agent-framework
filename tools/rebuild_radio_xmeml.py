from __future__ import annotations

import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_config import get_workspace_path

FALLBACK_SAMPLE_RATE = 48000


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def probe_audio_metadata(path: Path) -> dict[str, int | str | None]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels,codec_name",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    streams = json.loads(result.stdout).get("streams") or []
    stream = streams[0] if streams else {}
    sample_rate = stream.get("sample_rate")
    channels = stream.get("channels")
    return {
        "sample_rate": int(sample_rate) if str(sample_rate or "").isdigit() else None,
        "channels": int(channels) if str(channels or "").isdigit() else None,
        "codec_name": stream.get("codec_name"),
    }


def sample_rate_for(path: Path) -> int:
    try:
        value = probe_audio_metadata(path).get("sample_rate")
    except Exception:
        value = None
    return int(value or FALLBACK_SAMPLE_RATE)


def read_sections(script_path: Path) -> list[tuple[str, str]]:
    wanted = [
        "开场与历史上的今天",
        "开场和本地新闻",
        "主题引入",
        "主体展开",
        "情绪转折",
        "收尾祝福",
        "收尾",
    ]
    wanted_set = set(wanted)
    text = script_path.read_text(encoding="utf-8", errors="replace")
    sections: list[tuple[str, str]] = []
    active_name = ""
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            if active_name and current:
                sections.append((active_name, "".join(current).strip()))
            name = line[3:].strip()
            active_name = name if name in wanted_set else ""
            current = []
            continue
        if active_name and line:
            current.append(line)
    if active_name and current:
        sections.append((active_name, "".join(current).strip()))
    return sections[:5]


def elem(parent: ET.Element, tag: str, text: str | int | None = None, **attrs: str) -> ET.Element:
    child = ET.SubElement(parent, tag, attrs)
    if text is not None:
        child.text = str(text)
    return child


def rate(parent: ET.Element, timebase: int = 30) -> None:
    node = elem(parent, "rate")
    elem(node, "timebase", timebase)
    elem(node, "ntsc", "FALSE")


def path_url(path: Path) -> str:
    return "file://localhost/" + str(path).replace("\\", "/")


def media_file(parent: ET.Element, file_id: str, path: Path, duration_frames: int) -> None:
    file_el = elem(parent, "file", id=file_id)
    elem(file_el, "name", path.name)
    elem(file_el, "pathurl", path_url(path))
    rate(file_el)
    elem(file_el, "duration", duration_frames)
    media = elem(file_el, "media")
    audio = elem(media, "audio")
    sample = elem(audio, "samplecharacteristics")
    elem(sample, "depth", 16)
    elem(sample, "samplerate", sample_rate_for(path))
    elem(audio, "channelcount", 2)


def clipitem(
    parent: ET.Element,
    item_id: str,
    name: str,
    source: Path,
    start: int,
    end: int,
    file_id: str,
) -> None:
    duration = end - start
    clip = elem(parent, "clipitem", id=item_id)
    elem(clip, "name", name)
    elem(clip, "enabled", "TRUE")
    elem(clip, "duration", duration)
    rate(clip)
    elem(clip, "start", start)
    elem(clip, "end", end)
    elem(clip, "in", 0)
    elem(clip, "out", duration)
    media_file(clip, file_id, source, duration)


def generatoritem(parent: ET.Element, item_id: str, name: str, text: str, start: int, end: int) -> None:
    duration = end - start
    item = elem(parent, "generatoritem", id=item_id)
    elem(item, "name", name)
    elem(item, "enabled", "TRUE")
    elem(item, "duration", duration)
    rate(item)
    elem(item, "start", start)
    elem(item, "end", end)
    elem(item, "in", 0)
    elem(item, "out", duration)
    effect = elem(item, "effect")
    elem(effect, "name", "Text")
    elem(effect, "effectid", "Text")
    elem(effect, "effectcategory", "Text")
    elem(effect, "effecttype", "generator")
    elem(effect, "mediatype", "video")
    parameter = elem(effect, "parameter")
    elem(parameter, "parameterid", "str")
    elem(parameter, "name", "Text")
    elem(parameter, "value", text)


def retime_host(result_dir: Path) -> Path:
    source = result_dir / "host_voice_full.mp3"
    target = result_dir / "host_voice_retimed.mp3"
    source_duration = probe_duration(source)
    source_sample_rate = sample_rate_for(source)
    target_duration = 269.0
    tempo = source_duration / target_duration
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-filter:a",
            f"atempo={tempo:.6f}",
            "-ar",
            str(source_sample_rate),
            "-ac",
            "2",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(target),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return target


def update_json_references(result_dir: Path, xml_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    files = [
        result_dir / "deliverable_manifest.json",
        project_root / "web_agent_framework" / "latest_agent_command.json",
        project_root / "web_agent_framework" / "runs" / "default" / "agent_command.latest.json",
    ]
    for path in files:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "deliverable_manifest.json":
            data["timeline_xml_path"] = str(xml_path)
            data["timeline_xml_format"] = "FCP7 XML / xmeml"
            data["files"] = [
                item
                for item in data.get("files", [])
                if not str(item).endswith("_backup.xml")
            ]
            for item in [xml_path, result_dir / "host_voice_retimed.mp3"]:
                if str(item) not in data["files"]:
                    data["files"].append(str(item))
        else:
            deliverable = data.get("body", {}).get("outcome", {}).get("deliverable", {})
            if deliverable:
                deliverable["timeline_xml_path"] = str(xml_path)
                deliverable["timeline_xml_format"] = "FCP7 XML / xmeml"
                deliverable["files"] = [
                    item
                    for item in deliverable.get("files", [])
                    if not str(item).endswith("_backup.xml")
                ]
                for item in [xml_path, result_dir / "host_voice_retimed.mp3"]:
                    if str(item) not in deliverable["files"]:
                        deliverable["files"].append(str(item))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(result_dir: Path) -> None:
    xml_path = result_dir / "timeline_tracks.xml"
    if xml_path.exists():
        backup = result_dir / "timeline_tracks_before_xmeml_rebuild_backup.xml"
        if not backup.exists():
            shutil.copy2(xml_path, backup)

    host_retimed = retime_host(result_dir)
    bed = result_dir / "background_bed_noon_warm.mp3"
    song = result_dir / "closing_song_30s_noon_warm.mp3"
    sections = read_sections(result_dir / "program_script.md")
    while len(sections) < 5:
        sections.append((f"段落 {len(sections) + 1}", ""))

    subtitle_ranges = [
        (180, 1724),
        (1874, 2815),
        (3378, 5576),
        (6027, 7073),
        (7486, 8250),
    ]

    root = ET.Element("xmeml", {"version": "5"})
    seq = elem(root, "sequence", id="soundao_fm_xinjing_yantai")
    elem(seq, "name", "Soundao FM：心静自然凉")
    elem(seq, "duration", 9000)
    rate(seq)
    media = elem(seq, "media")
    video = elem(media, "video")
    fmt = elem(video, "format")
    sample = elem(fmt, "samplecharacteristics")
    rate(sample)
    elem(sample, "width", 1920)
    elem(sample, "height", 1080)
    elem(sample, "anamorphic", "FALSE")
    elem(sample, "pixelaspectratio", "square")
    elem(sample, "fielddominance", "none")
    elem(video, "track")
    subtitle_track = elem(video, "track")
    for idx, ((name, text), (start, end)) in enumerate(zip(sections, subtitle_ranges), 1):
        generatoritem(subtitle_track, f"subtitle_{idx:02d}", name, text, start, end)
    generatoritem(subtitle_track, "subtitle_closing_song", "结尾配歌", "以 30 秒配歌结束，音乐与口播最后 5 秒重叠后淡出。", 8100, 9000)

    audio = elem(media, "audio")
    audio_fmt = elem(audio, "format")
    audio_sample = elem(audio_fmt, "samplecharacteristics")
    elem(audio_sample, "depth", 16)
    elem(audio_sample, "samplerate", sample_rate_for(host_retimed))
    outputs = elem(audio, "outputs")
    for index in [1, 2]:
        group = elem(outputs, "group")
        elem(group, "index", index)
        elem(group, "numchannels", 1)
        elem(group, "downmix", 0)

    host_track = elem(audio, "track")
    clipitem(host_track, "host_full", "主持人口播完整轨", host_retimed, 180, 8250, "file_host_full")

    bgm_track = elem(audio, "track")
    for idx in range(5):
        clipitem(
            bgm_track,
            f"bgm_loop_{idx + 1}",
            "背景音乐循环",
            bed,
            idx * 1800,
            (idx + 1) * 1800,
            f"file_bgm_{idx + 1}",
        )

    song_track = elem(audio, "track")
    clipitem(song_track, "closing_song_30s", "结尾配歌 30 秒", song, 8100, 9000, "file_closing_song")

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    xml_path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE xmeml>\n' + body + "\n",
        encoding="utf-8",
    )
    ET.parse(xml_path)

    update_json_references(result_dir, xml_path)

    workspace = get_workspace_path(required=False)
    archive_dir = workspace / "02_工作成果" / "AI电台节目" / result_dir.name if workspace else None
    if archive_dir and archive_dir.exists():
        shutil.copy2(xml_path, archive_dir / xml_path.name)
        shutil.copy2(host_retimed, archive_dir / host_retimed.name)

    print(f"xml={xml_path}")
    print(f"host_retimed={host_retimed}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: rebuild_radio_xmeml.py <result-dir>")
        return 2
    build(Path(sys.argv[1]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
