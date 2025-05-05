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
from advanced_section_parser import AcademicPaperParser

def scan_lines(f_in, f_out):
    results = []
    parser = AcademicPaperParser()

    for line in f_in:
        item = json.loads(line.strip())
        result = parser.process_paper_analysis(item['analysis'])
        result['file_path'] = item['file_path']
        f_out.write(json.dumps(result) + '\n')
        results += [item]

    print(f"Analysis complete! {len(results)} results saved", file=sys.stderr)
        
    return results        

def main():
    parser = argparse.ArgumentParser(description="Parse Claude.ai output and store results in JSON")
    parser.add_argument("-i", "--input", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="Input JSONLines file with file pathnames (default: stdin)")
    parser.add_argument("-o", "--output", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="Output JSONLines file (default: stdout)")
    
    args = parser.parse_args()

    # if we are interactive, do error message
    if args.input is sys.stdin and sys.stdin.isatty():
        parser.print_help()
        return 0

    scan_lines(args.input, args.output)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

if __name__ == "__main__":
    sys.exit(main())