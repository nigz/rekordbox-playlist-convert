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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Formats that need conversion to AIFF (5 chars → 5 chars)
CONVERT_TO_AIFF = {".flac", ".alac"}

# Formats that need conversion to MP3 (4 chars → 4 chars)  
CONVERT_TO_MP3 = {".m4a", ".ogg", ".wma"}

# Formats already compatible (no conversion needed)
COMPATIBLE_FORMATS = {".mp3", ".aiff", ".aif", ".wav"}

# All convertible formats
CONVERTIBLE_FORMATS = CONVERT_TO_AIFF | CONVERT_TO_MP3

# All known audio formats
KNOWN_AUDIO_FORMATS = CONVERTIBLE_FORMATS | COMPATIBLE_FORMATS


def get_target_format(src_ext: str) -> str:
    """Get the appropriate target format based on source extension."""
    src_ext = src_ext.lower()
    if src_ext in CONVERT_TO_AIFF:
        return "aiff"
    elif src_ext in CONVERT_TO_MP3:
        return "mp3"
    else:
        return ""  # No conversion needed


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
    
    # Use specific extension globs for speed (avoid checking every file)
    for ext in CONVERTIBLE_FORMATS:
        pattern = f"**/*{ext}"
        for f in contents_dir.glob(pattern):
            if not f.name.startswith("._"):  # Skip macOS metadata
                convertible.append(f)
    
    for ext in COMPATIBLE_FORMATS:
        pattern = f"**/*{ext}"
        for f in contents_dir.glob(pattern):
            if not f.name.startswith("._"):
                compatible.append(f)
    
    return convertible, compatible, set()  # Skip unknown detection for speed


def convert_file(src: Path, target_format: str, delete_original: bool = True) -> Tuple[bool, Path, str]:
    """
    Convert a single audio file to the target format using FFmpeg.
    
    Args:
        src: Source file path
        target_format: Target format ('aiff' or 'mp3')
        delete_original: Whether to delete the source file after conversion
        
    Returns:
        Tuple of (success, output_path, filename)
    """
    dst = src.with_suffix(f".{target_format}")
    
    # Base FFmpeg command with optimizations
    base_cmd = [
        "ffmpeg",
        "-threads", "0",  # Use all available CPU cores
        "-i", str(src),
    ]
    
    # FFmpeg command based on target format
    if target_format == "aiff":
        cmd = base_cmd + [
            "-c:a", "pcm_s16be",  # Standard AIFF codec
            "-y",  # Overwrite
            str(dst)
        ]
    elif target_format == "mp3":
        cmd = base_cmd + [
            "-c:a", "libmp3lame",
            "-b:a", "320k",  # CBR 320kbps
            "-compression_level", "0",  # Fastest encoding
            "-y",
            str(dst)
        ]
    else:
        return False, dst, src.name
    
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )
        
        if delete_original and dst.exists():
            src.unlink()
            
        return True, dst, src.name
        
    except subprocess.CalledProcessError as e:
        return False, dst, src.name


