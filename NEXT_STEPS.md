# Next Steps: Finishing Polish

## 1. Fix "File Type" Display
**Status**: [~] Partially Fixed / Known Limitation
**Findings**: 
1. The "File Type ID" bytes (`0x35`/`0x33` for FLAC/MP3, `0x34` for AIFF) can be patched.
2. However, **native AIFF records** have a slightly different binary structure (an extra `0x03` byte in the header: `00 03 03 05...` vs `00 03 05...`).
3. Analysis files (`USBANLZ`) were scanned and confirmed to **NOT** contain file type IDs.
4. Structural differences in `export.pdb` prevent a perfect visual fix (cannot insert bytes without breaking DB).

**Conclusion**: The files play correctly and function as AIFFs. The "File Type: FLAC" display is a visual artifact of the original database record structure.

**Action**: No further action recommended. The script now ensures the best possible compatibility by patching the ID bytes.

## 2. Display Detected Playlists
**Goal**: The script should list the names of playlists found on the USB (e.g., "PHASE") to confirm what is being processed.

### Technical Detail
- Playlist names (like "PHASE") are visible in `export.pdb`.
- We need to identify the exact structure/offset to extract and list them reliably.

### Action Item
- Analyze `export.pdb` structure further to locate the playlist table and extract names for the CLI summary.
