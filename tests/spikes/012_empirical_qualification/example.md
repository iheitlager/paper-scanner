# These are some examples of regex based empirical paper classifiers

```python
import re

def is_empirical_research(abstract):
    abstract_lower = abstract.lower()
    
    # Quantitative indicators
    quant_patterns = [
        r'\bn\s*=\s*\d+',  # sample size
        r'survey.*\d+.*participants?',
        r'statistical analysis',
        r'regression|correlation|anova|t-test',
        r'questionnaire|measurement|hypothesis',
        r'significant.*p\s*[<>]',
    ]
    
    # Qualitative indicators  
    qual_patterns = [
        r'interview.*participants?',
        r'case study|ethnograph|grounded theory',
        r'thematic analysis|content analysis',
        r'observational study|field work',
        r'focus group|phenomenological',
    ]
    
    # Method indicators
    method_patterns = [
        r'data collection|data gathered',
        r'empirical study|empirical investigation',
        r'experimental design|quasi-experimental',
        r'longitudinal|cross-sectional',
    ]
    
    quant_score = sum(1 for p in quant_patterns if re.search(p, abstract_lower))
    qual_score = sum(1 for p in qual_patterns if re.search(p, abstract_lower))
    method_score = sum(1 for p in method_patterns if re.search(p, abstract_lower))
    
    return {
        'is_empirical': (quant_score + qual_score + method_score) >= 2,
        'type': 'quantitative' if quant_score > qual_score else 'qualitative' if qual_score > 0 else 'unknown',
        'confidence': min((quant_score + qual_score + method_score) / 10, 1.0)
    }
```

