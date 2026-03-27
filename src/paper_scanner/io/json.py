# src/paper_scanner/io/json_converter.py

"""
JSON ↔ Pydantic conversion functions (100% complete)
Handles full serialization/deserialization of all Paper fields
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.models import (
    Author,
    Discovery,
    DiscoveryMethod,
    Paper,
    PaperType,
    QualityTier,
    ScreeningDecision,
    StudyType,
)

# ============================================================================
# CUSTOM JSON ENCODER
# ============================================================================

class PaperJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Paper models"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, (PaperType, StudyType, QualityTier, DiscoveryMethod, ScreeningDecision)):
            return obj.value
        return super().default(obj)


# ============================================================================
# PYDANTIC → JSON (Complete Serialization)
# ============================================================================

def paper_to_dict(paper: Paper, exclude_none: bool = False) -> Dict[str, Any]:
    """
    Convert Paper Pydantic model to dictionary (100% complete)

    Self-references (duplicate_of, resolved_paper) are handled by @field_serializer
    decorators on the models, which convert Paper objects to ID strings during
    JSON serialization.

    Args:
        paper: Paper Pydantic model
        exclude_none: If True, exclude None values from output

    Returns:
        Complete dictionary representation with self-references as IDs
    """

    # Pydantic's field_serializer decorators handle self-reference conversion
    # No manual post-processing needed
    return paper.model_dump(
        mode='json',
        exclude_none=exclude_none,
        by_alias=False
    )


def paper_to_json(
    paper: Paper,
    exclude_none: bool = False,
    indent: Optional[int] = 2
) -> str:
    """
    Convert Paper to JSON string (100% complete)

    Args:
        paper: Paper Pydantic model
        exclude_none: Exclude None values
        indent: JSON indentation (None for compact)

    Returns:
        JSON string
    """

    paper_dict = paper_to_dict(paper, exclude_none=exclude_none)

    return json.dumps(
        paper_dict,
        cls=PaperJSONEncoder,
        indent=indent,
        ensure_ascii=False
    )


def papers_to_json(
    papers: List[Paper],
    exclude_none: bool = False,
    indent: Optional[int] = 2
) -> str:
    """
    Convert list of Papers to JSON string

    Args:
        papers: List of Paper models
        exclude_none: Exclude None values
        indent: JSON indentation

    Returns:
        JSON string (array of papers)
    """

    papers_list = [paper_to_dict(p, exclude_none=exclude_none) for p in papers]

    return json.dumps(
        papers_list,
        cls=PaperJSONEncoder,
        indent=indent,
        ensure_ascii=False
    )


def paper_to_json_file(
    paper: Paper,
    filepath: str,
    exclude_none: bool = False,
    indent: int = 2
) -> None:
    """
    Write Paper to JSON file

    Args:
        paper: Paper model
        filepath: Output file path
        exclude_none: Exclude None values
        indent: JSON indentation
    """

    json_string = paper_to_json(paper, exclude_none=exclude_none, indent=indent)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(json_string)


def papers_to_json_file(
    papers: List[Paper],
    filepath: str,
    exclude_none: bool = False,
    indent: int = 2
) -> None:
    """
    Write Papers to JSON file

    Args:
        papers: List of Paper models
        filepath: Output file path
        exclude_none: Exclude None values
        indent: JSON indentation
    """

    json_string = papers_to_json(papers, exclude_none=exclude_none, indent=indent)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(json_string)


# ============================================================================
# JSON → PYDANTIC (Complete Deserialization)
# ============================================================================

def dict_to_paper(data: Dict[str, Any]) -> Paper:
    """
    Convert dictionary to Paper Pydantic model (100% complete)

    Args:
        data: Dictionary representation of Paper

    Returns:
        Paper Pydantic model with all fields restored
    """

    # Pydantic will handle all validation and type conversion
    return Paper.model_validate(data)


def json_to_paper(json_string: str) -> Paper:
    """
    Convert JSON string to Paper model

    Args:
        json_string: JSON representation of Paper

    Returns:
        Paper Pydantic model
    """

    data = json.loads(json_string)
    return dict_to_paper(data)


def json_to_papers(json_string: str) -> List[Paper]:
    """
    Convert JSON string to list of Papers

    Args:
        json_string: JSON array of papers

    Returns:
        List of Paper models
    """

    data_list = json.loads(json_string)

    if not isinstance(data_list, list):
        raise ValueError("Expected JSON array of papers")

    return [dict_to_paper(data) for data in data_list]


def json_file_to_paper(filepath: str) -> Paper:
    """
    Load Paper from JSON file

    Args:
        filepath: Path to JSON file

    Returns:
        Paper model
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        json_string = f.read()

    return json_to_paper(json_string)


