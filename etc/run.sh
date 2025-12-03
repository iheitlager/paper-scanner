#!/usr/bin/env bash

set -e

# Get output filename from first argument, default to full.jsonl
output_file="${1:-full.jsonl}"
checkpoint_file="${output_file%.jsonl}-checkpoint.jsonl"

# Create output file if it doesn't exist
if [ ! -f "$output_file" ]; then
    touch "$output_file"
fi

echo "Processing output file: $output_file"
echo "Checkpoint file: $checkpoint_file"

# Pipeline: file-scanner -> paper-details -> file-processor -> tee checkpoint -> file-processor-references
file-scanner /Users/iheitlager/wc/papers -f "$output_file" \
  | paper-processor --config src/definitions/file-details.yml -v \
  | tee "$checkpoint_file" \
  | paper-processor --config src/definitions/file-summary.yml -v >> "$output_file"

echo "Pipeline complete. Analysis checkpoint saved to: $checkpoint_file"