## Example 2: More extensive
```python
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class StudyType(Enum):
    EMPIRICAL_QUALITATIVE = "empirical_qualitative"
    EMPIRICAL_QUANTITATIVE = "empirical_quantitative"
    EMPIRICAL_MIXED = "empirical_mixed"
    CASE_STUDY = "case_study"
    NONE = None

@dataclass
class ClassificationResult:
    study_type: StudyType
    confidence: float
    indicators: Dict[str, int]
    key_matches: List[str]

class EmpiricalResearchClassifier:
    def __init__(self):
        # Quantitative indicators
        self.quantitative_patterns = [
            r'\bn\s*=\s*\d+',
            r'sample size of \d+',
            r'\d+\s*participants?',
            r'\d+\s*respondents?',
            r'statistical analysis',
            r'regression|correlation|anova|t-test|chi-square',
            r'significant.*p\s*[<>]\s*0\.\d+',
            r'survey|questionnaire',
            r'likert scale',
            r'hypothesis test',
            r'control group|treatment group',
            r'randomized|random assignment',
            r'quantitative method',
            r'statistical significance',
            r'confidence interval',
            r'standard deviation|mean.*sd'
        ]
        
        # Qualitative indicators
        self.qualitative_patterns = [
            r'interview|interviewed',
            r'semi-structured interview',
            r'in-depth interview',
            r'focus group',
            r'observation|observational',
            r'ethnographic|ethnography',
            r'thematic analysis',
            r'content analysis',
            r'grounded theory',
            r'discourse analysis',
            r'narrative analysis',
            r'phenomenological',
            r'coding.*themes',
            r'qualitative method',
            r'open-ended questions',
            r'field notes',
            r'participant observation'
        ]
        
        # Case study indicators
        self.case_study_patterns = [
            r'case study',
            r'single case',
            r'multiple case',
            r'comparative case',
            r'exploratory case',
            r'descriptive case',
            r'case analysis',
            r'within-case',
            r'cross-case',
            r'case comparison',
            r'case description',
            r'in-depth analysis of.*organization|company|project|system'
        ]
        
        # Mixed methods indicators
        self.mixed_patterns = [
            r'mixed method',
            r'multi-method',
            r'triangulation',
            r'both.*qualitative.*quantitative',
            r'combining.*interviews.*survey',
            r'quantitative.*qualitative|qualitative.*quantitative',
            r'sequential explanatory',
            r'concurrent triangulation',
            r'survey.*followed by.*interview',
            r'interviews?.*supplement.*survey'
        ]
        
        # General empirical indicators
        self.empirical_patterns = [
            r'data collect|collected data',
            r'empirical study|empirical investigation',
            r'field study|field research',
            r'research design',
            r'data analysis',
            r'findings|results',
            r'evidence from',
            r'methodology|methods section'
        ]

    def _count_matches(self, text: str, patterns: List[str]) -> Tuple[int, List[str]]:
        """Count pattern matches and return matched patterns"""
        text_lower = text.lower()
        matches = []
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matches.append(pattern.replace('|', ' or ').replace(r'\b', '').replace(r'\d+', 'N'))
        return len(matches), matches

    def classify(self, abstract: str) -> ClassificationResult:
        """Classify abstract into one of five study types"""
        
        # Count matches for each category
        quant_count, quant_matches = self._count_matches(abstract, self.quantitative_patterns)
        qual_count, qual_matches = self._count_matches(abstract, self.qualitative_patterns)
        case_count, case_matches = self._count_matches(abstract, self.case_study_patterns)
        mixed_count, mixed_matches = self._count_matches(abstract, self.mixed_patterns)
        empirical_count, empirical_matches = self._count_matches(abstract, self.empirical_patterns)
        
        indicators = {
            'quantitative': quant_count,
            'qualitative': qual_count,
            'case_study': case_count,
            'mixed': mixed_count,
            'empirical': empirical_count
        }
        
        # Determine study type based on patterns
        study_type = self._determine_study_type(indicators)
        
        # Calculate confidence
        confidence = self._calculate_confidence(study_type, indicators)
        
        # Collect key matches
        all_matches = []
        if study_type == StudyType.EMPIRICAL_QUANTITATIVE:
            all_matches = quant_matches[:3]  # Top 3 matches
        elif study_type == StudyType.EMPIRICAL_QUALITATIVE:
            all_matches = qual_matches[:3]
        elif study_type == StudyType.EMPIRICAL_MIXED:
            all_matches = (mixed_matches[:2] + quant_matches[:1] + qual_matches[:1])[:3]
        elif study_type == StudyType.CASE_STUDY:
            all_matches = case_matches[:3]
        
        return ClassificationResult(
            study_type=study_type,
            confidence=confidence,
            indicators=indicators,
            key_matches=all_matches
        )
    
    def _determine_study_type(self, indicators: Dict[str, int]) -> StudyType:
        """Determine study type based on indicator counts"""
        
        # Check for case study first (it can overlap with others)
        if indicators['case_study'] >= 2:
            return StudyType.CASE_STUDY
        
        # Check for explicit mixed methods
        if indicators['mixed'] >= 1:
            return StudyType.EMPIRICAL_MIXED
        
        # Check for implicit mixed methods (both qual and quant indicators)
        if indicators['quantitative'] >= 2 and indicators['qualitative'] >= 2:
            return StudyType.EMPIRICAL_MIXED
        
        # Check for primarily quantitative
        if indicators['quantitative'] >= 2:
            return StudyType.EMPIRICAL_QUANTITATIVE
        
        # Check for primarily qualitative
        if indicators['qualitative'] >= 2:
            return StudyType.EMPIRICAL_QUALITATIVE
        
        # Check if any empirical indicators but not enough specific method indicators
        if indicators['empirical'] >= 2:
            # Lean towards the method with more indicators
            if indicators['quantitative'] > indicators['qualitative']:
                return StudyType.EMPIRICAL_QUANTITATIVE
            elif indicators['qualitative'] > indicators['quantitative']:
                return StudyType.EMPIRICAL_QUALITATIVE
            else:
                return StudyType.EMPIRICAL_MIXED
        
        # No clear empirical indicators
        return StudyType.NONE
    
    def _calculate_confidence(self, study_type: StudyType, indicators: Dict[str, int]) -> float:
        """Calculate confidence score based on indicators"""
        
        if study_type == StudyType.NONE:
            return 0.0
        
        # Base confidence on relevant indicators
        if study_type == StudyType.EMPIRICAL_QUANTITATIVE:
            score = indicators['quantitative'] + (indicators['empirical'] * 0.5)
        elif study_type == StudyType.EMPIRICAL_QUALITATIVE:
            score = indicators['qualitative'] + (indicators['empirical'] * 0.5)
        elif study_type == StudyType.EMPIRICAL_MIXED:
            score = indicators['mixed'] + (indicators['quantitative'] * 0.5) + (indicators['qualitative'] * 0.5)
        elif study_type == StudyType.CASE_STUDY:
            score = indicators['case_study'] + (indicators['empirical'] * 0.3)
        else:
            score = 0
        
        # Normalize to 0-1 range
        confidence = min(score / 8.0, 1.0)
        
        return round(confidence, 2)


# Simple usage example
def classify_abstract(abstract: str) -> StudyType:
    """Simple function that just returns the study type"""
    classifier = EmpiricalResearchClassifier()
    result = classifier.classify(abstract)
    return result.study_type


# Testing
if __name__ == "__main__":
    classifier = EmpiricalResearchClassifier()
    
    test_cases = [
        ("We surveyed 250 developers and performed regression analysis with p<0.05...", 
         StudyType.EMPIRICAL_QUANTITATIVE),
        ("Through interviews with 20 participants and thematic analysis...", 
         StudyType.EMPIRICAL_QUALITATIVE),
        ("Using mixed methods, we surveyed 100 users and interviewed 15...", 
         StudyType.EMPIRICAL_MIXED),
        ("This case study examines three organizations implementing DevOps...", 
         StudyType.CASE_STUDY),
        ("This paper proposes a theoretical framework for understanding...", 
         StudyType.NONE)
    ]
    
    for abstract, expected in test_cases:
        result = classifier.classify(abstract)
        print(f"Expected: {expected.value if expected else None}")
        print(f"Got: {result.study_type.value if result.study_type else None}")
        print(f"Confidence: {result.confidence}")
        print(f"Key matches: {result.key_matches}")
        print("-" * 50)
```