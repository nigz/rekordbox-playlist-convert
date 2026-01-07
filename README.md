# Rekordbox Playlist Convert

Convert FLAC tracks to AIFF/MP3 for Rekordbox USB exports while preserving all hot cues, memory points, and beatgrids.

## The Problem

CDJ-2000 Nexus 1 and older players don't support FLAC. If you maintain a FLAC library in Rekordbox, you need to convert files when exporting—but re-importing breaks your carefully set cue points.

## The Solution

This tool:
1. Converts FLAC files on the USB to AIFF or MP3 using FFmpeg
2. Patches the `export.pdb` database to update file references
3. Preserves all your cues and beatgrids perfectly

## Requirements

- Python 3.8+
- FFmpeg (`brew install ffmpeg`)

## Usage

```bash
# Full workflow: convert files + patch database
python patcher.py /Volumes/MY_USB

# Convert to MP3 instead of AIFF (320kbps CBR)
python patcher.py /Volumes/MY_USB --format mp3

# Only patch database (if files already converted via XLD)
python patcher.py /Volumes/MY_USB --patch-only

# Only convert files (skip database patching)
python patcher.py /Volumes/MY_USB --convert-only

# Keep original FLACs after conversion
python patcher.py /Volumes/MY_USB --keep-originals
```

## Workflow

1. Export your playlist to USB from Rekordbox as normal
2. Run: `python patcher.py /Volumes/YOUR_USB`
3. Eject and plug into your CDJ ✅

## Why AIFF?

- Same byte-length as FLAC (`.aiff` = 5 chars = `.flac`)
- Supports full metadata/cues unlike WAV
- Compatible with every CDJ that doesn't support FLAC

## License

MIT
