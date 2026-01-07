# Rekordbox Playlist Convert

Convert audio files on Rekordbox USB exports for CDJ compatibility while preserving all hot cues, memory points, and beatgrids.

## The Problem

CDJ-2000 Nexus 1 and older players don't support FLAC. Re-importing to convert breaks your carefully set cue points.

## The Solution

This tool:
1. Converts files on the USB using FFmpeg
2. Patches the `export.pdb` and `exportExt.pdb` databases to update references
3. Updates `ANLZ` analysis files (fixing UTF-16BE paths) so waveforms load instantly
4. Preserves all your cues and beatgrids perfectly

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
# Full workflow (default: converts to local SSD cache then copies to USB)
python patcher.py /Volumes/MY_USB

# Direct USB conversion (slower but saves local disk space)
python patcher.py /Volumes/MY_USB --on-device

# Only patch (files already converted manually)
python patcher.py /Volumes/MY_USB --patch-only

# Only convert (skip database patching)
python patcher.py /Volumes/MY_USB --convert-only

# Keep originals after conversion
python patcher.py /Volumes/MY_USB --keep-originals
```

## Performance

The script uses two strategies to handle slow USB write speeds:

1.  **SSD Cache (Default)**: files are converted in parallel to a local temp folder (max speed), then bulk copied to the USB.
2.  **On Device (`--on-device`)**: files are converted directly on the USB with fewer parallel workers (slower, but requires no local disk space).

## Workflow

1. Export your playlist to USB from Rekordbox
2. Run: `python patcher.py /Volumes/YOUR_USB`
3. Eject and plug into your CDJ ✅

## License

MIT
