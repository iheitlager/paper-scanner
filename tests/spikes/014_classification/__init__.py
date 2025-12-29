"""
Spike 014: Classification - Metadata Screening Implementation

This spike develops the metadata-screening step, an evolution of categorization
with tri-state logic for including/excluding papers based on metadata criteria.

Tri-state screening:
- INCLUDE: Hard include (must have these values)
- EXCLUDE: Hard exclude (must NOT have these values, or everything except specified)
- OMITTED: No requirement (leave aside)

Special operator:
- NOT: prefix means "exclude everything except this value"
  Example: NOT: en means exclude everything that is NOT English

Test files:
- test_01_parse.yml: YAML pipeline definition testing configuration parsing
- test_02_screen_files.py: pytest-based testing of screening logic and enum conversion
"""
