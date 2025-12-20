"""
Tests for fluent query builder (PapersQuery).

Tests chainable filter methods, sorting, limiting, and terminal operations.
"""

import pytest
from datetime import datetime
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.query import PapersQuery
from paper_scanner.core.models import Paper, Author


def make_author(first_name: str, last_name: str) -> Author:
    """Helper to create Author with required fields"""
    return Author(
        given_name=first_name,
        family_name=last_name,
        full_name=f"{first_name} {last_name}"
    )


class TestPapersQueryBasics:
    """Test basic query construction and execution"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with test papers"""
        db = PapersDatabase()
        
        # Add papers with various attributes
        db.add(Paper(
            id="p1",
            cite_key="Smith2020",
            title="Deep Learning in Healthcare",
            authors=[make_author("John", "Smith")],
            year=2020,
            keywords=["AI", "Healthcare", "Deep Learning"],
            abstract="This paper explores deep learning applications in healthcare"
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="Jones2021",
            title="Cloud Computing Architecture",
            authors=[make_author("Jane", "Jones")],
            year=2021,
            keywords=["Cloud", "Architecture", "Distributed Systems"],
            abstract="We present a new cloud computing architecture"
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="Brown2019",
            title="Artificial Intelligence and Ethics",
            authors=[
                make_author("Bob", "Brown"),
                make_author("Alice", "Brown")
            ],
            year=2019,
            keywords=["AI", "Ethics", "Philosophy"],
            abstract="Ethical considerations in artificial intelligence systems"
        ))
        
        db.add(Paper(
            id="p4",
            cite_key="Davis2022",
            title="Machine Learning for Climate Science",
            authors=[make_author("David", "Davis")],
            year=2022,
            keywords=["ML", "Climate", "Environmental"],
            abstract="Machine learning approaches to climate modeling"
        ))
        
        return db
    
    def test_query_returns_query_instance(self, db_with_papers):
        """query() returns PapersQuery instance"""
        query = db_with_papers.query()
        assert isinstance(query, PapersQuery)
    
    def test_execute_no_filters_returns_all(self, db_with_papers):
        """execute() with no filters returns all papers"""
        results = db_with_papers.query().execute()
        assert len(results) == 4
    
    def test_list_returns_same_as_execute(self, db_with_papers):
        """list() is alias for execute()"""
        execute_results = db_with_papers.query().execute()
        list_results = db_with_papers.query().list()
        assert execute_results == list_results


class TestFilterByTopic:
    """Test filter_by_topic chainable filter"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with test papers"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="AI1",
            title="AI Paper",
            authors=[],
            keywords=["AI", "Machine Learning"]
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="Cloud1",
            title="Cloud Paper",
            authors=[],
            keywords=["Cloud", "Distributed"]
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="NoneKeywords",
            title="Paper with no keywords",
            authors=[]
        ))
        
        return db
    
    def test_filter_by_topic_matches(self, db_with_papers):
        """filter_by_topic finds papers with matching keyword"""
        results = db_with_papers.query().filter_by_topic("AI").execute()
        assert len(results) == 1
        assert results[0].id == "p1"
    
    def test_filter_by_topic_case_insensitive(self, db_with_papers):
        """filter_by_topic is case-insensitive"""
        results = db_with_papers.query().filter_by_topic("ai").execute()
        assert len(results) == 1
    
    def test_filter_by_topic_partial_match(self, db_with_papers):
        """filter_by_topic uses substring matching"""
        results = db_with_papers.query().filter_by_topic("Mach").execute()
        assert len(results) == 1
        assert results[0].id == "p1"
    
    def test_filter_by_topic_no_matches(self, db_with_papers):
        """filter_by_topic returns empty when no matches"""
        results = db_with_papers.query().filter_by_topic("Quantum").execute()
        assert len(results) == 0


class TestFilterByYear:
    """Test filter_by_year chainable filter"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with papers from different years"""
        db = PapersDatabase()
        
        for year, count in [(2019, 1), (2020, 2), (2021, 1), (2022, 1)]:
            for i in range(count):
                db.add(Paper(
                    id=f"p{year}{i}",
                    cite_key=f"Paper{year}{i}",
                    title=f"Paper from {year}",
                    authors=[],
                    year=year
                ))
        
        return db
    
    def test_filter_by_year_single_year(self, db_with_papers):
        """filter_by_year with single year matches papers"""
        results = db_with_papers.query().filter_by_year(2020).execute()
        assert len(results) == 2
    
    def test_filter_by_year_range(self, db_with_papers):
        """filter_by_year with range matches papers in range"""
        results = db_with_papers.query().filter_by_year(2020, 2021).execute()
        assert len(results) == 3
    
    def test_filter_by_year_no_matches(self, db_with_papers):
        """filter_by_year returns empty when no matches"""
        results = db_with_papers.query().filter_by_year(2025).execute()
        assert len(results) == 0


