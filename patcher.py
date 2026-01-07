#!/usr/bin/env python3
"""
Rekordbox PDB Patcher

Converts audio files to AIFF/MP3 and patches the export.pdb database
to swap file extensions without breaking cues or beatgrids.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Known audio formats that can be converted
CONVERTIBLE_FORMATS = {".flac", ".wav", ".m4a", ".ogg", ".wma", ".alac"}

# Formats already compatible (no conversion needed, just patch DB if needed)  
COMPATIBLE_FORMATS = {".mp3", ".aiff", ".aif"}

# All known audio formats
KNOWN_AUDIO_FORMATS = CONVERTIBLE_FORMATS | COMPATIBLE_FORMATS


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def find_audio_files(contents_dir: Path) -> Tuple[List[Path], List[Path], Set[str]]:
    """
    Find all audio files in the Contents directory.
    
    Returns:
        Tuple of (convertible_files, compatible_files, unknown_extensions)
    """
    convertible = []
    compatible = []
    unknown_exts: Set[str] = set()
    
    for file in contents_dir.rglob("*"):
        if not file.is_file():
            continue
            
        ext = file.suffix.lower()
        
        if ext in CONVERTIBLE_FORMATS:
            convertible.append(file)
        elif ext in COMPATIBLE_FORMATS:
            compatible.append(file)
        elif ext and not ext.startswith("."):
            # Skip non-files
            continue
        elif ext and ext not in {".db", ".pdb", ".xml", ".txt", ".dat", ".edb"}:
            # Track unknown extensions (ignore known non-audio files)
            unknown_exts.add(ext)
    
    return convertible, compatible, unknown_exts


def convert_file(src: Path, target_format: str, delete_original: bool = True) -> Tuple[bool, Path]:
    """
    Convert a single audio file to the target format using FFmpeg.
    
    Args:
        src: Source file path
        target_format: Target format ('aiff' or 'mp3')
        delete_original: Whether to delete the source file after conversion
        
    Returns:
        Tuple of (success, output_path)
    """
    dst = src.with_suffix(f".{target_format}")
    
    # FFmpeg command based on target format
    if target_format == "aiff":
        cmd = [
            "ffmpeg", "-i", str(src),
            "-c:a", "pcm_s16be",  # Standard AIFF codec
            "-y",  # Overwrite
            str(dst)
        ]
    elif target_format == "mp3":
        cmd = [
            "ffmpeg", "-i", str(src),
            "-c:a", "libmp3lame",
            "-b:a", "320k",  # CBR 320kbps
            "-y",
            str(dst)
        ]
    else:
        print(f"Error: Unsupported format '{target_format}'")
        return False, dst
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )
        
        if delete_original and dst.exists():
            src.unlink()
            
        return True, dst
        
    except subprocess.CalledProcessError as e:
        print(f"Error converting {src.name}: {e.stderr.decode()}")
        return False, dst


def convert_all_files(contents_dir: Path, target_format: str, keep_originals: bool = False) -> Tuple[int, int, int]:
    """
    Convert all audio files in the Contents directory.
    
    Returns:
        Tuple of (successful_count, skipped_count, failed_count)
    """
    convertible, compatible, unknown_exts = find_audio_files(contents_dir)
    
    # Report unknown extensions
    if unknown_exts:
        print(f"\n⚠️  Unknown file types found: {', '.join(sorted(unknown_exts))}")
        print("   These files will be ignored.\n")
    
    # Report compatible files
    if compatible:
        print(f"Found {len(compatible)} file(s) already in compatible format")
    
    if not convertible:
        print("No files need conversion.")
        return 0, len(compatible), 0
    
    # Group by extension for reporting
    by_ext: Dict[str, int] = {}
    for f in convertible:
        ext = f.suffix.lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1
    
    ext_summary = ", ".join(f"{count} {ext}" for ext, count in sorted(by_ext.items()))
    print(f"Found {len(convertible)} file(s) to convert: {ext_summary}")
    
    success_count = 0
    fail_count = 0
    
    for i, audio_file in enumerate(convertible, 1):
        print(f"[{i}/{len(convertible)}] Converting: {audio_file.name}")
        success, _ = convert_file(audio_file, target_format, delete_original=not keep_originals)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    return success_count, len(compatible), fail_count


def patch_pdb(file_path: Path, old_ext: str, new_ext: str) -> bool:
    """
    Patch a Rekordbox export.pdb file, replacing one extension with another.
    
    Args:
        file_path: Path to the export.pdb file
        old_ext: Extension to replace (e.g., ".flac")
        new_ext: New extension (e.g., ".aiff")
        
    Returns:
        True if patching was successful, False otherwise
    """
    if not file_path.exists():
        print(f"Error: PDB file not found at {file_path}")
        return False
    
    # Validate extension lengths match
    if len(old_ext) != len(new_ext):
        print(f"Error: Extensions must be same length ({old_ext} vs {new_ext})")
        print("This is required to preserve binary offsets in the database.")
        return False
    
    # Create backup
    backup_path = file_path.with_suffix(".pdb.backup")
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path.name}")
    
    # Read and patch
    with open(file_path, 'rb') as f:
        content = f.read()
    
    old_bytes = old_ext.encode('utf-8')
    new_bytes = new_ext.encode('utf-8')
    
    count = content.count(old_bytes)
    
    if count == 0:
        print(f"No '{old_ext}' references found in the PDB.")
        return False
    
    new_content = content.replace(old_bytes, new_bytes)
    
    with open(file_path, 'wb') as f:
        f.write(new_content)
    
    print(f"Patched {count} track reference(s): {old_ext} → {new_ext}")
    return True


def find_usb_paths(usb_path: Path) -> Tuple[Path, Path]:
    """
    Find the Contents and export.pdb paths from a USB root.
    
    Args:
        usb_path: Path to USB root (e.g., /Volumes/MY_USB)
        
    Returns:
        Tuple of (contents_dir, pdb_path)
    """
    contents_dir = usb_path / "Contents"
    pdb_path = usb_path / "PIONEER" / "rekordbox" / "export.pdb"
    
    # Try alternate casing
    if not pdb_path.exists():
        pdb_path = usb_path / "PIONEER" / "Rekordbox" / "export.pdb"
    if not pdb_path.exists():
        pdb_path = usb_path / "PIONEER" / "REKORDBOX" / "export.pdb"
    
    return contents_dir, pdb_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert FLAC files and patch Rekordbox export.pdb",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full workflow: convert files and patch database
  python patcher.py /Volumes/MY_USB
  
  # Convert to MP3 instead of AIFF
  python patcher.py /Volumes/MY_USB --format mp3
  
  # Only patch the database (files already converted)
  python patcher.py /Volumes/MY_USB --patch-only
  
  # Only convert files (don't patch database)
  python patcher.py /Volumes/MY_USB --convert-only
"""
    )
    
    parser.add_argument(
        "usb_path",
        type=Path,
        help="Path to USB drive root (e.g., /Volumes/MY_USB)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["aiff", "mp3"],
        default="aiff",
        help="Target audio format (default: aiff)"
    )
    parser.add_argument(
        "--patch-only",
        action="store_true",
        help="Only patch the database, skip file conversion"
    )
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help="Only convert files, skip database patching"
    )
    parser.add_argument(
        "--keep-originals",
        action="store_true",
        help="Keep original FLAC files after conversion"
    )
    
    args = parser.parse_args()
    
    # Validate USB path
    if not args.usb_path.exists():
        print(f"Error: Path not found: {args.usb_path}")
        sys.exit(1)
    
    # Find paths
    contents_dir, pdb_path = find_usb_paths(args.usb_path)
    
    # Check FFmpeg if we need to convert
    if not args.patch_only:
        if not check_ffmpeg():
            print("Error: FFmpeg not found. Install with: brew install ffmpeg")
            sys.exit(1)
        
        if not contents_dir.exists():
            print(f"Error: Contents directory not found: {contents_dir}")
            sys.exit(1)
    
    # Check PDB if we need to patch
    if not args.convert_only:
        if not pdb_path.exists():
            print(f"Error: export.pdb not found: {pdb_path}")
            sys.exit(1)
    
    print(f"USB: {args.usb_path}")
    print(f"Target format: {args.format.upper()}")
    print("-" * 40)
    
    # Step 1: Convert files
    converted_exts: Set[str] = set()
    if not args.patch_only:
        print("\n📀 Scanning for audio files...")
        
        # Get list of what we'll convert for patching later
        convertible, _, _ = find_audio_files(contents_dir)
        converted_exts = {f.suffix.lower() for f in convertible}
        
        success, skipped, failed = convert_all_files(
            contents_dir, 
            args.format,
            keep_originals=args.keep_originals
        )
        print(f"\n✓ Converted: {success}, Skipped: {skipped}, Failed: {failed}")
        
        if failed > 0 and not args.convert_only:
            print("Warning: Some files failed to convert. Database may be inconsistent.")
    
    # Step 2: Patch database
    if not args.convert_only:
        print("\n📝 Patching database...")
        new_ext = f".{args.format}"
        
        # Patch all convertible extensions
        patched_any = False
        for old_ext in sorted(converted_exts or CONVERTIBLE_FORMATS):
            if len(old_ext) == len(new_ext):
                if patch_pdb(pdb_path, old_ext, new_ext):
                    patched_any = True
            else:
                print(f"⚠️  Cannot patch {old_ext} → {new_ext} (different lengths)")
        
        if patched_any:
            print("\n✅ Done! USB is ready for CDJ.")
        else:
            print("\n⚠️  No extensions were patched.")


if __name__ == "__main__":
    main()

