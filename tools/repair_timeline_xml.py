from __future__ import annotations

import datetime
import json
import shutil
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path


def unique(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            output.append(item)
            seen.add(item)
    return output


def pathurl_to_windows(value: str | None) -> str:
    if not value:
        return ""
    if value.startswith("file:///"):
        decoded = urllib.parse.unquote(value[len("file:///") :])
        return decoded.replace("/", "\\")
    return value


def clip_source(clip: ET.Element) -> str:
    file_el = clip.find("file")
    if file_el is None:
        return ""
    return pathurl_to_windows(file_el.findtext("pathurl") or file_el.findtext("name"))


def add_clip(
    track_el: ET.Element,
    clip_id: str,
    source: str,
    start: float,
    end: float,
    duration_sec: float,
    label: str,
    gain_db: str | None = None,
    **extra: str | None,
) -> ET.Element | None:
    if track_el.get("type") == "audio" and not source:
        return None
    if start >= duration_sec:
        return None
    end = min(end, duration_sec)
    if end <= start:
        return None

    attrs = {
        "id": clip_id,
    }
    if source:
        attrs["source"] = source
    if label:
        attrs["label"] = label
    attrs["start_sec"] = f"{start:.3f}"
    attrs["end_sec"] = f"{end:.3f}"
    if gain_db is not None:
        attrs["gain_db"] = gain_db
    for key, value in extra.items():
        if value is not None:
            attrs[key] = value
    return ET.SubElement(track_el, "clip", attrs)


def read_program_script_sections(script_path: Path) -> list[str]:
    if not script_path.exists():
        return []
    text = script_path.read_text(encoding="utf-8", errors="replace")
    sections: list[str] = []
    current: list[str] = []
    wanted_headings = {
        "开场与历史上的今天",
        "开场和本地新闻",
        "主题引入",
        "主体展开",
        "情绪转折",
        "收尾祝福",
        "收尾",
    }
    active = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if active and current:
                sections.append("".join(current).strip())
            heading = line[3:].strip()
            active = heading in wanted_headings
            current = []
            continue
        if active and line:
            current.append(line)
    if active and current:
        sections.append("".join(current).strip())
    return sections


def repair_result(result_dir: Path, archive_dir: Path | None = None) -> None:
    xml_path = result_dir / "timeline_tracks.xml"
    backup_path = result_dir / "timeline_tracks_xmeml_backup.xml"
    if not xml_path.exists():
        raise FileNotFoundError(xml_path)

    current_root = ET.parse(xml_path).getroot()
    if current_root.tag == "xmeml" and not backup_path.exists():
        shutil.copy2(xml_path, backup_path)

    source_xml = backup_path if backup_path.exists() else xml_path
    xroot = ET.parse(source_xml).getroot()
    if xroot.tag != "xmeml":
        raise ValueError(f"Expected xmeml source, got {xroot.tag}: {source_xml}")

    sequence = xroot.find("sequence")
    if sequence is None:
        raise ValueError("Missing xmeml sequence")
    timebase = int(sequence.findtext("rate/timebase") or "25")
    duration_frames = int(sequence.findtext("duration") or "7500")
    duration_sec = duration_frames / timebase
    title = sequence.findtext("name") or "Soundao FM"

    def frame_sec(value: str | None) -> float:
        return int(value or "0") / timebase

    track_map: dict[str, ET.Element] = {}
    for track in xroot.findall(".//media/audio/track"):
        track_map[(track.findtext("name") or "").strip()] = track

    timeline = ET.Element(
        "timeline",
        {
            "name": title,
            "frameRate": str(timebase),
            "timebase": "seconds",
        },
    )
    duration_el = ET.SubElement(timeline, "duration")
    duration_el.text = f"{duration_sec:.3f}"
    tracks_el = ET.SubElement(timeline, "tracks")
    fit_spans: list[tuple[float, float]] = []
    overflow = False

    background_source = ""
    background_track = track_map.get("background_music")
    if background_track is not None:
        first_clip = background_track.find("clipitem")
        if first_clip is not None:
            background_source = clip_source(first_clip)
    if background_source:
        bed_track = ET.SubElement(
            tracks_el,
            "track",
            {"id": "background_music", "name": "背景音乐"},
        )
        ET.SubElement(
            bed_track,
            "clip",
            {
                "id": "bed_loop",
                "source": background_source,
                "start": "0.000",
                "end": f"{duration_sec:.3f}",
                "loop": "true",
                "fadeIn": "5.000",
                "fadeOut": "5.000",
            },
        )

    host_track = track_map.get("host_voice")
    if host_track is not None:
        host_el = ET.SubElement(
            tracks_el,
            "track",
            {"id": "host_voice", "name": "主持人口播"},
        )
        host_clips = host_track.findall("clipitem")
        raw_spans = [
            (frame_sec(clip.findtext("start")), frame_sec(clip.findtext("end")))
            for clip in host_clips
        ]
        closing_start = duration_sec
        song_track = track_map.get("closing_song")
        if song_track is not None:
            song_first = song_track.find("clipitem")
            if song_first is not None:
                closing_start = frame_sec(song_first.findtext("start"))

        overflow = bool(raw_spans) and (
            raw_spans[-1][0] >= duration_sec or raw_spans[-1][1] > duration_sec
        )
        fit_spans = raw_spans

        for index, clip in enumerate(host_clips, 1):
            start, end = fit_spans[index - 1]
            ET.SubElement(
                host_el,
                "clip",
                {
                    "id": f"host_{index:02d}",
                    "source": clip_source(clip),
                    "start": f"{start:.3f}",
                    "end": f"{end:.3f}",
                },
            )

    song_track = track_map.get("closing_song")
    if song_track is not None:
        song_el = ET.SubElement(
            tracks_el,
            "track",
            {"id": "closing_song", "name": "结尾配歌"},
        )
        for index, clip in enumerate(song_track.findall("clipitem"), 1):
            raw_start = frame_sec(clip.findtext("start"))
            raw_end = frame_sec(clip.findtext("end"))
            if overflow and fit_spans:
                start = fit_spans[-1][1] + 2.0
                end = start + max(0.1, raw_end - raw_start)
            else:
                start = raw_start
                end = raw_end
            ET.SubElement(
                song_el,
                "clip",
                {
                    "id": f"closing_song_{index:02d}",
                    "source": clip_source(clip),
                    "start": f"{start:.3f}",
                    "end": f"{end:.3f}",
                    "fadeIn": "2.000",
                    "fadeOut": "3.000",
                },
            )

    max_clip_end = duration_sec
    for clip_el in tracks_el.findall(".//clip"):
        try:
            max_clip_end = max(max_clip_end, float(clip_el.get("end") or "0"))
        except ValueError:
            pass
    if max_clip_end > duration_sec:
        duration_sec = max_clip_end + 2.0
        duration_el.text = f"{duration_sec:.3f}"
        bed_loop = tracks_el.find("./track[@id='background_music']/clip[@id='bed_loop']")
        if bed_loop is not None:
            bed_loop.set("end", f"{duration_sec:.3f}")

    subtitle_track = track_map.get("subtitles")
    if subtitle_track is not None:
        subtitle_el = ET.SubElement(
            tracks_el,
            "track",
            {"id": "subtitles", "name": "字幕"},
        )
        script_sections = read_program_script_sections(result_dir / "program_script.md")
        subtitle_clips = subtitle_track.findall("clipitem")
        subtitle_spans = fit_spans if host_track is not None and len(fit_spans) == len(subtitle_clips) else [
            (frame_sec(clip.findtext("start")), frame_sec(clip.findtext("end")))
            for clip in subtitle_clips
        ]
        for index, clip in enumerate(subtitle_clips, 1):
            start, end = subtitle_spans[index - 1]
            end = min(end, duration_sec)
            if start >= duration_sec or end <= start:
                continue
            text = script_sections[index - 1] if index - 1 < len(script_sections) else (clip.findtext("name") or "")
            item = ET.SubElement(
                subtitle_el,
                "subtitle",
                {
                    "id": f"subtitle_{index:02d}",
                    "start": f"{start:.3f}",
                    "end": f"{end:.3f}",
                },
            )
            item.text = text

    ordered_tracks: list[ET.Element] = []
    for track_id in ["host_voice", "background_music", "closing_song", "subtitles"]:
        match = next((item for item in list(tracks_el) if item.get("id") == track_id), None)
        if match is not None:
            ordered_tracks.append(match)
    for item in list(tracks_el):
        tracks_el.remove(item)
    for item in ordered_tracks:
        tracks_el.append(item)

    ET.indent(timeline, space="  ")
    xml_body = ET.tostring(timeline, encoding="unicode")
    xml_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body + "\n",
        encoding="utf-8",
    )
    xml_text = xml_path.read_text(encoding="utf-8")
    if "????" in xml_text:
        raise ValueError("Generated XML contains question-mark corruption")
    ET.parse(xml_path)

    manifest_path = result_dir / "deliverable_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["timeline_xml_path"] = str(xml_path)
        manifest["timeline_xml_format"] = "Soundao simple timeline XML"
        manifest["files"] = unique(
            [str(item) for item in manifest.get("files", [])]
            + [str(xml_path), str(result_dir / "subtitles.srt")]
        )
        manifest["files"] = [
            item for item in manifest["files"] if Path(item).name != backup_path.name
        ]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if archive_dir and archive_dir.exists():
        for item in [
            xml_path,
            backup_path,
            manifest_path,
            result_dir / "subtitles.srt",
        ]:
            if item.exists():
                shutil.copy2(item, archive_dir / item.name)