class TestFilterByAuthor:
    """Test filter_by_author chainable filter"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with papers by different authors"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="Smith2020",
            title="Paper 1",
            authors=[make_author("John", "Smith")]
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="Jones2020",
            title="Paper 2",
            authors=[make_author("Jane", "Jones")]
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="Smith2021",
            title="Paper 3",
            authors=[
                make_author("John", "Smith"),
                make_author("Jane", "Doe")
            ]
        ))
        
        return db
    
    def test_filter_by_author_matches(self, db_with_papers):
        """filter_by_author finds papers by author"""
        results = db_with_papers.query().filter_by_author("Smith").execute()
        assert len(results) == 2
    
    def test_filter_by_author_case_insensitive(self, db_with_papers):
        """filter_by_author is case-insensitive"""
        results = db_with_papers.query().filter_by_author("smith").execute()
        assert len(results) == 2
    
    def test_filter_by_author_partial_match(self, db_with_papers):
        """filter_by_author uses substring matching"""
        results = db_with_papers.query().filter_by_author("Jon").execute()
        # "Jon" matches "Jones" but not "John"  
        assert len(results) == 1
        assert results[0].cite_key == "Jones2020"


class TestGrep:
    """Test grep full-text search filter"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with papers with different titles/abstracts"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="AI1",
            title="Deep Learning Applications",
            authors=[],
            abstract="This paper explores deep learning"
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="Cloud1",
            title="Cloud Architecture",
            authors=[],
            abstract="We present cloud computing approaches"
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="ML1",
            title="Machine Learning Basics",
            authors=[],
            abstract="An introduction to machine learning"
        ))
        
        return db
    
    def test_grep_in_title(self, db_with_papers):
        """grep finds text in title"""
        results = db_with_papers.query().grep("Deep").execute()
        assert len(results) == 1
        assert results[0].id == "p1"
    
    def test_grep_in_abstract(self, db_with_papers):
        """grep finds text in abstract"""
        results = db_with_papers.query().grep("cloud computing").execute()
        assert len(results) == 1
        assert results[0].id == "p2"
    
    def test_grep_case_insensitive(self, db_with_papers):
        """grep is case-insensitive"""
        results = db_with_papers.query().grep("LEARNING").execute()
        assert len(results) == 2


class TestSorting:
    """Test chainable sorting methods"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with papers to sort"""
        db = PapersDatabase()
        
        papers = [
            ("p1", "Zebra Research", 2021),
            ("p2", "Apple Studies", 2020),
            ("p3", "Monkey Insights", 2022),
        ]
        
        for id_, title, year in papers:
            db.add(Paper(
                id=id_,
                cite_key=f"cite{id_}",
                title=title,
                authors=[],
                year=year
            ))
        
        return db
    
    def test_order_by_year_ascending(self, db_with_papers):
        """order_by_year with descending=False sorts oldest first"""
        results = db_with_papers.query().order_by_year(descending=False).execute()
        years = [p.year for p in results]
        assert years == [2020, 2021, 2022]
    
    def test_order_by_year_descending(self, db_with_papers):
        """order_by_year with descending=True sorts newest first"""
        results = db_with_papers.query().order_by_year(descending=True).execute()
        years = [p.year for p in results]
        assert years == [2022, 2021, 2020]
    
    def test_order_by_title_ascending(self, db_with_papers):
        """order_by_title sorts alphabetically"""
        results = db_with_papers.query().order_by_title(descending=False).execute()
        titles = [p.title for p in results]
        assert titles == ["Apple Studies", "Monkey Insights", "Zebra Research"]
    
    def test_order_by_title_descending(self, db_with_papers):
        """order_by_title with descending=True sorts reverse alphabetically"""
        results = db_with_papers.query().order_by_title(descending=True).execute()
        titles = [p.title for p in results]
        assert titles == ["Zebra Research", "Monkey Insights", "Apple Studies"]


