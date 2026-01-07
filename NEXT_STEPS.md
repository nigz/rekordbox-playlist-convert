# Next Steps: Finishing Polish

## 1. Fix "File Type" Display
**Issue**: CDJ shows "File Type: FLAC" for converted AIFF files.
**Cause**: `export.pdb` has a "File Type ID" byte after the filename (`0xBB`=FLAC, `0x73`=MP3). We need to change this to the AIFF ID.

### Action Item
1.  **Export one AIFF track** from Rekordbox to a USB stick.
2.  **Share the `PIONEER` folder**.
3.  I will find the AIFF ID in `export.pdb` and update the patcher.

## 2. Display Detected Playlists
**Goal**: The script should list the names of playlists found on the USB (e.g., "PHASE") to confirm what is being processed.

### Technical Detail
- Playlist names (like "PHASE") are visible in `export.pdb`.
- We need to identify the exact structure/offset to extract and list them reliably.

### Action Item
- Analyze `export.pdb` structure further to locate the playlist table and extract names for the CLI summary.
