#!/usr/bin/env -S python

"""
PDF Folder Scanner

Scans a folder for PDF files and outputs a JSONLines file with file information.
Each line in the output file is a JSON object containing details about a PDF file.
If no output file is specified, writes to stdout.
"""

import argparse
import datetime
import json
import signal
import sys
from pathlib import Path


def scan_for_pdfs(
    folder_path,
    f_out,
    recursive=True,
    include_metadata=True,
    file_filter=[],
    verbose=False,
):
    """
    Scan a folder for PDF files and return a list of file information.

    Args:
        folder_path: Path to the folder to scan
        recursive: Whether to scan subfolders recursively
        include_metadata: Whether to include file metadata

    Returns:
        List of dictionaries containing file information
    """
    folder_path = Path(folder_path).resolve()
    results = []

    # Check if folder exists
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"The path '{folder_path}' is not a valid directory", file=sys.stderr)
        return None

    # Determine the glob pattern based on recursion preference
    pattern = "**/*.pdf" if recursive else "*.pdf"

    # Scan for PDF files
    for pdf_path in folder_path.glob(pattern):
        if pdf_path.is_file() and str(pdf_path) not in file_filter:
            file_info = {
                "file_path": str(pdf_path),
                "file_name": pdf_path.name,
                "directory": str(pdf_path.parent),
            }

            # Add metadata if requested
            if include_metadata:
                stat = pdf_path.stat()
                file_info.update(
                    {
                        "_metadata": {
                            "size_bytes": stat.st_size,
                            "created_time": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "accessed_time": datetime.datetime.fromtimestamp(stat.st_atime).isoformat(),
                        }
                    }
                )

            f_out.write(json.dumps(file_info) + "\n")
            f_out.flush()
            results.append(file_info)

    return results


def main():
    # Handle broken pipe gracefully when piping to commands like `first`
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = argparse.ArgumentParser(description="Scan PDFs in folder and write the list as JSONLines")
    parser.add_argument("folder", help="Folder to scan for PDF files")
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file (default: stdout)",
    )
    parser.add_argument("-f", "--filter", help="Use this JSONLines file as a filter")
    parser.add_argument("-r", "--recursive", action="store_true", help="Scan subfolders recursively")
    parser.add_argument("--no-metadata", action="store_true", help="Don't include file metadata")
    parser.add_argument("-v", "--verbose", default=False, action="store_true", help="Be verbose")

    args = parser.parse_args()

    if args.output and args.verbose:
        print(f"Scanning {args.folder} for PDF files...", file=sys.stderr)

    file_filter = []
    if args.filter:
        with open(args.filter, "r", encoding="utf-8") as f:
            for line in f.readlines():
                file_filter += [json.loads(line)["file_path"]]

    results = scan_for_pdfs(
        args.folder,
        args.output,
        recursive=args.recursive,
        include_metadata=not args.no_metadata,
        file_filter=file_filter,
        verbose=args.verbose,
    )

    if args.output and args.verbose:
        print(f"Found {len(results)} PDF files", file=sys.stderr)
    if args.output and args.verbose:
        print(f"Results written to {args.output}", file=sys.stderr)

    if args.output is not sys.stdout:
        args.output.close()

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
