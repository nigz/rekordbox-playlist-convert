01, Export your Rekordbox collection to XML

2. Download XLD (it's free ware, I use it myself no affiliation with the developers).

[https://tmkk.undo.jp/xld/index_e.html](https://tmkk.undo.jp/xld/index_e.html)

XLD hast the preference to place the "converted" tracks exactly at the same place as the original. Maintaining the fileapth, which is what you need/want!

e.g. the track named test.flac stored in the folder test:

/test/test.flac becomes /test/test.mp3

Convert all the FLAC files

3. open the XML you exported in the first step in a text editor that doesn't mess with formatting. Don't use WORD! I like to use BBEdit. Do a search & replace of all the occurrences in the xml of:

replace

Kind="FLAC File"

with

Kind="MP3 File"

and replace

.flac"

with

.mp3"

Save the document (suggestion use a new name so you can easily fall back if you mess things up).

4. import the XML you modified in step 3 back into Rekordbox.

I would advice to go with MP3 CBR 320Kbs at highest quality setting, but that's just me, nothing wrong with AIFF.

## 2

https://github.com/Holzhaus/rekordcrate
https://github.com/kimtore/rex
https://djl-analysis.deepsymmetry.org/rekordbox-export-analysis/exports.html
https://github.com/dylanljones/pyrekordbox
https://github.com/Deep-Symmetry/crate-digger

## 3
I see the issue. When you export to a USB, Rekordbox generates a binary database file (`export.pdb` or the newer `OneLibrary` format) that the CDJs read. Modifying an XML in your main library doesn't help because the USB has its own independent database that still points to the FLAC files you just exported.

Since you want to **avoid a parallel library** and **modify the export directly**, the most efficient way to do this is a **Binary Patch** on the exported database.

### The "AIFF Binary Swap" Strategy

This is the "pro" way to do it without re-importing anything.

- **The Logic:** Both `.flac` and `.aiff` have the **same character length** (4 letters + the dot).
    
- **The Benefit:** Because the character count is identical, you can perform a direct binary "Find and Replace" on the `export.pdb` file without breaking the database structure or shifting memory offsets.
    
- **Why AIFF?** Unlike WAV, AIFF supports metadata (tags/cues) perfectly and is compatible with every CDJ that doesn't support FLAC (like the CDJ-2000 Nexus 1).
    

---

## The Workflow

### 1. Export as Normal

Export your playlist to your USB drive using Rekordbox as you usually do. At this point, the USB contains FLAC files and a `.pdb` database pointing to them.

### 2. Convert the Files on the USB

Use **XLD** (Mac) or **FFmpeg** to convert the FLAC files _inside_ the USB's `Contents` folder to AIFF.

- **Crucial:** Set the converter to "Delete original" or manually delete the FLACs after conversion.
    
- The filename must remain exactly the same (e.g., `01 Track.flac` becomes `01 Track.aiff`).
    

### 3. Patch the `export.pdb`

Since you mentioned `pyrekordbox`, you can use a simple Python script to swap the extensions in the binary database.

> [!WARNING]
> 
> Always back up the PIONEER folder on your USB before running scripts on the database.

#### The Python "PDB Patcher" Script:

You don't need a heavy library for this; a simple binary write will work because we are keeping the byte-count the same.

Python

```
import os

# Path to your USB's Export.pdb
# Usually: /Volumes/YOUR_USB/PIONEER/Rekordbox/export.pdb
pdb_path = "/Volumes/MY_USB_NAME/PIONEER/Rekordbox/export.pdb"

def patch_pdb(file_path):
    if not os.path.exists(file_path):
        print("PDB file not found!")
        return

    with open(file_path, 'rb') as f:
        content = f.read()

    # Binary search and replace
    # We use .flac (5 bytes) and .aiff (5 bytes)
    # This keeps the binary offsets perfectly intact
    old_ext = b'.flac'
    new_ext = b'.aiff'

    if old_ext in content:
        new_content = content.replace(old_ext, new_ext)
        
        with open(file_path, 'wb') as f:
            f.write(new_content)
        print(f"Successfully patched {content.count(old_ext)} track references.")
    else:
        print("No .flac references found in the PDB.")

patch_pdb(pdb_path)
```

---

## Why this is better than the XML method:

1. **No Library Bloat:** Your main Rekordbox library stays 100% FLAC.
    
2. **Preserves All Info:** Since you aren't re-importing, your Hot Cues, Memory Points, and Beatgrids remain exactly where they were in the original export.
    
3. **Speed:** Converting and patching takes seconds compared to the "Export -> XML -> Edit -> Import -> Re-export" loop.
    

## Alternative: Using "Lexicon"

If you find yourself doing this frequently and want a UI, the software **Lexicon** has a "Sync to USB" feature that can automatically transcode files to a compatible format (like MP3 or AIFF) _during_ the export process while keeping your main library as FLAC. It's a paid tool, but it's the only one that automates this "Parallel Export" workflow natively.

**Would you like me to refine the Python script to also handle the file conversion (FFmpeg) automatically so you just have to run one command?**

