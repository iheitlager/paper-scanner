"""
Magic Methods Demo: Implicit execute() via Python Dunder Methods

The PapersQuery class uses Python magic methods (__iter__, __len__, __getitem__, __bool__)
to enable implicit execution in common contexts. No explicit .execute() or .query() needed!
"""

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper, Author


def make_author(first: str, last: str) -> Author:
    return Author(given_name=first, family_name=last, full_name=f"{first} {last}")


# Create test database
db = PapersDatabase()
db.add(Paper(id="1", cite_key="c1", title="AI Research", authors=[make_author("John", "Smith")], year=2020, keywords=["AI"]))
db.add(Paper(id="2", cite_key="c2", title="ML Methods", authors=[make_author("Jane", "Doe")], year=2021, keywords=["ML"]))
db.add(Paper(id="3", cite_key="c3", title="AI Ethics", authors=[make_author("John", "Brown")], year=2022, keywords=["AI", "Ethics"]))
db.add(Paper(id="4", cite_key="c4", title="Quantum Computing", authors=[make_author("Alice", "Wonder")], year=2023, keywords=["Quantum"]))

print("=" * 70)
print("MAGIC METHODS: Implicit execute() in Python Contexts")
print("=" * 70)
print()

print("1️⃣  __iter__: For loops (iteration)")
print("   Code: for p in db.by_topic('AI'): ...")
print("   Result:")
for p in db.by_topic("AI"):
    print(f"      • {p.title}")
print()

print("2️⃣  __len__: len() function")
print("   Code: len(db.by_topic('AI'))")
count = len(db.by_topic("AI"))
print(f"   Result: {count} papers")
print()

print("3️⃣  __getitem__: Indexing [n]")
print("   Code: db.by_topic('AI')[0].title")
title = db.by_topic("AI")[0].title
print(f"   Result: {title}")
print()

print("4️⃣  __getitem__: Slicing [n:m]")
print("   Code: db.by_topic('AI')[0:2]")
sliced = db.by_topic("AI")[0:2]
print(f"   Result: {[p.title for p in sliced]}")
print()

print("5️⃣  __bool__: if statement")
print("   Code: if db.by_topic('AI'): ...")
if db.by_topic("AI"):
    print("   Result: True - AI papers exist")
print()

print("6️⃣  __bool__: Falsy query")
print("   Code: if db.by_topic('Photosynthesis'): ...")
if db.by_topic("Photosynthesis"):
    print("   Result: True")
else:
    print("   Result: False - No Photosynthesis papers")
print()

print("7️⃣  List comprehension (uses __iter__)")
print("   Code: [p.year for p in db.by_year(2021, 2023)]")
years = [p.year for p in db.by_year(2021, 2023)]
print(f"   Result: {years}")
print()

print("8️⃣  Unpacking (uses __iter__)")
print("   Code: p1, p2, *rest = db.by_topic('AI')")
p1, p2 = db.by_topic("AI")[:2]
print(f"   Result: p1={p1.title}, p2={p2.title}")
print()

print("9️⃣  any() / all() (uses __iter__)")
print("   Code: any(p.year > 2021 for p in db.by_topic('AI'))")
has_recent = any(p.year > 2021 for p in db.by_topic("AI"))
print(f"   Result: {has_recent}")
print()

print("🔟 Assignment with implicit execution (via __iter__)")
print("   Code: papers = db.by_topic('AI')")
papers = db.by_topic("AI")
print(f"   Result: papers is {type(papers).__name__} with {len(papers)} items")
print(f"   Can iterate: {[p.title for p in papers]}")
print()

print("=" * 70)
print("NO EXPLICIT .execute() OR .query() NEEDED!")
print("=" * 70)
print()

print("Python Magic Methods Summary:")
print("-" * 70)
print("__iter__     → for loops, list comprehensions, unpacking")
print("__len__      → len(query)")
print("__getitem__  → indexing [n] and slicing [n:m]")
print("__bool__     → if statements, boolean context")
print()
print("All return results by calling execute() internally.")
print()
