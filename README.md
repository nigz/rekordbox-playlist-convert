# Rekordbox Playlist Convert

Convert audio files on Rekordbox USB exports for CDJ compatibility while preserving all hot cues, memory points, and beatgrids.

## The Problem

CDJ-2000 Nexus 1 and older players don't support FLAC. Re-importing to convert breaks your carefully set cue points.

## The Solution

This tool:
1. Converts files on the USB using FFmpeg
2. Patches the `export.pdb` database to update references
3. Preserves all your cues and beatgrids perfectly

**Format mapping** (based on extension length to preserve DB offsets):
| Source | Target |
|--------|--------|
| FLAC, ALAC | AIFF |
| M4A, OGG, WMA | MP3 |
| WAV, MP3, AIFF | *(kept as-is)* |

## Requirements

- Python 3.8+
- FFmpeg (`brew install ffmpeg`)

## Usage

```bash
# Full workflow: convert + patch
python patcher.py /Volumes/MY_USB

# Only patch (files already converted manually)
python patcher.py /Volumes/MY_USB --patch-only

# Only convert (skip database patching)
python patcher.py /Volumes/MY_USB --convert-only

# Keep originals after conversion
python patcher.py /Volumes/MY_USB --keep-originals
```

## Workflow

1. Export your playlist to USB from Rekordbox
2. Run: `python patcher.py /Volumes/YOUR_USB`
3. Eject and plug into your CDJ ✅

## License

MIT