def update_latest_command(command_path: Path, result_dir: Path) -> None:
    if not command_path.exists():
        return
    data = json.loads(command_path.read_text(encoding="utf-8"))
    deliverable = (
        data.get("body", {})
        .get("outcome", {})
        .get("deliverable", {})
    )
    if not deliverable:
        return
    xml_path = result_dir / "timeline_tracks.xml"
    backup_path = result_dir / "timeline_tracks_xmeml_backup.xml"
    deliverable["timeline_xml_path"] = str(xml_path)
    deliverable["timeline_xml_format"] = "Soundao simple timeline XML"
    deliverable["files"] = unique(
        [str(item) for item in deliverable.get("files", [])]
        + [str(xml_path), str(result_dir / "subtitles.srt")]
    )
    deliverable["files"] = [
        item for item in deliverable["files"] if Path(item).name != backup_path.name
    ]
    command_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: repair_timeline_xml.py <result-dir>")
        return 2
    result_dir = Path(sys.argv[1]).resolve()
    project_root = Path(__file__).resolve().parents[2]
    archive_dir = (
        project_root
        / "Soundao_Agent_Workspace"
        / "02_工作成果"
        / "AI电台节目"
        / result_dir.name
    )

    repair_result(result_dir, archive_dir)
    framework_dir = project_root / "soundao-web-agent-framework"
    update_latest_command(framework_dir / "latest_agent_command.json", result_dir)
    update_latest_command(
        framework_dir / "runs" / "default" / "agent_command.latest.json",
        result_dir,
    )

    root = ET.parse(result_dir / "timeline_tracks.xml").getroot()
    print(f"repaired={result_dir / 'timeline_tracks.xml'}")
    print(f"backup={result_dir / 'timeline_tracks_xmeml_backup.xml'}")
    print(f"root={root.tag}")
    print(f"size={(result_dir / 'timeline_tracks.xml').stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
