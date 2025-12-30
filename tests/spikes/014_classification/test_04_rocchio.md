# Adaptive Rocchio-Based Semantic Screening for Systematic Reviews

## Introduction

This document describes an adaptive semantic screening approach for systematic literature reviews that evolves decision boundaries as papers are labeled. Rather than applying a static similarity threshold to all papers against a fixed query, the screening filter adapts using the **Rocchio Algorithm** - a classic information retrieval technique that maintains persistent centroid vectors across snowballing iterations.

The key insight is to bootstrap screening confidence from metadata and keyword filtering results (e.g., 20 accepted, 50 rejected papers from initial filtering), then use those labeled samples to compute centroids in embedding space. As the system encounters new papers during snowballing iterations, centroids update incrementally, creating a reinforcing feedback loop where the decision boundary naturally evolves to match the emerging literature.

**Key properties:**
- No LLM required - pure embedding-based vector operations
- Centroid vectors persist across runs and snowballing iterations  
- Computationally efficient - O(1) centroid update per paper
- Well-established theoretical foundation (Rocchio, 1971)
- Transparent decision boundary that can be inspected and explained

---

## Prototyping Plan

### Prototype 1: Zero-Seed Baseline

**Objective**: Test Rocchio screening with no initial accept/reject seeds, starting from research question alone.

**Flow**:
1. Load `scopus_sample_20.bib` into database via bibtex_import step (zero papers pre-labeled)
2. Apply keyword_screening step to generate initial accept/reject labels
3. Apply semantic_classification step (Rocchio-based) with zero seeds, initializing from research question embedding only
4. Observe classification results and centroid evolution with minimal training signal

**Research Question**: "How do incumbent firms involve suppliers in digital innovation processes?"

**Expected Outcome**: Understanding how Rocchio performs with minimal labeled seeds; establishing baseline for centroid quality.

### Prototype 2: Improved Dataset with Better Seeds

**Objective**: Test Rocchio with higher-quality accept/reject distribution using an improved bib file.

**Flow**:
1. Load improved bib file into database (to be created with better accept/reject ratio)
2. Apply keyword_screening step to generate initial labels
3. Apply semantic_classification step with seeds from keyword_screening output
4. Compare classification quality and centroid effectiveness vs. Prototype 1

**Expected Outcome**: Better understanding of Rocchio's adaptive learning with quality seed data.

---

## Design & Approach

### Core Algorithm: Rocchio with Persistent Centroids

The Rocchio Algorithm (1971) represents a query using a weighted combination of:
- The original research question embedding
- The centroid of accepted papers
- The centroid of rejected papers

This creates a dynamic decision boundary that can be updated incrementally as more papers are labeled. Unlike LLM-based approaches, centroids are simple vectors that can be persisted to disk and restored across sessions, making them ideal for long-running systematic review processes with snowballing iterations.

### Mathematical Foundation

The Rocchio score for a given document embedding is:

```
Q_new = α·Q_original + β·(1/|D_r|)·Σd∈D_r + γ·(1/|D_nr|)·Σd∈D_nr
```

Where:
- `Q_original` = your research question embedding (or initial seed centroid)
- `D_r` = relevant (accepted) papers
- `D_nr` = non-relevant (rejected) papers  
- `α, β, γ` = weights (typically α=1, β=0.75, γ=0.15)

### Workflow Across Iterations

**Iteration 0 (Bootstrapping):**
1. Embed research question to initialize query centroid
2. Receive labeled results from metadata/keyword screening (20 accepted, 50 rejected)
3. Compute initial centroids from labeled papers
4. Score remaining papers in corpus against decision boundary
5. Separate into auto-accept, auto-reject, and uncertain for manual review

**Iteration 1+ (Snowballing):**
1. Load persisted centroids from disk
2. Process new papers from forward/backward citations
3. Route through same scoring logic (centroids already reflect prior decisions)
4. Update centroids incrementally with any manually labeled papers
5. Save updated centroids for next iteration

