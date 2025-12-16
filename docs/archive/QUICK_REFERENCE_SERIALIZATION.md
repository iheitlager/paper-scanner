# Quick Reference: field_serializer Pattern

## Problem Solved
Self-referencing models (Paper → Citation → Paper) no longer create deep nesting or circular references in JSON output.

## Solution at a Glance

### On Your Model
```python
from pydantic import BaseModel, field_serializer

class Citation(BaseModel):
    resolved_paper: Optional['Paper'] = None  # Forward reference
    
    @field_serializer('resolved_paper', when_used='json')
    def serialize_resolved_paper(self, value: Optional['Paper']) -> Optional[str]:
        return value.id if value else None
```

### In Your Converter
```python
# Before: 30+ lines of isinstance checks
# After: Just use model_dump()
def paper_to_dict(paper: Paper) -> Dict[str, Any]:
    return paper.model_dump(mode='json')
```

## When It Applies

✓ `Paper.duplicate_of` → `Optional['Paper']`  
✓ `Citation.resolved_paper` → `Optional['Paper']`  
✓ `DeduplicationResult.duplicate_of` → `Optional['Paper']`  

## What Happens

| Scenario | Result |
|----------|--------|
| `model_dump_json()` | `"duplicate_of": "id-string"` ✓ |
| `model_dump(mode='json')` | `"duplicate_of": "id-string"` ✓ |
| `model_dump(mode='python')` | `"duplicate_of": <Paper object>` |
| `paper_to_dict()` | `"duplicate_of": "id-string"` ✓ |

## Key Points

1. **Location matters**: Put `@field_serializer` on the model that has the self-reference
2. **Type safety**: Use string quotes for forward references: `'Paper'` not `Paper`
3. **Selective**: `when_used='json'` means it only applies to JSON/dict mode
4. **Null-safe**: Always check `if value` before accessing `.id`

## If You Need Full Objects After Load

```python
# Option A: Keep references as IDs and restore on demand
paper_dict = json.loads(json_str)
paper = Paper.model_validate(paper_dict)
if isinstance(paper.duplicate_of, str):
    paper.duplicate_of = database.get_paper(paper.duplicate_of)

# Option B: Manual deserialization helper
def restore_references(paper: Paper) -> Paper:
    if isinstance(paper.duplicate_of, str):
        paper.duplicate_of = database.get_paper(paper.duplicate_of)
    return paper
```

## Files Changed

- `src/paper_scanner/core/models.py` - Added 3 field_serializers
- `src/paper_scanner/io/json.py` - Simplified paper_to_dict()

## No Breaking Changes

Existing code works as-is. JSON output is actually **smaller** (IDs instead of nested objects).

---
**Full docs:** See `SELF_REFERENCE_SERIALIZATION.md`
