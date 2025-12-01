#!/usr/bin/env -S python

"""
File Parser

Takes a JSONLines list with content from Claude
Each line is a scanned document and parsed for real content
Results are stored back in JSONLines
"""

import json
import sys
import argparse
from paper_scanner.core.advanced_section_parser import AcademicPaperParser


def scan_lines(f_in, f_out):
    results = []
    parser = AcademicPaperParser()

    for line in f_in:
        try:
            item = json.loads(line.strip())
        except Exception as e:
            print(f"Error parsing in line {len(results)+1}: {e}", file=sys.stderr)
            return None

        if 'analysis' in item:
            result = parser.process_paper_analysis(item['analysis'])
            item.update(result)
        f_out.write(json.dumps(item) + '\n')
        f_out.flush()
        results += [item]

    return results        


def main():
    parser = argparse.ArgumentParser(description="Parse Claude.ai output and store results in JSON")
    parser.add_argument("-i", "--input", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="Input JSONLines file with file pathnames (default: stdin)")
    parser.add_argument("-o", "--output", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="Output JSONLines file (default: stdout)")
    parser.add_argument("-v", "--verbose", default=False, action="store_true", help="Be verbose")
   
    args = parser.parse_args()

    # if we are interactive, do error message
    if args.input is sys.stdin and sys.stdin.isatty():
        parser.print_help()
        return 1

    results = scan_lines(args.input, args.output)

    if args.verbose:
        print(f"Parsing complete! {len(results)} results saved", file=sys.stderr)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

    return 0 if results else 1

if __name__ == "__main__":
    sys.exit(main())