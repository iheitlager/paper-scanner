#!/usr/bin/env bash

set -e

# Get output filename from first argument, default to full.jsonl
output_file="${1:-full.jsonl}"

# Create output file if it doesn't exist
if [ ! -f "$output_file" ]; then
    touch "$output_file"
fi

echo "Processing output file: $output_file"

file-scanner ../papers -f "$output_file" | paper-details -v  | file-processor -o "$output_file" -v --custom_prompt src/prompts/paper-summary.md