# Three Levels of PapersQuery API

This document shows the three ways to use the fluent query API, from explicit to implicit.

## Level 1: Explicit (Full Control)

Use when you want maximum clarity and control. Call `query()` and `execute()` explicitly.

```python
from paper_scanner.core.database import PapersDatabase

db = PapersDatabase()
# ... load papers ...

# Explicit: query() → chain filters → execute()
papers = db.query().filter_by_topic("AI").filter_by_year(2020, 2023).execute()

# Get count
count = db.query().filter_by_topic("AI").count()

# Get first
paper = db.query().filter_by_topic("AI").order_by_year(descending=True).first()
```

**When to use:**
- Complex queries with many filters
- When you want to be explicit about execution
- For readability in production code
- Chainable operations that need clear intent

---

## Level 2: Shorthand Methods (Convenience)

Use shorthand methods like `by_topic()`, `by_author()` instead of `query().filter_by_topic()`.

```python
# Shorthand: Direct method on database
papers = db.by_topic("AI")

# Chain with full query API
papers = db.by_topic("AI").filter_by_year(2020, 2023).order_by_year(descending=True)

# Available shortcuts
papers = db.by_topic("AI")              # Alias for query().filter_by_topic()
papers = db.by_author("Smith")          # Alias for query().filter_by_author()
papers = db.by_year(2020, 2023)         # Alias for query().filter_by_year()
papers = db.grep("neural networks")     # Alias for query().grep()
papers = db.filter(lambda p: ...)       # Alias for query().filter()
```

**When to use:**
- Quick filtering without verbose `query()` call
- Interactive exploration
- Simple, common queries
- When you want brevity without magic

---

## Level 3: Implicit (Python Magic Methods)

Use Python's magic methods (`__iter__`, `__len__`, `__getitem__`, `__bool__`) for implicit execution.
No need to call `.execute()` or even `query()`.

### 1. For Loops (via `__iter__`)

```python
# No .execute() needed
for paper in db.by_topic("AI"):
    print(paper.title)

# With chaining
for paper in db.by_topic("AI").order_by_year(descending=True):
    print(f"{paper.title} ({paper.year})")
```

### 2. List Comprehensions (via `__iter__`)

```python
# Get titles of AI papers
titles = [p.title for p in db.by_topic("AI")]

# Filter with comprehension
recent_ai = [p for p in db.by_topic("AI") if p.year > 2020]

# Nested comprehension
author_titles = {p.authors[0].full_name: p.title for p in db.by_topic("AI")}
```

### 3. Unpacking (via `__iter__`)

```python
# Unpack first two
first, second, *rest = db.by_topic("AI")

# Unpack with slicing
p1, p2 = db.by_topic("AI")[0:2]
```

### 4. Indexing & Slicing (via `__getitem__`)

```python
# Get first paper
first = db.by_topic("AI")[0]

# Get last paper
last = db.by_topic("AI")[-1]

# Slice results
top_3 = db.by_topic("AI").order_by_year(descending=True)[0:3]

# Single item
paper = db.by_topic("AI").order_by_year(descending=True)[0]
```

### 5. Length (via `__len__`)

```python
# Count papers
count = len(db.by_topic("AI"))

# Check if non-empty
if len(db.by_topic("Quantum")) > 0:
    print("Has Quantum papers")
```

### 6. Boolean Context (via `__bool__`)

```python
# Check if query has results
if db.by_topic("AI"):
    print("AI papers exist")

# Check if no results
if not db.by_topic("Photosynthesis"):
    print("No Photosynthesis papers found")

# Use in conditional
papers = db.by_topic("AI") if db.by_topic("AI") else []
```

### 7. with Statement (via `__iter__`)

```python
# Assignment preserves query object
papers = db.by_topic("AI")
print(len(papers))  # Uses __len__
print(papers[0])    # Uses __getitem__
for p in papers:    # Uses __iter__
    print(p.title)
```

### 8. any() / all() (via `__iter__`)

```python
# Check if any paper matches
has_recent = any(p.year > 2021 for p in db.by_topic("AI"))

# Check if all match
all_recent = all(p.year > 2020 for p in db.by_topic("AI"))

# Count matches
recent_count = sum(1 for p in db.by_topic("AI") if p.year > 2020)
```

**When to use:**
- Interactive notebooks and REPL
- Simple one-liners
- When the intent is obvious from context
- Quick data exploration
- When brevity is valued over explicit clarity

---

## Practical Examples

### Example 1: Research Notebook

```python
# Level 3 (Implicit) - Natural for notebooks
df_data = {
    'title': [p.title for p in db.by_topic("AI")],
    'year': [p.year for p in db.by_topic("AI")],
    'authors': [len(p.authors) for p in db.by_topic("AI")]
}

if db.by_topic("AI"):  # Boolean check
    print(f"Found {len(db.by_topic('AI'))} AI papers")
    newest = db.by_topic("AI").order_by_year(descending=True)[0]
    print(f"Newest: {newest.title}")
```

### Example 2: Production Code

```python
# Level 1 (Explicit) - Clear and maintainable
ai_papers = db.query().filter_by_topic("AI").filter_by_year(2020, 2023).execute()
if not ai_papers:
    logger.warning("No AI papers found in recent years")
    return None

count = db.query().filter_by_topic("AI").count()
logger.info(f"Processing {count} AI papers")
```

### Example 3: Quick Script

```python
# Level 2 (Shorthand) - Balance of brevity and clarity
for paper in db.by_topic("AI").order_by_year(descending=True):
    print(f"{paper.title} - {paper.year}")

recent_ai = len(db.by_year(2022, 2023).filter_by_topic("AI"))
print(f"Recent AI papers: {recent_ai}")
```

---

## Magic Method Reference

| Method | Usage | Example |
|--------|-------|---------|
| `__iter__` | For loops, comprehensions, unpacking | `for p in db.by_topic("AI"):` |
| `__len__` | `len()` function | `len(db.by_topic("AI"))` |
| `__getitem__` | Indexing `[n]` and slicing `[n:m]` | `db.by_topic("AI")[0:3]` |
| `__bool__` | Boolean context `if`, `and`, `or` | `if db.by_topic("AI"):` |

All magic methods call `execute()` internally and return the results.

---

## Summary

| Level | Style | Pros | Cons |
|-------|-------|------|------|
| **1. Explicit** | `db.query().filter().execute()` | Very clear intent, full control | Verbose |
| **2. Shorthand** | `db.by_topic().filter()` | Convenient, readable | Still need to chain |
| **3. Implicit** | `for p in db.by_topic():` | Pythonic, concise | Less explicit |

**Recommendation:** Use Level 2 (Shorthand) as the sweet spot for most code. Use Level 1 (Explicit) for complex queries or production code that needs clarity. Use Level 3 (Implicit) in interactive notebooks and quick scripts.