The centroids naturally strengthen the decision boundary - accepted papers move the relevant centroid closer to them, rejected papers push the irrelevant centroid away, and subsequent papers are evaluated against this evolving boundary.

### Implementation Approach

The formula:

```
Q_new = α·Q_original + β·(1/|D_r|)·Σd∈D_r + γ·(1/|D_nr|)·Σd∈D_nr
```

Where:
- `Q_original` = your research question embedding (or initial seed centroid)
- `D_r` = relevant (accepted) papers
- `D_nr` = non-relevant (rejected) papers
- `α, β, γ` = weights (typically α=1, β=0.75, γ=0.15)

## Implementation

### Core Data Structures and Classes

```python
"""
Adaptive Rocchio-based screening filter for CC-CASLR.

Persists centroids across snowballing iterations, enabling
the decision boundary to evolve as more papers are labeled.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import json
import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class ScreeningState:
    """Persistent state for the adaptive screener."""
    
    # Centroids (the key persistent vectors)
    centroid_relevant: np.ndarray | None = None
    centroid_irrelevant: np.ndarray | None = None
    query_centroid: np.ndarray | None = None  # From research question
    
    # Counts for incremental centroid updates
    n_relevant: int = 0
    n_irrelevant: int = 0
    
    # Rocchio weights
    alpha: float = 1.0    # Weight for query/RQ
    beta: float = 0.75    # Weight for relevant docs
    gamma: float = 0.15   # Weight for irrelevant docs
    
    # Thresholds for decision
    accept_threshold: float = 0.7
    reject_threshold: float = 0.3
    
    # History for reproducibility
    iteration: int = 0
    papers_seen: list[str] = field(default_factory=list)
    
    def save(self, path: Path) -> None:
        """Persist state to disk."""
        state = {
            'centroid_relevant': self.centroid_relevant.tolist() if self.centroid_relevant is not None else None,
            'centroid_irrelevant': self.centroid_irrelevant.tolist() if self.centroid_irrelevant is not None else None,
            'query_centroid': self.query_centroid.tolist() if self.query_centroid is not None else None,
            'n_relevant': self.n_relevant,
            'n_irrelevant': self.n_irrelevant,
            'alpha': self.alpha,
            'beta': self.beta,
            'gamma': self.gamma,
            'accept_threshold': self.accept_threshold,
            'reject_threshold': self.reject_threshold,
            'iteration': self.iteration,
            'papers_seen': self.papers_seen,
        }
        path.write_text(json.dumps(state, indent=2))
    
    @classmethod
    def load(cls, path: Path) -> 'ScreeningState':
        """Load state from disk."""
        data = json.loads(path.read_text())
        state = cls()
        state.centroid_relevant = np.array(data['centroid_relevant']) if data['centroid_relevant'] else None
        state.centroid_irrelevant = np.array(data['centroid_irrelevant']) if data['centroid_irrelevant'] else None
        state.query_centroid = np.array(data['query_centroid']) if data['query_centroid'] else None
        state.n_relevant = data['n_relevant']
        state.n_irrelevant = data['n_irrelevant']
        state.alpha = data['alpha']
        state.beta = data['beta']
        state.gamma = data['gamma']
        state.accept_threshold = data['accept_threshold']
        state.reject_threshold = data['reject_threshold']
        state.iteration = data['iteration']
        state.papers_seen = data['papers_seen']
        return state


class AdaptiveRocchioScreener:
    """
    Rocchio-based adaptive screening filter.
    
    Key properties:
    - No LLM required (pure embeddings + vector math)
    - Centroids persist across snowballing iterations
    - Decision boundary evolves with each labeled paper
    - Computationally efficient (cosine similarity only)
    
    References:
        Rocchio, J. J. (1971). Relevance feedback in information retrieval.
        Manning et al. (2008). Introduction to Information Retrieval, Ch. 9 & 14.
    """
    
    def __init__(
        self,
        model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        state_path: Path | None = None,
    ):
        self.model = SentenceTransformer(model_name)
        self.state_path = state_path
        
        # Load or initialize state
        if state_path and state_path.exists():
            self.state = ScreeningState.load(state_path)
        else:
            self.state = ScreeningState()
    
    def initialize_from_research_question(self, rq_text: str) -> None:
        """
        Bootstrap the query centroid from the research question.
        
        This provides the initial "direction" in embedding space.
        """
        self.state.query_centroid = self._embed(rq_text)
    
    def bootstrap_from_seeds(
        self,
        accepted_abstracts: list[str],
        rejected_abstracts: list[str],
    ) -> None:
        """
        Initialize centroids from metadata/keyword screening results.
        
        This is your "50 rejected, 20 accepted" from the first pass.
        """
        if accepted_abstracts:
            embeddings = self._embed_batch(accepted_abstracts)
            self.state.centroid_relevant = embeddings.mean(axis=0)
            self.state.n_relevant = len(accepted_abstracts)
        
        if rejected_abstracts:
            embeddings = self._embed_batch(rejected_abstracts)
            self.state.centroid_irrelevant = embeddings.mean(axis=0)
            self.state.n_irrelevant = len(rejected_abstracts)
        
        self._persist()
    
    def classify(
        self,
        abstract: str,
        paper_id: str | None = None,
    ) -> tuple[Literal['accept', 'reject', 'uncertain'], float]:
        """
        Classify a paper based on distance to centroids.
        
        Returns:
            (decision, confidence) where confidence is in [0, 1]
        """
        embedding = self._embed(abstract)
        score = self._compute_rocchio_score(embedding)
        
        # Track for reproducibility
        if paper_id:
            self.state.papers_seen.append(paper_id)
        
        if score >= self.state.accept_threshold:
            return ('accept', score)
        elif score <= self.state.reject_threshold:
            return ('reject', 1.0 - score)
        else:
            return ('uncertain', 0.5 - abs(score - 0.5))
    
    def update(self, abstract: str, label: bool) -> None:
        """
        Update centroids with new labeled paper.
        
        Uses incremental mean update (no need to recompute from scratch):
            new_centroid = old_centroid + (new_embedding - old_centroid) / (n + 1)
        """
        embedding = self._embed(abstract)
        
        if label:  # Relevant/Accept
            if self.state.centroid_relevant is None:
                self.state.centroid_relevant = embedding
            else:
                # Incremental mean update
                self.state.centroid_relevant = (
                    self.state.centroid_relevant + 
                    (embedding - self.state.centroid_relevant) / (self.state.n_relevant + 1)
                )
            self.state.n_relevant += 1
        else:  # Irrelevant/Reject
            if self.state.centroid_irrelevant is None:
                self.state.centroid_irrelevant = embedding
            else:
                self.state.centroid_irrelevant = (
                    self.state.centroid_irrelevant + 
                    (embedding - self.state.centroid_irrelevant) / (self.state.n_irrelevant + 1)
                )
            self.state.n_irrelevant += 1
        
        self._persist()
    
    def next_iteration(self) -> None:
        """
        Mark transition to next snowballing iteration.
        
        Centroids persist - this just increments the iteration counter
        for tracking purposes.
        """
        self.state.iteration += 1
        self._persist()
    
    def _compute_rocchio_score(self, embedding: np.ndarray) -> float:
        """
        Compute Rocchio-style relevance score.
        
        Score is normalized to [0, 1] where:
            1.0 = definitely relevant
            0.0 = definitely irrelevant
            0.5 = uncertain
        """
        scores = []
        weights = []
        
        # Query/RQ similarity
        if self.state.query_centroid is not None:
            sim_query = self._cosine_similarity(embedding, self.state.query_centroid)
            scores.append(sim_query)
            weights.append(self.state.alpha)
        
        # Relevant centroid similarity (positive signal)
        if self.state.centroid_relevant is not None:
            sim_relevant = self._cosine_similarity(embedding, self.state.centroid_relevant)
            scores.append(sim_relevant)
            weights.append(self.state.beta)
        
        # Irrelevant centroid similarity (negative signal)
        if self.state.centroid_irrelevant is not None:
            sim_irrelevant = self._cosine_similarity(embedding, self.state.centroid_irrelevant)
            scores.append(-sim_irrelevant)  # Negative because we want to move AWAY
            weights.append(self.state.gamma)
        
        if not scores:
            return 0.5  # No information yet
        
        # Weighted combination, normalized to [0, 1]
        raw_score = np.average(scores, weights=weights)
        return (raw_score + 1) / 2  # Map [-1, 1] to [0, 1]
    
    def _embed(self, text: str) -> np.ndarray:
        """Embed a single text."""
        return self.model.encode(text, convert_to_numpy=True)
    
    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed multiple texts."""
        return self.model.encode(texts, convert_to_numpy=True)
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def _persist(self) -> None:
        """Save state if path is configured."""
        if self.state_path:
            self.state.save(self.state_path)
```

