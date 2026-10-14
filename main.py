#!/usr/bin/env python3
"""
FMOD Bank Audio Extractor
Extracts native audio streams (Vorbis .ogg, PCM .wav, etc.) from Unity / FMOD Studio .bank files.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
import fsb5



def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing or replacing invalid filesystem characters."""
    invalid_chars = '<>:"/\\|?*\0'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name.strip()


def extract_bank(bank_path: Path, output_dir: Path, convert_format: str = None) -> list:
    """Extract audio files from a single .bank file."""
    with open(bank_path, "rb") as f:
        data = f.read()

    fsb_offset = data.find(b"FSB5")
    if fsb_offset == -1:
        return []

    try:
        fsb = fsb5.load(data[fsb_offset:])
    except Exception as e:
        print(f"  [!] Failed to parse FSB5 structure in {bank_path.name}: {e}")
        return []

    ext = fsb.get_sample_extension() or "ogg"
    bank_folder = output_dir / bank_path.stem
    bank_folder.mkdir(parents=True, exist_ok=True)

    extracted_files = []
    print(f"[*] Processing {bank_path.name} ({len(fsb.samples)} audio tracks, format: {ext})...")

    for idx, sample in enumerate(fsb.samples):
        clean_name = sanitize_filename(sample.name) or f"sample_{idx:03d}"
        raw_filename = f"{clean_name}.{ext}"
        target_path = bank_folder / raw_filename

        try:
            sample_bytes = fsb.rebuild_sample(sample)
            with open(target_path, "wb") as out_f:
                out_f.write(sample_bytes)

            final_path = target_path
            # Optional conversion using ffmpeg
            if convert_format and convert_format.lower() != ext.lower():
                conv_filename = f"{clean_name}.{convert_format.lower()}"
                conv_path = bank_folder / conv_filename
                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(target_path),
                    str(conv_path)
                ]
                res = subprocess.run(cmd)
                if res.returncode == 0:
                    target_path.unlink()  # remove intermediate raw file
                    final_path = conv_path
                else:
                    print(f"  [!] ffmpeg conversion failed for {clean_name}, keeping .{ext}")

            extracted_files.append(final_path)
        except Exception as e:
            print(f"  [!] Error extracting '{sample.name}': {e}")

    return extracted_files


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio files from FMOD .bank files (Unity sound banks)"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=".",
        help="Input .bank file or directory containing .bank files (default: current directory)"
    )
    parser.add_argument(
        "-o", "--output",
        default="extracted_audio",
        help="Output directory (default: extracted_audio)"
    )
    parser.add_argument(
        "-c", "--convert",
        choices=["wav", "mp3", "flac"],
        default=None,
        help="Optional: Convert audio to specified format using ffmpeg (e.g. wav, mp3)"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if input_path.is_file():
        bank_files = [input_path]
    elif input_path.is_dir():
        bank_files = sorted(list(input_path.glob("*.bank")))
    else:
        print(f"Error: Path '{input_path}' not found.")
        sys.exit(1)

    if not bank_files:
        print(f"No .bank files found in '{input_path}'.")
        sys.exit(0)

    print(f"Found {len(bank_files)} bank file(s). Target output: '{output_dir.resolve()}'")
    if args.convert:
        print(f"Conversion target: {args.convert.upper()} (via ffmpeg)")

    total_extracted = 0
    results_summary = {}

    for b in bank_files:
        extracted = extract_bank(b, output_dir, args.convert)
        results_summary[b.name] = len(extracted)
        total_extracted += len(extracted)

    print("\n" + "=" * 50)
    print("EXTRACTION SUMMARY:")
    print("=" * 50)
    for bname, count in results_summary.items():
        if count > 0:
            print(f"  ✓ {bname:25s} : {count} tracks extracted")
        else:
            print(f"  - {bname:25s} : 0 tracks (metadata / strings bank)")

    print(f"\nTotal audio files extracted: {total_extracted}")
    print(f"Files saved in: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
