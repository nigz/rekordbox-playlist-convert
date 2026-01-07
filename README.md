# Rekordbox Playlist Convert

A tool to convert FLAC tracks to AIFF/MP3 for Rekordbox USB exports, preserving all hot cues, memory points, and beatgrids.

## The Problem

CDJ-2000 Nexus 1 and other older players don't support FLAC files. If you maintain a FLAC library in Rekordbox, you need to convert files when exporting to USB—but re-importing breaks your carefully set cue points.

## The Solution

This tool patches the `export.pdb` database directly after you convert the files, swapping `.flac` references to `.aiff` (or `.mp3`). Since both extensions have the same byte length, the binary offsets remain intact and your cues are preserved.

## Usage

1. Export your playlist to USB from Rekordbox as normal
2. Convert FLAC files on the USB to AIFF using XLD or FFmpeg
3. Run the patcher script to update the database

```bash
python patcher.py /Volumes/YOUR_USB/PIONEER/Rekordbox/export.pdb
```

## Requirements

- Python 3.8+
- XLD or FFmpeg (for file conversion)

## License

MIT