class TestLimiting:
    """Test chainable limiting methods"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with 5 papers"""
        db = PapersDatabase()
        
        for i in range(5):
            db.add(Paper(
                id=f"p{i}",
                cite_key=f"cite{i}",
                title=f"Paper {i}",
                authors=[],
                year=2020
            ))
        
        return db
    
    def test_top_limits_results(self, db_with_papers):
        """top() limits results"""
        results = db_with_papers.query().top(3).execute()
        assert len(results) == 3
    
    def test_limit_is_alias_for_top(self, db_with_papers):
        """limit() works same as top()"""
        top_results = db_with_papers.query().top(2).execute()
        limit_results = db_with_papers.query().limit(2).execute()
        assert len(top_results) == len(limit_results) == 2


class TestTerminalOperations:
    """Test terminal operations that end the query chain"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with test papers"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="cite1",
            title="First Paper",
            authors=[],
            year=2020,
            keywords=["AI"]
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="cite2",
            title="Second Paper",
            authors=[],
            year=2021,
            keywords=["AI"]
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="cite3",
            title="Third Paper",
            authors=[],
            year=2022,
            keywords=["ML"]
        ))
        
        return db
    
    def test_first_returns_single_paper(self, db_with_papers):
        """first() returns first matching paper"""
        result = db_with_papers.query().filter_by_topic("AI").first()
        assert result is not None
        assert result.id in ["p1", "p2"]
    
    def test_first_returns_none_when_no_matches(self, db_with_papers):
        """first() returns None when no matches"""
        result = db_with_papers.query().filter_by_topic("Quantum").first()
        assert result is None
    
    def test_count_returns_total(self, db_with_papers):
        """count() returns total matching papers"""
        total = db_with_papers.query().filter_by_topic("AI").count()
        assert total == 2
    
    def test_count_no_filters(self, db_with_papers):
        """count() with no filters returns all papers"""
        total = db_with_papers.query().count()
        assert total == 3


class TestChaining:
    """Test chainable method combinations"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with diverse papers"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="AI2020",
            title="AI Fundamentals",
            authors=[make_author("John", "Smith")],
            year=2020,
            keywords=["AI", "Fundamentals"],
            abstract="Basic AI concepts"
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="ML2021",
            title="Machine Learning Advanced",
            authors=[make_author("Jane", "Jones")],
            year=2021,
            keywords=["ML", "Advanced"],
            abstract="Deep learning techniques"
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="AI2022",
            title="AI Applications",
            authors=[make_author("John", "Brown")],
            year=2022,
            keywords=["AI", "Applications"],
            abstract="Real-world AI deployment"
        ))
        
        return db
    
    def test_filter_then_sort_then_limit(self, db_with_papers):
        """Can chain filter -> sort -> limit"""
        results = (db_with_papers.query()
                   .filter_by_topic("AI")
                   .order_by_year(descending=True)
                   .top(1)
                   .execute())
        assert len(results) == 1
        assert results[0].year == 2022
    
    def test_multiple_filters(self, db_with_papers):
        """Can chain multiple filters"""
        results = (db_with_papers.query()
                   .filter_by_topic("AI")
                   .filter_by_year(2020, 2021)
                   .execute())
        assert len(results) == 1
        assert results[0].id == "p1"
    
    def test_grep_with_year_filter(self, db_with_papers):
        """Can chain grep with other filters"""
        results = (db_with_papers.query()
                   .grep("learning")
                   .filter_by_year(2021)
                   .execute())
        assert len(results) == 1
        assert results[0].id == "p2"
    
    def test_author_filter_with_topic_and_sort(self, db_with_papers):
        """Complex chain: author -> topic -> sort -> limit"""
        results = (db_with_papers.query()
                   .filter_by_author("John")
                   .filter_by_topic("AI")
                   .order_by_year(descending=True)
                   .top(1)
                   .execute())
        assert len(results) == 1
        assert results[0].year == 2022


