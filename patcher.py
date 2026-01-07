#!/usr/bin/env python3
"""
Rekordbox PDB Patcher

Patches the export.pdb database to swap file extensions
(e.g., .flac -> .aiff) without breaking cues or beatgrids.
"""

import os
import sys
import shutil
from pathlib import Path


def patch_pdb(file_path: str, old_ext: str = ".flac", new_ext: str = ".aiff") -> bool:
    """
    Patch a Rekordbox export.pdb file, replacing one extension with another.
    
    Args:
        file_path: Path to the export.pdb file
        old_ext: Extension to replace (e.g., ".flac")
        new_ext: New extension (e.g., ".aiff")
        
    Returns:
        True if patching was successful, False otherwise
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: PDB file not found at {file_path}")
        return False
    
    # Validate extension lengths match
    if len(old_ext) != len(new_ext):
        print(f"Error: Extensions must be the same length ({old_ext} vs {new_ext})")
        print("This is required to preserve binary offsets in the database.")
        return False
    
    # Create backup
    backup_path = path.with_suffix(".pdb.backup")
    shutil.copy2(path, backup_path)
    print(f"Created backup at {backup_path}")
    
    # Read and patch
    with open(path, 'rb') as f:
        content = f.read()
    
    old_bytes = old_ext.encode('utf-8')
    new_bytes = new_ext.encode('utf-8')
    
    count = content.count(old_bytes)
    
    if count == 0:
        print(f"No '{old_ext}' references found in the PDB.")
        return False
    
    new_content = content.replace(old_bytes, new_bytes)
    
    with open(path, 'wb') as f:
        f.write(new_content)
    
    print(f"Successfully patched {count} track reference(s): {old_ext} -> {new_ext}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python patcher.py <path_to_export.pdb> [old_ext] [new_ext]")
        print("")
        print("Examples:")
        print("  python patcher.py /Volumes/USB/PIONEER/Rekordbox/export.pdb")
        print("  python patcher.py /Volumes/USB/PIONEER/Rekordbox/export.pdb .flac .aiff")
        print("  python patcher.py /Volumes/USB/PIONEER/Rekordbox/export.pdb .flac .mp3_")
        sys.exit(1)
    
    pdb_path = sys.argv[1]
    old_ext = sys.argv[2] if len(sys.argv) > 2 else ".flac"
    new_ext = sys.argv[3] if len(sys.argv) > 3 else ".aiff"
    
    success = patch_pdb(pdb_path, old_ext, new_ext)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
