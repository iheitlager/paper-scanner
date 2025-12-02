#!/usr/bin/env -S python

"""
File Parser

Takes a JSONLines list with content from Claude
Each line is a scanned document and parsed for real content
Results are stored back in JSONLines
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from paper_scanner.core.advanced_section_parser import AcademicPaperParser


def scan_lines(f_in, f_out, verbose=False):
    """
    Parse Claude analysis output and extract structured data.

    Args:
        f_in: Input file object
        f_out: Output file object
        verbose: Enable verbose logging

    Returns:
        List of parsed items or None on error
    """
    results = []
    parser = AcademicPaperParser()
    line_num = 0

    for line_num, line in enumerate(f_in, 1):
        try:
            item = json.loads(line.strip())
        except json.JSONDecodeError as e:
            print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
            if verbose:
                print(f"  Raw line: {line[:100]}", file=sys.stderr)
            continue

        try:
            if "analysis" in item:
                result = parser.process_paper_analysis(item["analysis"])
                item.update(result)
            f_out.write(json.dumps(item) + "\n")
            f_out.flush()
            results.append(item)
        except Exception as e:
            print(f"Error processing line {line_num}: {e}", file=sys.stderr)
            if verbose:
                print(f"  Item keys: {list(item.keys())}", file=sys.stderr)
            continue

    if verbose:
        print(f"Parsed {len(results)}/{line_num} lines successfully", file=sys.stderr)

    return results


def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Parse Claude.ai output and extract structured data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: cat analysis.jsonl | file-parser -v > parsed.jsonl",
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSONLines file with Claude analysis (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file with parsed results (default: stdout)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Show help if reading from stdin in interactive mode
    if args.input is sys.stdin and sys.stdin.isatty():
        parser.print_help()
        return 1

    try:
        results = scan_lines(args.input, args.output, verbose=args.verbose)

        if results is None:
            return 1

        if args.verbose:
            print(f"✓ Parsing complete! {len(results)} results saved", file=sys.stderr)

        return 0 if results else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1
    finally:
        # Close file handles
        if args.input is not sys.stdin:
            args.input.close()
        if args.output is not sys.stdout:
            args.output.close()


if __name__ == "__main__":
    sys.exit(main())