### Model Selection for Scientific Text

The embedding model choice significantly impacts centroid quality. Different models optimize for different aspects of document similarity:

| Model | Dimensions | Speed | Scientific Domain | Recommendation |
|-------|------------|-------|-------------------|----------------|
| `allenai/specter2` | 768 | Medium | ⭐⭐⭐⭐⭐ | **Best for systematic reviews** |
| `BAAI/bge-base-en-v1.5` | 768 | Medium | ⭐⭐⭐ | Fallback - best general embeddings |
| `intfloat/e5-base-v2` | 768 | Medium | ⭐⭐⭐ | Good balance, simpler integration |
| `sentence-transformers/all-mpnet-base-v2` | 768 | Medium | ⭐⭐⭐ | General purpose |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Fast | ⭐⭐ | Fast baseline only |

**Primary recommendation:** `allenai/specter2` - trained on citation graphs and specifically optimized for scientific document relatedness. Papers close in citation space are close in embedding space, which aligns perfectly with systematic review logic: relevant papers tend to cite each other.

**Fallback recommendation:** `BAAI/bge-base-en-v1.5` - top performer on general benchmarks if SPECTER doesn't work well for your specific domain.

---

### Usage Pattern Across Iterations

```python
from pathlib import Path

# Initialize (or load existing state)
screener = AdaptiveRocchioScreener(
    model_name='sentence-transformers/all-MiniLM-L6-v2',
    state_path=Path('screening_state.json')  # Persists across runs!
)

# ITERATION 0: Bootstrap from research question + keyword screening
screener.initialize_from_research_question(
    "How do vendors engage incumbent organizations in IT/OT convergence?"
)
screener.bootstrap_from_seeds(
    accepted_abstracts=accepted_from_keyword_screening,  # Your 20
    rejected_abstracts=rejected_from_keyword_screening,  # Your 50
)

# Screen remaining papers
for paper in unlabeled_pool:
    decision, confidence = screener.classify(paper.abstract, paper.id)
    
    if decision == 'accept':
        # Auto-accept and update centroid
        screener.update(paper.abstract, label=True)
        accept_paper(paper)
    elif decision == 'reject':
        # Auto-reject and update centroid
        screener.update(paper.abstract, label=False)
        reject_paper(paper)
    else:
        # Route to manual review (or your confidence cascade)
        manual_review_queue.append(paper)

# ITERATION 1: Forward snowballing
screener.next_iteration()

# New papers from citations - centroids are ALREADY updated from iteration 0
for paper in forward_citation_papers:
    decision, confidence = screener.classify(paper.abstract, paper.id)
    # ... same logic, but now with refined centroids
```

