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
    folder_count = 0
    
    print(f"Scanning: {contents_dir}", end="", flush=True)
    
    # Use os.walk for fast traversal (faster than glob on USB)
    for root, dirs, files in os.walk(contents_dir):
        folder_count += 1
        if folder_count % 50 == 0:  # Show progress every 50 folders
            print(".", end="", flush=True)
        
        for name in files:
            # Skip macOS metadata files
            if name.startswith("._"):
                continue
            
            ext = os.path.splitext(name)[1].lower()
            filepath = Path(root) / name
            
            if ext in CONVERTIBLE_FORMATS:
                convertible.append(filepath)
            elif ext in COMPATIBLE_FORMATS:
                compatible.append(filepath)
    
    print(f" done! ({folder_count} folders)")
    return convertible, compatible, set()


def convert_file(src: Path, target_format: str, delete_original: bool = True) -> Tuple[bool, Path, str, str]:
    """
    Convert a single audio file to the target format using FFmpeg.
    
    Args:
        src: Source file path
        target_format: Target format ('aiff' or 'mp3')
        delete_original: Whether to delete the source file after conversion
        
    Returns:
        Tuple of (success, output_path, filename, error_msg)
    """
    dst = src.with_suffix(f".{target_format}")
    
    # Base FFmpeg command with optimizations
    base_cmd = [
        "ffmpeg",
        "-loglevel", "error",  # Only show errors
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
        return False, dst, src.name, f"Unsupported format: {target_format}"
    
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,  # Prevent FFmpeg from waiting for input
            capture_output=True,
            check=True,
            timeout=300  # 5 minute timeout per file
        )
        
        if delete_original and dst.exists():
            src.unlink()
            
        return True, dst, src.name, ""
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        return False, dst, src.name, error_msg
    except subprocess.TimeoutExpired:
        return False, dst, src.name, "Timeout (>5min)"


