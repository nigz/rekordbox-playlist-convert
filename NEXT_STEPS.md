# Next Steps: Fixing "File Type" Display

## Current Status
- **Conversion**: Files are correctly converted (FLAC → AIFF).
- **Playback**: Tracks play correctly on CDJ.
- **Waveforms**: Analysis files are patched; waveforms and grids load correctly.
- **Issue**: CDJ track info still says **"File Type: FLAC"** (even though it's an AIFF).

## Technical Findings
In `export.pdb`, the byte immediately following the filename string acts as a "File Type ID":
- **FLAC**: `0xBB`
- **MP3**: `0x73`

Currently, we update the filename extension (`.flac` → `.aiff`) but leave this ID byte as `0xBB`. This causes the CDJ to display the wrong label.

## Next Step
We need to find the correct ID byte for **AIFF**.

### Action Item
1.  **Export one AIFF track** from Rekordbox to a USB stick.
2.  **Share the `PIONEER` folder** from that USB.
3.  I will analyze the `export.pdb` to find the ID byte for AIFF.
4.  I will update `patcher.py` to replace `0xBB` (FLAC) with the new AIFF ID.

Once done, the CDJ will correctly display "File Type: AIFF".