---

## Advantages for Systematic Review Screening

| Feature | Benefit |
|---------|---------|
| **Persistent centroids** | Decision boundary survives between runs; centroids evolve across snowballing iterations |
| **No LLM required** | Fast, deterministic, reproducible, no API costs |
| **Incremental updates** | O(1) centroid update per paper (incremental mean formula) |
| **Well-established theory** | Decades of IR research; cite authoritative papers |
| **Confidence routing** | Uncertain papers naturally route to manual review |
| **Transparent boundaries** | Easy to inspect and explain why papers were included/excluded |
| **Scalable to long reviews** | Handles hundreds or thousands of papers efficiently |

---

## Recommended Test Protocol

To evaluate which embedding model works best for your domain, run this evaluation:

```python
def evaluate_model_for_rocchio(model_name, seed_accept, seed_reject, test_papers):
    """
    Evaluate how well centroids separate accept/reject papers.
    
    Key metrics:
    1. Intra-class variance (lower = tighter clusters = better)
    2. Inter-class distance (higher = more separable = better)
    3. Silhouette score (combines both)
    """
    # Embed seeds
    accept_embeddings = embed(seed_accept, model_name)
    reject_embeddings = embed(seed_reject, model_name)
    
    # Compute centroids
    centroid_accept = accept_embeddings.mean(axis=0)
    centroid_reject = reject_embeddings.mean(axis=0)
    
    # Metrics
    intra_accept = np.mean([cosine_dist(e, centroid_accept) for e in accept_embeddings])
    intra_reject = np.mean([cosine_dist(e, centroid_reject) for e in reject_embeddings])
    inter_class = cosine_dist(centroid_accept, centroid_reject)
    
    # Separation ratio (higher = better)
    separation = inter_class / (intra_accept + intra_reject)
    
    return {
        'model': model_name,
        'intra_accept': intra_accept,
        'intra_reject': intra_reject,
        'inter_class': inter_class,
        'separation_ratio': separation,
    }
```

