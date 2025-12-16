# Self-Reference Serialization Pattern

## Problem
When models have self-references (e.g., `Paper` → `Citation` → `Paper`), `model_dump()` creates deep nesting that wastes space and causes circular reference issues.

## Solution: Use `field_serializer` Decorators

Instead of post-processing in `paper_to_dict()`, use Pydantic's `field_serializer` to control serialization at the model level.

### Implementation

Add to your `Paper` model:

```python
from pydantic import field_serializer

class Paper(BaseModel):
    # ... existing fields ...
    duplicate_of: Optional[Paper] = None
    
    @field_serializer('duplicate_of', when_used='json')
    def serialize_duplicate_of(self, value: Optional['Paper']) -> Optional[str]:
        """Convert Paper reference to ID string during JSON serialization"""
        return value.id if value else None
```

Add to your `Citation` model:

```python
class Citation(BaseModel):
    # ... existing fields ...
    resolved_paper: Optional[Paper] = None
    
    @field_serializer('resolved_paper', when_used='json')
    def serialize_resolved_paper(self, value: Optional[Paper]) -> Optional[str]:
        """Convert Paper reference to ID string during JSON serialization"""
        return value.id if value else None
```

Add to your `DeduplicationResult` model:

```python
class DeduplicationResult(BaseModel):
    # ... existing fields ...
    duplicate_of: Optional[Paper] = None
    
    @field_serializer('duplicate_of', when_used='json')
    def serialize_duplicate_of(self, value: Optional[Paper]) -> Optional[str]:
        """Convert Paper reference to ID string during JSON serialization"""
        return value.id if value else None
```

## Benefits

| Aspect | Before (Manual Post-Processing) | After (field_serializer) |
|--------|--------------------------------|-------------------------|
| **Location** | In converter function (`json.py`) | On the model itself |
| **Type Safety** | Manual isinstance checks | Type hints in signature |
| **Maintainability** | Scattered logic | Centralized on model |
| **Testability** | Must test in isolation | Tests move to model tests |
| **Performance** | Dict post-processing | Native serialization |
| **Selective** | Always applied | Use `when_used='json'` for control |

## Advanced: Conditional Serialization Modes

You can have different serialization modes:

```python
@field_serializer('duplicate_of', when_used='json')
def serialize_duplicate_of_json(self, value):
    """JSON: Return only ID"""
    return value.id if value else None

# For internal use (Python objects), the full Paper object is preserved
```

Then use:
```python
# Serialize to JSON (uses field_serializer)
json_string = paper.model_dump_json()

# Serialize for Python (preserves full objects)
dict_with_objects = paper.model_dump(mode='python')
```

## Updating the Converter

Once models are updated, simplify `paper_to_dict()`:

```python
def paper_to_dict(paper: Paper, exclude_none: bool = False) -> Dict[str, Any]:
    """
    Convert Paper Pydantic model to dictionary
    
    field_serializer decorators on Paper model handle self-references.
    """
    return paper.model_dump(
        mode='json',
        exclude_none=exclude_none,
        by_alias=False
    )
```

The manual post-processing code can be removed entirely.

## Full Example

```python
from pydantic import BaseModel, field_serializer
from typing import Optional

class Paper(BaseModel):
    id: str
    title: str
    duplicate_of: Optional['Paper'] = None
    
    @field_serializer('duplicate_of', when_used='json')
    def serialize_duplicate_of(self, value: Optional['Paper']) -> Optional[str]:
        return value.id if value else None

# Usage:
paper1 = Paper(id='1', title='Original')
paper2 = Paper(id='2', title='Duplicate', duplicate_of=paper1)

# In-memory: full object preserved
print(paper2.duplicate_of.title)  # ✓ "Original"

# JSON serialization: ID only
print(paper2.model_dump_json())
# {"id": "2", "title": "Duplicate", "duplicate_of": "1"}
```

## See Also

- [Pydantic field_serializer docs](https://docs.pydantic.dev/latest/api/functional_serializers/#pydantic.field_serializer)
- [Pydantic serialization modes](https://docs.pydantic.dev/latest/concepts/serialization/#serialization-modes)
