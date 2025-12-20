# PapersDatabase Query API - Quick Reference

## Three Ways to Query

### 1. **Explicit Builder** (Most Control)
Use when you want full control and explicit execution:

```python
results = db.query().filter_by_topic("AI").order_by_year().top(5).execute()
```

### 2. **Shorthand Methods** (Most Readable)
Use the convenience methods for common queries:

```python
results = db.by_topic("AI").order_by_year().execute()
```

### 3. **Compact Syntax** (Most Pythonic - NO `.execute()` needed!)
Use implicit execution via Python magic methods:

```python
# Indexing - get first result
first_paper = db.by_topic("AI")[0]

# Length - count results
count = len(db.by_topic("AI"))

# Iteration - loop without .execute()
for paper in db.by_topic("AI"):
    print(paper.title)

# Boolean check - if results exist
if db.by_topic("AI"):
    print("Found AI papers")

# Slicing - get range of results
top_5 = db.by_topic("AI").order_by_year(descending=True)[0:5]
```

## Shorthand Methods on PapersDatabase

| Method | Equivalent | Example |
|--------|-----------|---------|
| `db.filter(predicate)` | `db.query().filter()` | `db.filter(lambda p: p.year > 2020)` |
| `db.by_topic(topic)` | `db.query().filter_by_topic()` | `db.by_topic("AI")[0]` |
| `db.by_author(name)` | `db.query().filter_by_author()` | `db.by_author("Smith").count()` |
| `db.by_year(y1, y2)` | `db.query().filter_by_year()` | `db.by_year(2020, 2023)` |
| `db.search(text)` | `db.query().grep()` | `db.search("transformer")[0]` |

## Complete Examples

### Get first AI paper
```python
paper = db.by_topic("AI")[0]
```

### Count papers by author
```python
smith_count = len(db.by_author("Smith"))
```

### Check if papers exist
```python
if db.by_topic("Quantum"):
    print("Found Quantum papers")
```

### Filter and sort without .execute()
```python
recent_ai = db.by_topic("AI").order_by_year(descending=True)[0:3]
```

### Iterate results
```python
for paper in db.search("neural network"):
    print(f"{paper.title} ({paper.year})")
```

### Complex query in one line
```python
newest = db.by_topic("AI").exclude_duplicates().order_by_year(descending=True)[0]
```

### List comprehension
```python
titles = [p.title for p in db.by_year(2020, 2023) if "learning" in p.abstract]
```

## Magic Methods Supported

Once you have a query object, Python's built-in operations work automatically:

- **`query[0]`** → Returns first paper (calls `execute()`)
- **`query[0:5]`** → Returns slice of papers
- **`len(query)`** → Returns count (calls `count()`)
- **`for p in query`** → Iteration (calls `execute()`)
- **`if query`** → Boolean check (calls `count() > 0`)

No explicit `.execute()` needed!

## When to Use Each Approach

| Situation | Use | Example |
|-----------|-----|---------|
| Simple single filter | Shorthand | `db.by_topic("AI")[0]` |
| Multiple filters | Shorthand chain | `db.by_topic("AI").order_by_year()[0:10]` |
| Custom predicate | Explicit builder | `db.query().filter(lambda p: p.year > 2020)` |
| Multiple papers in a loop | Any (all work!) | `for p in db.by_topic("AI"):` |
| Count results | Shorthand | `len(db.by_topic("AI"))` |
| Get one paper | Shorthand indexing | `db.by_topic("AI")[0]` |

## Return Types

All methods return PapersQuery objects that support magic methods:

```python
query = db.by_topic("AI")  # Returns PapersQuery

# These all work without .execute():
list(query)              # Convert to list
len(query)              # Get count
query[0]                # Get first
query[0:5]              # Slice
bool(query)             # Check if any results
for p in query: ...     # Iterate
```

For explicit control, use terminal operations:

```python
query.execute()         # Return list of papers
query.first()          # Return first paper or None
query.count()          # Return count (int)
query.list()           # Alias for execute()
```

## Performance Note

- **Lazy evaluation**: Filters aren't applied until you access results
- **No queries until needed**: `db.by_topic("AI")` returns immediately
- **Executed on access**: First `[0]`, `len()`, or `for` triggers computation
- **Caching**: Multiple accesses re-compute (no caching by default)

For multiple uses of the same query, call `.execute()` once:

```python
# Good: compute once
results = db.by_topic("AI").execute()
count = len(results)
first = results[0]

# Less efficient: computes three times
count = len(db.by_topic("AI"))
first = db.by_topic("AI")[0]
first_alt = db.by_topic("AI").first()
```