def convert_all_files(contents_dir: Path, keep_originals: bool = False, max_workers: int = None, on_device: bool = False) -> Tuple[int, int, int, Dict[str, str]]:
    """
    Convert all audio files. By default uses SSD caching for speed.
    
    Args:
        contents_dir: Directory containing audio files
        keep_originals: Whether to keep original files after conversion
        max_workers: Max parallel conversions (default: 8 for SSD, 2 for on-device)
        on_device: If True, convert directly on USB (slower but no temp space needed)
    
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
    
    total = len(convertible)
    
    if on_device:
        # Direct on-device conversion (slower)
        workers = max_workers if max_workers else 2
        return _convert_on_device(convertible, total, workers, keep_originals, compatible, ext_mappings)
    else:
        # SSD-cached conversion (faster)
        workers = max_workers if max_workers else 8
        return _convert_with_ssd_cache(convertible, contents_dir, total, workers, keep_originals, compatible, ext_mappings)


def _convert_on_device(convertible: List[Path], total: int, workers: int, keep_originals: bool, compatible: List[Path], ext_mappings: Dict[str, str]) -> Tuple[int, int, int, Dict[str, str]]:
    """Convert files directly on USB (slower, less temp space needed)."""
    print(f"\n🚀 Converting {total} file(s) on device with {workers} workers...\n")
    
    success_count = 0
    fail_count = 0
    failed_files: List[str] = []
    errors: List[str] = []
    completed = [0]
    
    import threading
    lock = threading.Lock()
    
    def convert_one(audio_file: Path) -> Tuple[bool, str, str]:
        target_format = get_target_format(audio_file.suffix)
        success, _, name, error = convert_file(audio_file, target_format, delete_original=not keep_originals)
        
        with lock:
            completed[0] += 1
            pct = int(completed[0] / total * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            short_name = name[:30] if len(name) <= 30 else name[:27] + "..."
            print(f"\r[{bar}] {completed[0]}/{total} ({pct}%) - {short_name:<30}", end="", flush=True)
        
        return success, name, error
    
    print(f"[{'░' * 20}] 0/{total} (0%) - Starting...", end="", flush=True)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(convert_one, f) for f in convertible]
        for future in as_completed(futures):
            success, name, error = future.result()
            if success:
                success_count += 1
            else:
                fail_count += 1
                failed_files.append(name)
                if error:
                    errors.append(f"{name}: {error[:50]}")
    
    print()
    
    if failed_files:
        print(f"\n⚠️  Failed: {len(failed_files)} file(s)")
        for err in errors[:5]:
            print(f"   {err}")
    
    return success_count, len(compatible), fail_count, ext_mappings


def _convert_with_ssd_cache(convertible: List[Path], contents_dir: Path, total: int, workers: int, keep_originals: bool, compatible: List[Path], ext_mappings: Dict[str, str]) -> Tuple[int, int, int, Dict[str, str]]:
    """Convert files using local SSD for speed, then copy to USB."""
    
    # Create temp directory in script folder
    script_dir = Path(__file__).parent
    temp_dir = script_dir / ".convert_cache"
    temp_dir.mkdir(exist_ok=True)
    
    print(f"\n🚀 Converting {total} file(s) (SSD-cached, {workers} workers)...")
    print(f"   Cache: {temp_dir}\n")
    
    success_count = 0
    fail_count = 0
    failed_files: List[str] = []
    errors: List[str] = []
    completed = [0]
    converted_files: List[Tuple[Path, Path]] = []  # (temp_file, usb_dest)
    
    import threading
    lock = threading.Lock()
    
    def convert_one(audio_file: Path) -> Tuple[bool, str, str, Path, Path]:
        """Convert to temp dir, return paths for later copy."""
        target_format = get_target_format(audio_file.suffix)
        
        # Determine paths
        rel_path = audio_file.relative_to(contents_dir)
        temp_file = temp_dir / rel_path.with_suffix(f".{target_format}")
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        usb_dest = audio_file.with_suffix(f".{target_format}")
        
        # Build FFmpeg command
        base_cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-threads", "0",
            "-i", str(audio_file),
        ]
        
        if target_format == "aiff":
            cmd = base_cmd + ["-c:a", "pcm_s16be", "-y", str(temp_file)]
        elif target_format == "mp3":
            cmd = base_cmd + ["-c:a", "libmp3lame", "-b:a", "320k", "-compression_level", "0", "-y", str(temp_file)]
        else:
            return False, audio_file.name, f"Unknown format: {target_format}", temp_file, usb_dest
        
        try:
            subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=300)
            
            with lock:
                completed[0] += 1
                pct = int(completed[0] / total * 100)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                short_name = audio_file.name[:30] if len(audio_file.name) <= 30 else audio_file.name[:27] + "..."
                print(f"\r[{bar}] {completed[0]}/{total} ({pct}%) - {short_name:<30}", end="", flush=True)
            
            return True, audio_file.name, "", temp_file, usb_dest
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            return False, audio_file.name, error_msg, temp_file, usb_dest
        except subprocess.TimeoutExpired:
            return False, audio_file.name, "Timeout", temp_file, usb_dest
    
    # Step 1: Convert all files to SSD (fast, parallel)
    print(f"[{'░' * 20}] 0/{total} (0%) - Starting...", end="", flush=True)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(convert_one, f) for f in convertible]
        for future in as_completed(futures):
            success, name, error, temp_file, usb_dest = future.result()
            if success:
                success_count += 1
                converted_files.append((temp_file, usb_dest))
            else:
                fail_count += 1
                failed_files.append(name)
                if error:
                    errors.append(f"{name}: {error[:50]}")
    
    print()
    
    if fail_count > 0:
        print(f"\n⚠️  Failed: {fail_count} file(s)")
        for err in errors[:5]:
            print(f"   {err}")
    
    # Step 2: Copy converted files to USB
    if converted_files:
        print(f"\n📦 Copying {len(converted_files)} file(s) to USB...")
        print(f"[{'░' * 20}] 0/{len(converted_files)} (0%)", end="", flush=True)
        
        for i, (temp_file, usb_dest) in enumerate(converted_files, 1):
            shutil.copy2(temp_file, usb_dest)
            
            pct = int(i / len(converted_files) * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"\r[{bar}] {i}/{len(converted_files)} ({pct}%)", end="", flush=True)
        
        print()
        
        # Step 3: Delete originals from USB (if not keeping)
        if not keep_originals:
            print(f"🗑️  Removing {len(convertible)} original file(s)...")
            for audio_file in convertible:
                if audio_file.exists():
                    audio_file.unlink()
        
        # Step 4: Clean up temp directory
        print("🧹 Cleaning up cache...")
        shutil.rmtree(temp_dir, ignore_errors=True)
    
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


def find_usb_paths(usb_path: Path) -> Tuple[Path, List[Path]]:
    """
    Find the Contents and all relevant PDB paths from a USB root.
    
    Args:
        usb_path: Path to USB root (e.g., /Volumes/MY_USB)
        
    Returns:
        Tuple of (contents_dir, list_of_pdb_paths)
    """
    contents_dir = usb_path / "Contents"
    
    # Check casing for PIONEER/rekordbox
    rekordbox_dir = usb_path / "PIONEER" / "rekordbox"
    if not rekordbox_dir.exists():
        rekordbox_dir = usb_path / "PIONEER" / "Rekordbox"
    if not rekordbox_dir.exists():
        rekordbox_dir = usb_path / "PIONEER" / "REKORDBOX"
    
    pdb_paths = []
    if rekordbox_dir.exists():
        # Patch ALL PDB files (export.pdb, exportExt.pdb, export.modify.pdb, etc.)
        for pdb in rekordbox_dir.glob("*.pdb"):
            if not pdb.name.endswith(".backup"):
                pdb_paths.append(pdb)
    
    return contents_dir, pdb_paths


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
  
  # Keep originals after conversion
  python patcher.py /Volumes/MY_USB --keep-originals
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
    parser.add_argument(
        "--on-device",
        action="store_true",
        help="Convert directly on USB (slower, but no temp space needed)"
    )
    
    args = parser.parse_args()
    
    # Validate USB path
    if not args.usb_path.exists():
        print(f"Error: Path not found: {args.usb_path}")
        sys.exit(1)
    
    # Find paths
    contents_dir, pdb_paths = find_usb_paths(args.usb_path)
    
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
        if not pdb_paths:
            print(f"Error: No export.pdb or exportExt.pdb found in PIONEER/rekordbox location.")
            sys.exit(1)
    
    print(f"USB: {args.usb_path}")
    print("-" * 40)
    
    # Step 1: Convert files
    ext_mappings: Dict[str, str] = {}
    if not args.patch_only:
        print("\n📀 Scanning for audio files...")
        
        success, skipped, failed, ext_mappings = convert_all_files(
            contents_dir,
            keep_originals=args.keep_originals,
            on_device=args.on_device
        )
        print(f"\n✓ Converted: {success}, Skipped: {skipped}, Failed: {failed}")
        
        if failed > 0 and not args.convert_only:
            print("Warning: Some files failed to convert. Database may be inconsistent.")
    
    # Step 2: Patch Database
    if not args.convert_only:
        print("\n📝 Patching database...")
        
        if not ext_mappings:
            # If we didn't run conversion, scan convertible files to infer what mappings are needed
            # Or we could just attempt patching common mappings:
            # FLAC->AIFF, ALAC->AIFF, M4A->MP3, etc.
            # For simplicity, let's look for convertible files again to build the map if empty
            if not args.patch_only: # If we just converted, mappings might be empty if no files needed conversion
                pass # Already empty
            else:
                # If patch-only, we need to infer mappings or assume standard ones
                print("   (Inferring mappings for patch-only mode...)")
                ext_mappings = {
                    ".flac": ".aiff",
                    ".alac": ".aiff",
                    ".m4a": ".mp3",
                    ".ogg": ".mp3",
                    ".wma": ".mp3"
                }
        
        if not ext_mappings:
            print("   No text mappings found/needed. Skipping patch.")
        else:
            total_patched_files = 0
            for pdb_path in pdb_paths:
                print(f"   Target: {pdb_path.name}")
                patched_any = False
                
                for old_ext, new_ext in ext_mappings.items():
                    print(f"   Patching: {old_ext} → {new_ext}")
                    if patch_pdb(pdb_path, old_ext, new_ext):
                        patched_any = True
                
                if patched_any:
                    total_patched_files += 1
            
            if total_patched_files == 0:
                print("   ⚠️  No changes made to any PDB files.")
            else:
                print("   ✓ Database patching complete.")

    print("\n✅ All done! USB is ready for CDJ.")


if __name__ == "__main__":
    main()