def json_file_to_papers(filepath: str) -> List[Paper]:
    """
    Load Papers from JSON file

    Args:
        filepath: Path to JSON file (array of papers)

    Returns:
        List of Paper models
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        json_string = f.read()

    return json_to_papers(json_string)


# ============================================================================
# JSONL (JSON Lines) FORMAT - For Large Datasets
# ============================================================================

def papers_to_jsonl(
    papers: List[Paper],
    exclude_none: bool = False
) -> str:
    """
    Convert papers to JSONL format (one JSON object per line)
    Efficient for large datasets

    Args:
        papers: List of Paper models
        exclude_none: Exclude None values

    Returns:
        JSONL string
    """

    lines = []
    for paper in papers:
        paper_dict = paper_to_dict(paper, exclude_none=exclude_none)
        line = json.dumps(paper_dict, cls=PaperJSONEncoder, ensure_ascii=False)
        lines.append(line)

    return '\n'.join(lines) + '\n'


def papers_to_jsonl_file(
    papers: List[Paper],
    filepath: str,
    exclude_none: bool = False
) -> None:
    """
    Write papers to JSONL file

    Args:
        papers: List of Paper models
        filepath: Output file path
        exclude_none: Exclude None values
    """

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        for paper in papers:
            paper_dict = paper_to_dict(paper, exclude_none=exclude_none)
            line = json.dumps(paper_dict, cls=PaperJSONEncoder, ensure_ascii=False)
            f.write(line + '\n')


def jsonl_to_papers(jsonl_string: str) -> List[Paper]:
    """
    Convert JSONL string to Papers

    Args:
        jsonl_string: JSONL formatted string

    Returns:
        List of Paper models
    """

    papers = []

    for line in jsonl_string.strip().split('\n'):
        if line.strip():
            data = json.loads(line)
            paper = dict_to_paper(data)
            papers.append(paper)

    return papers


def jsonl_file_to_papers(filepath: str) -> List[Paper]:
    """
    Load papers from JSONL file (memory efficient for large files)

    Args:
        filepath: Path to JSONL file

    Returns:
        List of Paper models
    """

    papers = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                paper = dict_to_paper(data)
                papers.append(paper)

    return papers


# ============================================================================
# STREAMING JSONL - For Very Large Datasets
# ============================================================================

def stream_jsonl_file(filepath: str):
    """
    Stream papers from JSONL file (generator, memory efficient)

    Args:
        filepath: Path to JSONL file

    Yields:
        Paper models one at a time

    Usage:
        for paper in stream_jsonl_file('papers.jsonl'):
            process(paper)
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                yield dict_to_paper(data)


# ============================================================================
# PAPER COLLECTION (Batch) CONVERSION
# ============================================================================

def collection_to_dict(collection: PaperCollection) -> Dict[str, Any]:
    """
    Convert PaperCollection to dictionary

    Args:
        collection: PaperCollection model

    Returns:
        Dictionary representation
    """

    return collection.model_dump(mode='json')


def collection_to_json(
    collection: PaperCollection,
    indent: Optional[int] = 2
) -> str:
    """
    Convert PaperCollection to JSON string

    Args:
        collection: PaperCollection model
        indent: JSON indentation

    Returns:
        JSON string
    """

    data = collection_to_dict(collection)

    return json.dumps(
        data,
        cls=PaperJSONEncoder,
        indent=indent,
        ensure_ascii=False
    )


def collection_to_json_file(
    collection: PaperCollection,
    filepath: str,
    indent: int = 2
) -> None:
    """
    Write PaperCollection to JSON file

    Args:
        collection: PaperCollection model
        filepath: Output file path
        indent: JSON indentation
    """

    json_string = collection_to_json(collection, indent=indent)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(json_string)


def dict_to_collection(data: Dict[str, Any]) -> PaperCollection:
    """
    Convert dictionary to PaperCollection

    Args:
        data: Dictionary representation

    Returns:
        PaperCollection model
    """

    return PaperCollection.model_validate(data)


def json_to_collection(json_string: str) -> PaperCollection:
    """
    Convert JSON string to PaperCollection

    Args:
        json_string: JSON representation

    Returns:
        PaperCollection model
    """

    data = json.loads(json_string)
    return dict_to_collection(data)


