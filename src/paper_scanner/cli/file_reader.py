#!/usr/bin/env -S python

"""
File reader

This scans the parsed output and transforms this into CSV.
"""

import argparse
import json
import sys

COLUMNS = ["AUTHORS", "c", "a", "m", "o", "description"]


def author(item):
    if "AUTHORS" in item:
        return item["AUTHORS"].split(", ")[0].split(" ")[-1] + item["YEAR"]
    else:
        "unknown"


def scan_lines(f_in, f_out, verbose=False):
    """
    Scan a file and extract all relevant info.

    Args:
        f_in: input stream
        f_out: output stream
        verbose: extra messages

    Returns:
        writes csv
    """
    results = []

    f_out.write(", ".join(COLUMNS) + "\n")

    for line in f_in:
        item = json.loads(line.strip())
        for camo in item["CAMO"]:
            out_line = [
                author(item),
                camo["c"],
                camo["a"],
                camo["m"],
                camo["o"],
                camo["description"],
            ]
            f_out.write(", ".join(out_line) + "\n")
            f_out.flush()
            results += [out_line]

    return results


def main():
    parser = argparse.ArgumentParser(description="Reads the list of JSONLines and outputs csv")
    parser.add_argument(
        "-i",
        "--input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSONLines file with file pathnames (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file (default: stdout)",
    )
    parser.add_argument("-v", "--verbose", default=False, action="store_true", help="Be verbose")

    args = parser.parse_args()

    results = scan_lines(args.input, args.output, verbose=args.verbose)

    if args.output and args.verbose:
        print(f"Found {len(results)} lines", file=sys.stderr)
    if args.output and args.verbose:
        print(f"Results written to {args.output}", file=sys.stderr)

    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

    return 0 if results else 1


if __name__ == "__main__":
    main()