**Recommendation:** Start with SPECTER2. If it underperforms on your IT/OT domain, fall back to BGE.

---

## References

**Foundational - Rocchio Algorithm:**
- Rocchio, J. J. (1971). Relevance feedback in information retrieval. In *The SMART retrieval system: Experiments in automatic document processing* (pp. 313–323). Prentice-Hall.

**Classic Textbook - Information Retrieval Theory:**
- Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press. https://nlp.stanford.edu/IR-book/ (Chapters 9 & 14)

**Probabilistic Analysis:**
- Joachims, T. (1997). A probabilistic analysis of the Rocchio algorithm with TFIDF for text categorization. *Proceedings of ICML 1997*.

**Scientific Document Embeddings - SPECTER:**
- Cohan, A., Feldman, S., Beltagy, I., Downey, D., & Weld, D. S. (2020). SPECTER: Document-level representation learning using citation-informed transformers. *Proceedings of ACL 2020*, 2270–2282. https://aclanthology.org/2020.acl-main.207/

**SPECTER2 - Improved Version:**
- Singh, A., D'Arcy, M., Cohan, A., Downey, D., & Feldman, S. (2023). SciRepEval: A multi-format benchmark for scientific document representations. *Proceedings of EMNLP 2023*.

**General Embeddings Benchmarks - BGE:**
- Xiao, S., Liu, Z., Zhang, P., & Muennighoff, N. (2023). C-Pack: Packaged resources to advance general Chinese embedding. *arXiv preprint arXiv:2309.07597*.

**Related - Feedback Loop Approaches:**
- Hearst, M. A. (1992). Direction-based text interpretation as an information access paradigm. *PhD Thesis, UC Berkeley*.
- Salton, G., & McGill, M. J. (1983). *Introduction to modern information retrieval*. McGraw-Hill. (Classic reference for relevance feedback)