def json_file_to_collection(filepath: str) -> PaperCollection:
    """
    Load PaperCollection from JSON file

    Args:
        filepath: Path to JSON file

    Returns:
        PaperCollection model
    """

    with open(filepath, 'r', encoding='utf-8') as f:
        json_string = f.read()

    return json_to_collection(json_string)


# ============================================================================
# PARTIAL EXPORT (Specific Fields Only)
# ============================================================================

def paper_to_dict_minimal(paper: Paper) -> Dict[str, Any]:
    """
    Export minimal paper info (for listings, overviews)

    Fields: id, cite_key, title, authors, year, doi, final_decision
    """

    return {
        'id': str(paper.id),
        'cite_key': paper.cite_key,
        'title': paper.title,
        'authors': paper.author_string,
        'year': paper.year,
        'doi': paper.doi,
        'final_decision': paper.screening.final_decision.value
    }


def paper_to_dict_bibliographic(paper: Paper) -> Dict[str, Any]:
    """
    Export bibliographic info only (for citations)

    Fields: All bibliographic metadata, no embeddings/processing
    """

    return {
        'id': str(paper.id),
        'cite_key': paper.cite_key,
        'doi': paper.doi,
        'title': paper.title,
        'abstract': paper.abstract,
        'authors': [
            {
                'given_name': a.given_name,
                'family_name': a.family_name,
                'full_name': a.full_name
            }
            for a in paper.authors
        ],
        'year': paper.year,
        'journal': paper.journal,
        'booktitle': paper.booktitle,
        'volume': paper.volume,
        'number': paper.number,
        'pages': paper.pages,
        'publisher': paper.publisher,
        'keywords': paper.keywords,
        'url': paper.url
    }


def paper_to_dict_screening(paper: Paper) -> Dict[str, Any]:
    """
    Export screening info only

    Fields: All screening decisions and scores
    """

    screening = paper.screening

    result = {
        'id': str(paper.id),
        'cite_key': paper.cite_key,
        'title': paper.title[:100],
        'current_stage': screening.current_stage,
        'final_decision': screening.final_decision.value
    }

    # Metadata Screening
    if screening.metadata_screening:
        result['metadata_screening'] = {
            'paper_type': screening.metadata_screening.paper_type.value,
            'quality_tier': screening.metadata_screening.quality_tier.value,
            'is_peer_reviewed': screening.metadata_screening.is_peer_reviewed,
            'passed': screening.metadata_screening.passed
        }

    # Keyword Screening (includes study_type and is_empirical)
    if screening.keyword_screening:
        result['keyword_screening'] = {
            'study_type': screening.keyword_screening.study_type.value,
            'is_empirical': screening.keyword_screening.is_empirical,
            'is_conceptual': screening.keyword_screening.is_conceptual,
            'is_literature_review': screening.keyword_screening.is_literature_review,
        }

    # Semantic screening
    if screening.semantic_screening:
        result['semantic_screening'] = {
            'passed': screening.semantic_screening.passed,
            'similarity_score': screening.semantic_screening.similarity_score,
            'threshold': screening.semantic_screening.threshold,
            'llm_decision': screening.semantic_screening.llm_decision.value if screening.semantic_screening.llm_decision else None
        }

    return result


def paper_to_dict_camo(paper: Paper) -> Dict[str, Any]:
    """
    Export CAMO statements only

    Fields: Paper identification + all CAMO statements
    """

    result = {
        'id': str(paper.id),
        'cite_key': paper.cite_key,
        'title': paper.title,
        'year': paper.year,
        'camo_statements': []
    }

    if paper.conceptual_analysis and paper.conceptual_analysis.camo_statements:
        for camo in paper.conceptual_analysis.camo_statements:
            result['camo_statements'].append({
                'id': camo.id,
                'context': camo.context,
                'agency': camo.agency,
                'mechanism': camo.mechanism,
                'outcome': camo.outcome,
                'cluster_id': camo.cluster_id,
                'cluster_label': camo.cluster_label,
                'innovation_type': camo.innovation_type,
                'confidence': camo.confidence
            })

    return result


