# Next Steps: Finishing Polish

## 1. Fix "File Type" Display
**Status**: [X] Completed
**Findings**: 
1. The "File Type ID" in `export.pdb` uses a two-byte pattern: `03 05 [ID] 05 [SEC_ID]`. 
   - FLAC: `03 05 35 05 32` ('5' then '2')
   - AIFF: `03 05 34 05 34` ('4' then '4')

**Resolution**: 
1. Updated `patcher.py` to patch **BOTH** ID bytes (`0x35`→`0x34` and `0x32`→`0x34`) in `export.pdb`.

**Action**: You should re-run the patcher on your USB to apply the 2-byte patch:
`python3 patcher.py /Volumes/YOUR_USB --patch-only` (If files are already converted)
OR
`python3 patcher.py /Volumes/YOUR_USB` (To convert and patch)

## 2. Display Detected Playlists
**Goal**: The script should list the names of playlists found on the USB (e.g., "PHASE") to confirm what is being processed.

### Technical Detail
- Playlist names (like "PHASE") are visible in `export.pdb`.
- We need to identify the exact structure/offset to extract and list them reliably.

### Action Item
- Analyze `export.pdb` structure further to locate the playlist table and extract names for the CLI summary.
