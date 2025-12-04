#!/usr/bin/env -S python

"""
Combiner

Takes JSONLines and adds a field based on another field. Each line in the output file is a JSON object containing the combined fields.
If no output file is specified, writes to stdout.
"""

import argparse
import json
import sys
from collections import defaultdict
from enum import Enum


class SetOperation(Enum):
    MERGE = "MERGE"
    INTERSECT = "INTERSECT"
    EXCEPT = "EXCEPT"


def combine_lines(f_in, f_out, data_dict, set_operation=SetOperation.MERGE):
    results = []

    for line in f_in:
        include = False
        try:
            item = json.loads(line.strip())
        except Exception as e:
            print(f"Error parsing in line {len(results) + 1}: {e}", file=sys.stderr)
            return None

        # see if we can merge key
        for mkey, t in data_dict.items():
            if mkey in item:
                for rkey, values in t.items():
                    if item[mkey] in values:
                        include = True
                        item[rkey] = values[item[mkey]]

        # add the line to results, take intersect option into account
        if set_operation == SetOperation.MERGE or include != (set_operation == SetOperation.EXCEPT):
            f_out.write(json.dumps(item) + "\n")
            f_out.flush()
            results += [item]

    return results


def prep_dictionary(file_path):
    """
    Prepare a dictionary from the data for JSONLines output.

    Args:
        data: List of dictionaries to prepare

    Returns:
        List of dictionaries ready for JSONLines output
    """
    results = defaultdict(lambda: defaultdict(list))

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())

                # Extract required fields
                key = data.get("key")
                add = data.get("add")
                match = data.get("match")
                result_value = data.get("result")

                # Validate required fields
                if not all([key, add, match, result_value]):
                    print(
                        f"Warning: Line {len(results) + 1} missing required fields: {line}",
                        file=sys.stderr,
                    )
                    continue

                # Initialize the structure if not exists
                if key not in results:
                    results[key] = {}
                if add not in results[key]:
                    results[key][add] = {}

                results[key][add][match] = result_value

    except json.JSONDecodeError as e:
        print(f"Error parsing line {len(results) + 1}: {e}", file=sys.stderr)
        return None

    # Convert defaultdict to regular dict for cleaner output
    return results


def write_jsonlines(data, output_file=None):
    """
    Write data to a JSONLines file or stdout.

    Args:
        data: List of dictionaries to write
        output_file: Path to the output file, or None to write to stdout
    """
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
    else:
        # Write to stdout
        for item in data:
            print(json.dumps(item))


def main():
    parser = argparse.ArgumentParser(description="Scan lines and merge fields, write the list as JSONLines")
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
    parser.add_argument("-d", "--datafile", help="Use this JSONLines file to combine")
    parser.add_argument("-v", "--verbose", default=False, action="store_true", help="Be verbose")

    # Create mutually exclusive group for set operations
    set_group = parser.add_mutually_exclusive_group()
    set_group.add_argument(
        "-s",
        "--intersect",
        action="store_const",
        const=SetOperation.INTERSECT,
        dest="set_type",
        help="Use INTERSECT operation to find common elements",
    )
    set_group.add_argument(
        "-e",
        "--except",
        action="store_const",
        const=SetOperation.EXCEPT,
        dest="set_type",
        help="Use EXCEPT operation to find lines not matched",
    )
    # Set default value for set_type
    parser.set_defaults(set_type=SetOperation.MERGE)

    args = parser.parse_args()

    if not args.datafile:
        print("Error: --datafile argument is required", file=sys.stderr)
        parser.print_help()
        return 1

    combine_dict = prep_dictionary(args.datafile)

    # if we are interactive, do error message
    if args.input is sys.stdin and sys.stdin.isatty():
        parser.print_help()
        return 1

    results = combine_lines(args.input, args.output, combine_dict, args.set_type)

    if args.verbose:
        print(f"Merge complete! {len(results)} results returned", file=sys.stderr)

    # close all filehandles
    if args.input is not sys.stdin:
        args.input.close()
    if args.output is not sys.stdout:
        args.output.close()

    return 0 if results else 1


if __name__ == "__main__":
    main()