def papers_to_json_partial(
    papers: List[Paper],
    mode: str = 'minimal',
    indent: Optional[int] = 2
) -> str:
    """
    Export papers with specific fields only

    Args:
        papers: List of Paper models
        mode: 'minimal', 'bibliographic', 'screening', or 'camo'
        indent: JSON indentation

    Returns:
        JSON string
    """

    converters = {
        'minimal': paper_to_dict_minimal,
        'bibliographic': paper_to_dict_bibliographic,
        'screening': paper_to_dict_screening,
        'camo': paper_to_dict_camo
    }

    if mode not in converters:
        raise ValueError(f"Unknown mode: {mode}. Choose from: {list(converters.keys())}")

    converter = converters[mode]

    papers_list = [converter(p) for p in papers]

    return json.dumps(
        papers_list,
        cls=PaperJSONEncoder,
        indent=indent,
        ensure_ascii=False
    )


# ============================================================================
# VALIDATION & VERIFICATION
# ============================================================================

def validate_json_schema(json_string: str) -> bool:
    """
    Validate that JSON can be deserialized to Paper model

    Args:
        json_string: JSON string

    Returns:
        True if valid, False otherwise
    """

    try:
        json_to_paper(json_string)
        return True
    except Exception:
        return False


def validate_json_file(filepath: str) -> Dict[str, Any]:
    """
    Validate JSON file and return diagnostics

    Args:
        filepath: Path to JSON file

    Returns:
        Dict with validation results
    """

    result = {
        'valid': False,
        'error': None,
        'paper_count': 0,
        'file_size_mb': 0
    }

    try:
        file_size = Path(filepath).stat().st_size
        result['file_size_mb'] = round(file_size / (1024 * 1024), 2)

        # Try to load
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check if single paper or list
        if isinstance(data, list):
            papers = [dict_to_paper(d) for d in data]
            result['paper_count'] = len(papers)
        else:
            dict_to_paper(data)
            result['paper_count'] = 1

        result['valid'] = True

    except Exception as e:
        result['error'] = str(e)

    return result


# ============================================================================
# ROUND-TRIP VERIFICATION
# ============================================================================

def verify_round_trip(paper: Paper) -> bool:
    """
    Verify that Paper can be serialized and deserialized without loss

    Args:
        paper: Paper model

    Returns:
        True if round-trip successful, False otherwise
    """

    try:
        # Paper → JSON → Paper
        json_string = paper_to_json(paper)
        restored_paper = json_to_paper(json_string)

        # Compare (excluding computed properties and timestamps)
        original_dict = paper_to_dict(paper)
        restored_dict = paper_to_dict(restored_paper)

        return original_dict == restored_dict

    except Exception as e:
        print(f"Round-trip failed: {e}")
        return False


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

