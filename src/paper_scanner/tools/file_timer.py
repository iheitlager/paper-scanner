#!/usr/bin/env -S python

"""
File Time

This allows only one line to be submitted to allow for API usage
"""

import argparse
import sys
import time


def scan_lines(f_in, f_out, t):
    for line in f_in:
        f_out.write(line)
        time.sleep(t)


def main():
    parser = argparse.ArgumentParser(description="Parse Claude.ai output and store results in JSON")
    parser.add_argument(
        "-i",
        "--input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSONLines file with file pathnames (default: stdin)",
    )
    parser.add_argument(
        "-t",
        "--time",
        nargs="?",
        type=int,
        default=0,
        help="Amount of seconds to wait for each line",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSONLines file (default: stdout)",
    )

    args = parser.parse_args()

    # if we are interactive, do error message
    if args.input is sys.stdin and sys.stdin.isatty():
        parser.print_help()
        return 0

    scan_lines(args.input, args.output, args.time)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()


if __name__ == "__main__":
    sys.exit(main())
