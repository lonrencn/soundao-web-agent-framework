---
name: premiere-xml-timeline
description: "Generate, repair, and validate Premiere Pro importable FCP7 XML / xmeml timelines for Soundao audio projects. Use when exporting timeline_tracks.xml, debugging XML that imports with silent flat waveforms, creating subtitle tracks, retiming radio narration into a 300-second timeline, or ensuring PR/Premiere sees audio waveforms instead of silent lines."
---

# Premiere XML Timeline Skill

Use this skill whenever an Agent needs to create or repair `timeline_tracks.xml` for Adobe Premiere Pro / PR import.

Scope boundary: this skill only defines FCP7 XML / `xmeml` file format rules and referenced-media format rules. It must not define radio program structure, script heading style, BGM generation workflow, closing-song generation workflow, or subtitle timing algorithms. Those belong to the caller's project skill or business workflow.

The known-good reference is `Soundao FM：气质的价值`:

`web_agent_framework/runs/default/agent_outputs/1783821945337-result/timeline_tracks.xml`

That reference imports with visible audio waveforms. Match its structure unless the user explicitly asks for a different editor format.

## Required Output

Export `timeline_tracks.xml` as FCP7 XML / `xmeml`, not a custom `<timeline>` XML.

Minimum structure:

- XML declaration: `<?xml version="1.0" encoding="utf-8"?>`
- DOCTYPE: `<!DOCTYPE xmeml>`
- Root: `<xmeml version="5">`
- Sequence:
  - 30 fps
  - `duration` = `9000` frames for a 300-second show
  - `rate/timebase` = `30`
  - `ntsc` = `FALSE`
- Video track:
  - optional subtitle `generatoritem` entries
  - Text effect with full subtitle text in `<parameter><value>...</value></parameter>`
- Audio tracks:
  - one or more `track` nodes containing `clipitem` entries
  - each `clipitem` must point to a real local media file through `file/pathurl`
  - track names and clip IDs are project-defined; do not require specific names such as host, BGM, or closing song

## Path Rules

Use Premiere-friendly local file URLs:

```xml
<pathurl>file://localhost/<absolute-path-with-forward-slashes></pathurl>
```

Do not use raw Windows paths in `pathurl`. Do not use URL-encoded Chinese path fragments for local media files.

## Audio Media Description

Every `clipitem/file/media/audio` must include complete audio metadata.

Required for every audio file node:

```xml
<media>
  <audio>
    <samplecharacteristics>
      <depth>16</depth>
      <samplerate>actual-audio-sample-rate</samplerate>
    </samplecharacteristics>
    <channelcount>2</channelcount>
  </audio>
</media>
```

This is not optional. If these fields are missing, Premiere may import the clip as a silent flat line even when the file path exists.

Do not hardcode `44100` or `48000` as a universal rule. Use `ffprobe` to read the referenced media file's actual sample rate and write that value into `samplecharacteristics/samplerate`. If the workflow transcodes media before XML export, write the sample rate of the transcoded file that the XML actually references.

## Audio File Rules

- Referenced media file names are not prescribed by this skill.
- Every `pathurl` must resolve to an existing local media file.
- Prefer MP3 assets that Premiere can conform reliably.
- Before delivery, verify every referenced audio file exists and is not silent.
- Use `ffprobe` to check duration, sample rate, channel count, and codec.
- Use `ffmpeg -af volumedetect` to confirm non-silent audio. A normal result should have meaningful `mean_volume` and `max_volume`, not silence.

## Retiming Rule

If a workflow retimes or transcodes an audio asset, do not merely change XML timecodes.

Correct options:

- Generate or transcode a real media file with the intended duration and format.
- Point XML `clipitem/file/pathurl` to that actual file.
- Ensure `clipitem` `duration`, `start`, `end`, `in`, and `out` match the referenced media usage in frames.

## Subtitle Rules

- Subtitle text must be stored in Text effect `parameter/value`.
- Every subtitle `generatoritem` must have valid `duration`, `start`, `end`, `in`, and `out` frame values.
- Subtitle IDs and timing strategy are project-defined; this skill only requires XML-valid generator items.
- Do not allow `????` replacement characters or mojibake in subtitle values.

## Validation Checklist

Before marking the XML complete:

1. Parse `timeline_tracks.xml` with `xml.etree.ElementTree`.
2. Confirm root is `xmeml`.
3. Confirm sequence duration is `9000` and timebase is `30`.
4. Confirm XML contains `<!DOCTYPE xmeml>`.
5. Confirm every referenced media file exists.
6. Confirm all `pathurl` local files exist.
7. Confirm every `clipitem/file/media/audio` has:
   - `samplecharacteristics/depth`
   - `samplecharacteristics/samplerate` matching the referenced media's actual sample rate
   - `channelcount`
8. Confirm referenced audio files are non-silent with `volumedetect`.
9. Confirm no `????` appears in the XML.
10. Confirm `deliverable_manifest.json` points `timeline_xml_path` to this XML and includes important media files.

## Known Failure Modes

- **Imports but waveform is a flat line**: usually missing `samplecharacteristics` or bad media description in the `file` node.
- **Imports but no audio**: a `clipitem` points to a file that does not exist, has mismatched media metadata, is mono-only in a fragile conform path, or was not generated after retiming/transcoding.
- **Imports wrong XML**: backup XML files were included in `deliverable_manifest.json`. Only expose the main `timeline_tracks.xml` to the page.
- **Simple custom XML fails in PR**: `<timeline>` with `start/end` or `start_sec/end_sec` is not the target format for PR. Use `xmeml`.
- **XML says 300 seconds but audio exceeds it**: regenerate or retime the audio. Do not fake it with XML-only timecode changes.

## Preferred Script

For Soundao radio outputs, prefer the project script:

```bash
python web_agent_framework/tools/rebuild_radio_xmeml.py "<result-dir>"
```

The script should:

- write `timeline_tracks.xml` as `xmeml`
- add complete media audio metadata
- update `deliverable_manifest.json`
- keep backup XML out of user-facing file lists

If the script is missing a needed field, patch the script rather than hand-writing XML repeatedly.
