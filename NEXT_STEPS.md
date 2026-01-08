# Next Steps: Finishing Polish

## 1. Fix "File Type" Display
**Status**: [X] Completed
**Findings**: 
1. The "File Type ID" in `export.pdb` uses a two-byte pattern: `03 05 [ID] 05 [SEC_ID]`. 
   - FLAC/Compressed: Can be `03 05 35 05 32` OR `03 05 33 05 32`.
   - AIFF: `03 05 34 05 34` ('4' then '4')
2. "Wenu Wenu.flac" used the ID `0x33` which was previously unhandled.

**Resolution**: 
1. Updated `patcher.py` to ALL compressed IDs (`0x35`, `0x33`, etc.) to `0x34` (AIFF) for any file with `.aiff` extension.
2. It correctly sets the pattern to `03 05 34 05 34`, matching native AIFF tracks identically.

**Action**: You should re-run the patcher on your USB to apply the fix:
`python3 patcher.py /Volumes/YOUR_USB --patch-only`

## 2. Display Detected Playlists
**Goal**: The script should list the names of playlists found on the USB (e.g., "PHASE") to confirm what is being processed.

### Technical Detail
- Playlist names (like "PHASE") are visible in `export.pdb`.
- We need to identify the exact structure/offset to extract and list them reliably.

### Action Item
- Analyze `export.pdb` structure further to locate the playlist table and extract names for the CLI summary.
