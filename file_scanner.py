#!/usr/bin/env -S python

"""
PDF Folder Scanner

Scans a folder for PDF files and outputs a JSONLines file with file information.
Each line in the output file is a JSON object containing details about a PDF file.
If no output file is specified, writes to stdout.
"""

import sys
import json
import argparse
import datetime
from pathlib import Path


def scan_for_pdfs(folder_path, recursive=True, include_metadata=True):
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
        raise ValueError(f"The path '{folder_path}' is not a valid directory")
    
    # Determine the glob pattern based on recursion preference
    pattern = "**/*.pdf" if recursive else "*.pdf"
    
    # Scan for PDF files
    for pdf_path in folder_path.glob(pattern):
        if pdf_path.is_file():
            file_info = {
                "file_path": str(pdf_path),
                "file_name": pdf_path.name,
                "directory": str(pdf_path.parent),
                "relative_path": str(pdf_path.relative_to(folder_path))
            }
            
            # Add metadata if requested
            if include_metadata:
                stat = pdf_path.stat()
                file_info.update({
                    "size_bytes": stat.st_size,
                    "created_time": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_time": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "accessed_time": datetime.datetime.fromtimestamp(stat.st_atime).isoformat()
                })
            
            results.append(file_info)
    
    return results

def write_jsonlines(data, output_file=None):
    """
    Write data to a JSONLines file or stdout.
    
    Args:
        data: List of dictionaries to write
        output_file: Path to the output file, or None to write to stdout
    """
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
    else:
        # Write to stdout
        for item in data:
            print(json.dumps(item))

def main():
    parser = argparse.ArgumentParser(description="Scan PDFs in folder and write them as JSON Lines")
    parser.add_argument("folder", help="Folder to scan for PDF files")
    parser.add_argument("-o", "--output", help="Output JSONLines file (defaults to stdout if not specified)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Scan subfolders recursively")
    parser.add_argument("--no-metadata", action="store_true", help="Don't include file metadata")
    
    args = parser.parse_args()
    
    
    try:
        # Only print status messages to stderr if they won't interfere with stdout output
        if args.output:
            print(f"Scanning {args.folder} for PDF files...", file=sys.stderr)
        
        results = scan_for_pdfs(
            args.folder, 
            recursive=args.recursive, 
            include_metadata=not args.no_metadata
        )
        
        write_jsonlines(results, args.output)
        
        if args.output:
            print(f"Found {len(results)} PDF files", file=sys.stderr)
            print(f"Results written to {args.output}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    main()