class TestExcludeDuplicates:
    """Test exclude_duplicates filter"""
    
    def test_exclude_duplicates_filter(self):
        """exclude_duplicates removes duplicate papers"""
        db = PapersDatabase()
        
        # Add primary paper
        primary = Paper(
            id="p1",
            cite_key="primary",
            title="Primary Paper",
            authors=[]
        )
        db.add(primary)
        
        # Add duplicate with proper reference
        duplicate = Paper(
            id="p2",
            cite_key="duplicate",
            title="Duplicate Paper",
            authors=[],
            duplicate_of=primary  # Use Paper object, not string ID
        )
        db.add(duplicate)
        
        # Without exclude_duplicates
        all_results = db.query().execute()
        assert len(all_results) == 2
        
        # With exclude_duplicates
        primary_results = db.query().exclude_duplicates().execute()
        assert len(primary_results) == 1
        assert primary_results[0].id == "p1"


class TestCustomFilter:
    """Test custom filter method"""
    
    def test_custom_filter_predicate(self):
        """filter() accepts custom predicate"""
        db = PapersDatabase()
        
        db.add(Paper(id="p1", cite_key="c1", title="Title", authors=[], year=2020))
        db.add(Paper(id="p2", cite_key="c2", title="Title", authors=[], year=2021))
        db.add(Paper(id="p3", cite_key="c3", title="Title", authors=[], year=2022))
        
        # Custom filter: year is even
        results = db.query().filter(lambda p: p.year % 2 == 0).execute()
        assert len(results) == 2
        assert all(p.year % 2 == 0 for p in results)


