#!/usr/bin/env python3
"""
Rekordbox PDB Patcher

Converts FLAC files to AIFF/MP3 and patches the export.pdb database
to swap file extensions without breaking cues or beatgrids.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple


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


def find_flac_files(contents_dir: Path) -> List[Path]:
    """Find all FLAC files in the Contents directory."""
    return list(contents_dir.rglob("*.flac"))


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


def convert_all_files(contents_dir: Path, target_format: str) -> Tuple[int, int]:
    """
    Convert all FLAC files in the Contents directory.
    
    Returns:
        Tuple of (successful_count, failed_count)
    """
    flac_files = find_flac_files(contents_dir)
    
    if not flac_files:
        print("No FLAC files found.")
        return 0, 0
    
    print(f"Found {len(flac_files)} FLAC file(s) to convert")
    
    success_count = 0
    fail_count = 0
    
    for i, flac_file in enumerate(flac_files, 1):
        print(f"[{i}/{len(flac_files)}] Converting: {flac_file.name}")
        success, _ = convert_file(flac_file, target_format)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    return success_count, fail_count


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
    if not args.patch_only:
        print("\n📀 Converting files...")
        success, failed = convert_all_files(
            contents_dir, 
            args.format
        )
        print(f"\n✓ Converted: {success}, Failed: {failed}")
        
        if failed > 0 and not args.convert_only:
            print("Warning: Some files failed to convert. Database may be inconsistent.")
    
    # Step 2: Patch database
    if not args.convert_only:
        print("\n📝 Patching database...")
        old_ext = ".flac"
        new_ext = f".{args.format}"
        
        if patch_pdb(pdb_path, old_ext, new_ext):
            print("\n✅ Done! USB is ready for CDJ.")
        else:
            print("\n❌ Patching failed.")
            sys.exit(1)


if __name__ == "__main__":
    main()