def convert_all_files(contents_dir: Path, keep_originals: bool = False, max_workers: int = None) -> Tuple[int, int, int, Dict[str, str]]:
    """
    Convert all audio files in the Contents directory using parallel processing.
    Auto-selects target format based on source extension length.
    
    Args:
        contents_dir: Directory containing audio files
        keep_originals: Whether to keep original files after conversion
        max_workers: Max parallel conversions (default: CPU count)
    
    Returns:
        Tuple of (successful_count, skipped_count, failed_count, ext_mappings)
    """
    convertible, compatible, unknown_exts = find_audio_files(contents_dir)
    
    # Report unknown extensions
    if unknown_exts:
        print(f"\n⚠️  Unknown file types found: {', '.join(sorted(unknown_exts))}")
        print("   These files will be ignored.\n")
    
    # Report compatible files
    if compatible:
        by_compat: Dict[str, int] = {}
        for f in compatible:
            ext = f.suffix.lower()
            by_compat[ext] = by_compat.get(ext, 0) + 1
        compat_summary = ", ".join(f"{count} {ext}" for ext, count in sorted(by_compat.items()))
        print(f"Found {len(compatible)} file(s) already compatible: {compat_summary}")
    
    if not convertible:
        print("No files need conversion.")
        return 0, len(compatible), 0, {}
    
    # Group by extension and show conversion plan
    by_ext: Dict[str, int] = {}
    ext_mappings: Dict[str, str] = {}  # old_ext -> new_ext
    for f in convertible:
        ext = f.suffix.lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1
        if ext not in ext_mappings:
            ext_mappings[ext] = f".{get_target_format(ext)}"
    
    print(f"Found {len(convertible)} file(s) to convert:")
    for ext, count in sorted(by_ext.items()):
        target = ext_mappings[ext]
        print(f"   {count} {ext} → {target}")
    
    # Determine worker count
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 8)  # Cap at 8 to avoid I/O bottleneck
    
    print(f"\n🚀 Converting with {max_workers} parallel workers...")
    
    success_count = 0
    fail_count = 0
    failed_files: List[str] = []
    total = len(convertible)
    
    import threading
    import sys
    progress_lock = threading.Lock()
    completed = [0]  # Use list to allow mutation in nested function
    
    # Print initial progress bar
    sys.stdout.write(f"\r[{'░' * 20}] 0/{total} (0%) - Starting...{' ' * 20}")
    sys.stdout.flush()
    
    def do_convert(audio_file: Path) -> Tuple[bool, str]:
        target_format = get_target_format(audio_file.suffix)
        success, _, name = convert_file(audio_file, target_format, delete_original=not keep_originals)
        
        with progress_lock:
            completed[0] += 1
            pct = int(completed[0] / total * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            short_name = name[:30] if len(name) <= 30 else name[:27] + "..."
            sys.stdout.write(f"\r[{bar}] {completed[0]}/{total} ({pct}%) - {short_name:<30}")
            sys.stdout.flush()
        
        return success, name
    
    # Run conversions in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(do_convert, f) for f in convertible]
        
        for future in as_completed(futures):
            success, name = future.result()
            if success:
                success_count += 1
            else:
                fail_count += 1
                failed_files.append(name)
    
    print()  # New line after progress bar
    
    if failed_files:
        print(f"\n⚠️  Failed files: {', '.join(failed_files)}")
    
    return success_count, len(compatible), fail_count, ext_mappings


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
        description="Convert audio files and patch Rekordbox export.pdb",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Auto-converts based on extension length (to preserve DB offsets):
  FLAC, ALAC (5 chars) → AIFF (5 chars)
  M4A, OGG, WMA (4 chars) → MP3 (4 chars)
  WAV, MP3, AIFF → kept as-is (already compatible)

Examples:
  # Full workflow: convert files and patch database
  python patcher.py /Volumes/MY_USB
  
  # Only patch the database (files already converted manually)
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
        help="Keep original files after conversion"
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
    print("-" * 40)
    
    # Step 1: Convert files
    ext_mappings: Dict[str, str] = {}
    if not args.patch_only:
        print("\n📀 Scanning for audio files...")
        
        success, skipped, failed, ext_mappings = convert_all_files(
            contents_dir,
            keep_originals=args.keep_originals
        )
        print(f"\n✓ Converted: {success}, Skipped: {skipped}, Failed: {failed}")
        
        if failed > 0 and not args.convert_only:
            print("Warning: Some files failed to convert. Database may be inconsistent.")
    
    # Step 2: Patch database
    if not args.convert_only:
        print("\n📝 Patching database...")
        
        # Use mappings from conversion, or scan for defaults if patch-only
        if not ext_mappings:
            # Patch-only mode: try all known convertible formats
            for old_ext in CONVERTIBLE_FORMATS:
                target = get_target_format(old_ext)
                if target:
                    ext_mappings[old_ext] = f".{target}"
        
        patched_any = False
        for old_ext, new_ext in sorted(ext_mappings.items()):
            if patch_pdb(pdb_path, old_ext, new_ext):
                patched_any = True
        
        if patched_any:
            print("\n✅ Done! USB is ready for CDJ.")
        else:
            print("\n✅ Done! No database changes needed.")


if __name__ == "__main__":
    main()