class TestImplicitExecution:
    """Test magic methods for implicit execution without execute()"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with test papers"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="c1",
            title="AI Paper",
            authors=[],
            year=2020,
            keywords=["AI"]
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="c2",
            title="ML Paper",
            authors=[],
            year=2021,
            keywords=["ML"]
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="c3",
            title="AI Ethics",
            authors=[],
            year=2022,
            keywords=["AI", "Ethics"]
        ))
        
        return db
    
    def test_iteration_without_execute(self, db_with_papers):
        """Can iterate over query results without explicit execute()"""
        count = 0
        for paper in db_with_papers.query().filter_by_topic("AI"):
            count += 1
        assert count == 2
    
    def test_len_without_execute(self, db_with_papers):
        """len() works on query without explicit execute()"""
        query = db_with_papers.query().filter_by_topic("AI")
        assert len(query) == 2
    
    def test_indexing_without_execute(self, db_with_papers):
        """Can use indexing [0], [1] without explicit execute()"""
        query = db_with_papers.query().filter_by_topic("AI").order_by_year(descending=True)
        assert query[0].id == "p3"  # Most recent AI paper
        assert query[1].id == "p1"
    
    def test_slicing_without_execute(self, db_with_papers):
        """Can use slicing [0:2] without explicit execute()"""
        results = db_with_papers.query().order_by_year(descending=True)[0:2]
        assert len(results) == 2
        assert results[0].year == 2022
        assert results[1].year == 2021
    
    def test_bool_check_without_execute(self, db_with_papers):
        """Can use bool() check on query without explicit execute()"""
        has_ai = bool(db_with_papers.query().filter_by_topic("AI"))
        no_quantum = bool(db_with_papers.query().filter_by_topic("Quantum"))
        assert has_ai is True
        assert no_quantum is False
    
    def test_if_statement_without_execute(self, db_with_papers):
        """Can use query in if statement without explicit execute()"""
        if db_with_papers.query().filter_by_topic("AI"):
            result = "found"
        else:
            result = "not found"
        assert result == "found"


class TestShorthandMethods:
    """Test convenience shorthand methods on PapersDatabase"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database with test papers"""
        db = PapersDatabase()
        
        db.add(Paper(
            id="p1",
            cite_key="c1",
            title="AI Fundamentals",
            authors=[make_author("John", "Smith")],
            year=2020,
            keywords=["AI"],
            abstract="Basic AI concepts"
        ))
        
        db.add(Paper(
            id="p2",
            cite_key="c2",
            title="Machine Learning",
            authors=[make_author("Jane", "Doe")],
            year=2021,
            keywords=["ML"],
            abstract="Machine learning methods"
        ))
        
        db.add(Paper(
            id="p3",
            cite_key="c3",
            title="AI Ethics",
            authors=[make_author("John", "Brown")],
            year=2022,
            keywords=["AI", "Ethics"],
            abstract="Ethical AI"
        ))
        
        return db
    
    def test_where_shorthand(self, db_with_papers):
        """where() shorthand for custom filter"""
        results = db_with_papers.where(lambda p: p.year >= 2021).execute()
        assert len(results) == 2
    
    def test_by_topic_shorthand(self, db_with_papers):
        """by_topic() shorthand"""
        results = db_with_papers.by_topic("AI").execute()
        assert len(results) == 2
    
    def test_by_author_shorthand(self, db_with_papers):
        """by_author() shorthand"""
        results = db_with_papers.by_author("John").execute()
        assert len(results) == 2
    
    def test_by_year_shorthand(self, db_with_papers):
        """by_year() shorthand"""
        results = db_with_papers.by_year(2021, 2022).execute()
        assert len(results) == 2
    
    def test_search_shorthand(self, db_with_papers):
        """search() shorthand for grep"""
        results = db_with_papers.search("ethical").execute()
        assert len(results) == 1
        assert results[0].id == "p3"
    
    def test_shorthand_with_implicit_execution(self, db_with_papers):
        """Shorthand methods work with implicit execution via indexing"""
        first_ai_paper = db_with_papers.by_topic("AI")[0]
        assert "AI" in first_ai_paper.keywords
    
    def test_shorthand_with_len(self, db_with_papers):
        """Shorthand methods work with len()"""
        ai_count = len(db_with_papers.by_topic("AI"))
        assert ai_count == 2
    
    def test_shorthand_chaining(self, db_with_papers):
        """Shorthand methods return query builder for chaining"""
        results = db_with_papers.by_topic("AI").order_by_year(descending=True).execute()
        assert results[0].year == 2022
        assert results[1].year == 2020


class TestCompactSyntax:
    """Test most compact usage patterns"""
    
    @pytest.fixture
    def db_with_papers(self):
        """Create database"""
        db = PapersDatabase()
        
        db.add(Paper(id="p1", cite_key="c1", title="Paper", authors=[], year=2020, keywords=["AI"]))
        db.add(Paper(id="p2", cite_key="c2", title="Paper", authors=[], year=2021, keywords=["ML"]))
        db.add(Paper(id="p3", cite_key="c3", title="Paper", authors=[], year=2022, keywords=["AI"]))
        
        return db
    
    def test_most_compact_usage_1(self, db_with_papers):
        """Single line: get first AI paper"""
        paper = db_with_papers.by_topic("AI")[0]
        assert "AI" in paper.keywords
    
    def test_most_compact_usage_2(self, db_with_papers):
        """Single line: count papers by topic"""
        count = len(db_with_papers.by_topic("AI"))
        assert count == 2
    
    def test_most_compact_usage_3(self, db_with_papers):
        """Single line: check if papers exist"""
        if db_with_papers.by_topic("Quantum"):
            found = True
        else:
            found = False
        assert found is False
    
    def test_most_compact_usage_4(self, db_with_papers):
        """Single line: iterate without explicit list()"""
        ids = [p.id for p in db_with_papers.by_topic("AI")]
        assert len(ids) == 2
    
    def test_most_compact_usage_5(self, db_with_papers):
        """Single line: complex chain without execute()"""
        result = db_with_papers.by_topic("AI").order_by_year(descending=True)[0]
        assert result.year == 2022