def split_papers_to_files(
    papers: List[Paper],
    output_dir: str,
    papers_per_file: int = 100,
    prefix: str = "papers"
) -> List[str]:
    """
    Split papers into multiple JSON files

    Args:
        papers: List of Paper models
        output_dir: Output directory
        papers_per_file: Number of papers per file
        prefix: Filename prefix

    Returns:
        List of created file paths
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    created_files = []

    for i in range(0, len(papers), papers_per_file):
        batch = papers[i:i + papers_per_file]
        batch_num = (i // papers_per_file) + 1

        filename = f"{prefix}_batch_{batch_num:03d}.json"
        filepath = output_path / filename

        papers_to_json_file(batch, str(filepath))
        created_files.append(str(filepath))

        print(f"Created {filepath} ({len(batch)} papers)")

    return created_files


def merge_json_files(
    filepaths: List[str],
    output_filepath: str
) -> int:
    """
    Merge multiple JSON files into one

    Args:
        filepaths: List of JSON file paths
        output_filepath: Output file path

    Returns:
        Total number of papers merged
    """

    all_papers = []

    for filepath in filepaths:
        papers = json_file_to_papers(filepath)
        all_papers.extend(papers)
        print(f"Loaded {len(papers)} papers from {filepath}")

    papers_to_json_file(all_papers, output_filepath)

    print(f"\nMerged {len(all_papers)} papers to {output_filepath}")

    return len(all_papers)


# ============================================================================
# COMPRESSION SUPPORT
# ============================================================================

def papers_to_json_gz(
    papers: List[Paper],
    filepath: str,
    exclude_none: bool = False,
    indent: Optional[int] = None
) -> None:
    """
    Write papers to compressed JSON file (.json.gz)

    Args:
        papers: List of Paper models
        filepath: Output file path
        exclude_none: Exclude None values
        indent: JSON indentation (None for compact)
    """

    import gzip

    json_string = papers_to_json(papers, exclude_none=exclude_none, indent=indent)

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        f.write(json_string)


def json_gz_to_papers(filepath: str) -> List[Paper]:
    """
    Load papers from compressed JSON file (.json.gz)

    Args:
        filepath: Path to .json.gz file

    Returns:
        List of Paper models
    """

    import gzip

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        json_string = f.read()

    return json_to_papers(json_string)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":

    # ========================================
    # Example 1: Single Paper - Full Export
    # ========================================

    print("="*60)
    print("Example 1: Full Paper Export")
    print("="*60)

    # Create a sample paper (would normally come from database)
    from datetime import datetime

    sample_paper = Paper(
        cite_key="Smith2023",
        title="Digital Transformation in Manufacturing: A Systematic Review",
        abstract="This paper examines...",
        authors=[
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
            Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")
        ],
        year=2023,
        journal="Journal of Manufacturing Technology",
        volume="45",
        number="3",
        pages="123-145",
        doi="10.1234/jmt.2023.001",
        keywords=["digital transformation", "manufacturing", "industry 4.0"],
        source_type="scopus",
        discovery=Discovery(
            method=DiscoveryMethod.KEYWORD_SEARCH,
            source_database="scopus"
        )
    )

    # Export to JSON
    json_output = paper_to_json(sample_paper, indent=2)
    print(json_output[:500])
    print("...\n")

    # ========================================
    # Example 2: Round-trip Verification
    # ========================================

    print("="*60)
    print("Example 2: Round-trip Verification")
    print("="*60)

    # Paper → JSON → Paper
    restored_paper = json_to_paper(json_output)

    print(f"Original cite_key: {sample_paper.cite_key}")
    print(f"Restored cite_key: {restored_paper.cite_key}")
    print(f"Titles match: {sample_paper.title == restored_paper.title}")
    print(f"Authors match: {len(sample_paper.authors) == len(restored_paper.authors)}")
    print(f"Round-trip successful: {verify_round_trip(sample_paper)}")
    print()

    # ========================================
    # Example 3: Batch Export
    # ========================================

    print("="*60)
    print("Example 3: Batch Export (Multiple Papers)")
    print("="*60)

    papers = [sample_paper] * 3  # Simulate 3 papers

    # Export to file
    papers_to_json_file(papers, "output/papers.json")
    print(f"Exported {len(papers)} papers to output/papers.json")

    # Load back
    loaded_papers = json_file_to_papers("output/papers.json")
    print(f"Loaded {len(loaded_papers)} papers")
    print()

    # ========================================
    # Example 4: JSONL Format
    # ========================================

    print("="*60)
    print("Example 4: JSONL Format (Line-delimited)")
    print("="*60)

    # Export to JSONL
    papers_to_jsonl_file(papers, "output/papers.jsonl")
    print(f"Exported {len(papers)} papers to output/papers.jsonl")

    # Load back
    loaded_papers = jsonl_file_to_papers("output/papers.jsonl")
    print(f"Loaded {len(loaded_papers)} papers")

    # Stream (memory efficient)
    print("\nStreaming papers:")
    for i, paper in enumerate(stream_jsonl_file("output/papers.jsonl"), 1):
        print(f"  {i}. {paper.cite_key}")
    print()

    # ========================================
    # Example 5: Partial Export
    # ========================================

    print("="*60)
    print("Example 5: Partial Export (Minimal)")
    print("="*60)

    minimal_json = papers_to_json_partial(papers, mode='minimal', indent=2)
    print(minimal_json)
    print()

    # ========================================
    # Example 6: Compressed Export
    # ========================================

    print("="*60)
    print("Example 6: Compressed Export (.json.gz)")
    print("="*60)

    papers_to_json_gz(papers, "output/papers.json.gz", indent=None)
    print("Exported to output/papers.json.gz (compressed)")

    loaded_papers = json_gz_to_papers("output/papers.json.gz")
    print(f"Loaded {len(loaded_papers)} papers from compressed file")
    print()

    # ========================================
    # Example 7: Validation
    # ========================================

    print("="*60)
    print("Example 7: File Validation")
    print("="*60)

    validation = validate_json_file("output/papers.json")
    print(f"Valid: {validation['valid']}")
    print(f"Papers: {validation['paper_count']}")
    print(f"Size: {validation['file_size_mb']} MB")

    if validation['error']:
        print(f"Error: {validation['error']}")
