# API JSON Response Format Analysis

## BibTeX Target Format
```bibtex
@article{10.1186/s13731-024-00404-5,
  abstract = {Digital transformation is a pivotal strategic pillar...},
  author = {Hoessler, Sabrina and Carbon, Claus-Christian},
  doi = {10.1186/s13731-024-00404-5},
  journal = {Journal of Innovation and Entrepreneurship},
  number = {1},
  publisher = {Springer Science and Business Media LLC},
  title = {Digital transformation in incumbent companies: a qualitative study on exploration and exploitation activities in innovation},
  url = {https://doi.org/10.1186/s13731-024-00404-5},
  volume = {13},
  year = {2024}
}
```

## API Mapping

### 1. DOI (Citation Key)
| API | Field Path | Value |
|-----|-----------|-------|
| **Crossref** | `DOI` | `10.1186/s13731-024-00404-5` |
| **OpenAlex** | `doi` (remove `https://doi.org/` prefix) | `https://doi.org/10.1186/s13731-024-00404-5` → `10.1186/s13731-024-00404-5` |
| **CORE** | `doi` | `10.1186/s13731-024-00404-5` |
| **Semantic Scholar** | `externalIds.DOI` | `10.1186/s13731-024-00404-5` |
| **Unpaywall** | `doi` | `10.1186/s13731-024-00404-5` |
| **IEEE Xplore** | `doi` | TBD (API not tested) |

### 2. Title
| API | Field Path |
|-----|-----------|
| **Crossref** | `title` (array, take first) |
| **OpenAlex** | `title` |
| **CORE** | `title` |
| **Semantic Scholar** | `title` |
| **Unpaywall** | `title` |

### 3. Authors
| API | Field Path | Format |
|-----|-----------|--------|
| **Crossref** | `author[].{given, family}` | Concatenate: `family, given` |
| **OpenAlex** | `authorships[].author.display_name` | Direct name |
| **CORE** | `authors[].name` | Direct name (may need parsing) |
| **Semantic Scholar** | `authors[].name` | Direct name (abbreviated, e.g., "S. Hoessler") |
| **Unpaywall** | NOT PROVIDED | Must get from another source |

### 4. Publication Year
| API | Field Path |
|-----|-----------|
| **Crossref** | `issued.date-parts[0][0]` |
| **OpenAlex** | `publication_year` |
| **CORE** | `yearPublished` or `publishedDate` |
| **Semantic Scholar** | `year` |
| **Unpaywall** | `year` |

### 5. Journal/Source
| API | Field Path |
|-----|-----------|
| **Crossref** | `container-title` (array, take first) |
| **OpenAlex** | `primary_location.source.display_name` |
| **CORE** | `journals[0].title` |
| **Semantic Scholar** | NOT PROVIDED (in standard response) |
| **Unpaywall** | `journal_name` |

### 6. Volume
| API | Field Path |
|-----|-----------|
| **Crossref** | `volume` |
| **OpenAlex** | `biblio.volume` |
| **CORE** | `journals[0].volume` |
| **Semantic Scholar** | NOT PROVIDED |
| **Unpaywall** | NOT PROVIDED |

### 7. Issue/Number
| API | Field Path |
|-----|-----------|
| **Crossref** | `issue` |
| **OpenAlex** | `biblio.issue` |
| **CORE** | `journals[0].issue` |
| **Semantic Scholar** | NOT PROVIDED |
| **Unpaywall** | NOT PROVIDED |

### 8. Publisher
| API | Field Path |
|-----|-----------|
| **Crossref** | `publisher` |
| **OpenAlex** | `primary_location.source.host_organization_name` |
| **CORE** | `publisher` |
| **Semantic Scholar** | NOT PROVIDED |
| **Unpaywall** | `publisher` |

### 9. Abstract
| API | Field Path | Notes |
|-----|-----------|-------|
| **Crossref** | `abstract` | HTML/XML tags present, needs cleaning |
| **OpenAlex** | `abstract` | Usually null |
| **CORE** | `abstract` | Plain text |
| **Semantic Scholar** | `abstract` | Usually null (publisher blocks) |
| **Unpaywall** | NOT PROVIDED | Must get from Crossref/CORE |

### 10. URL
| API | Field Path |
|-----|-----------|
| **Crossref** | Build from DOI: `https://doi.org/{DOI}` |
| **OpenAlex** | `primary_location.landing_page_url` |
| **CORE** | `downloadUrl` |
| **Semantic Scholar** | Build from DOI |
| **Unpaywall** | `best_oa_location.url` or `doi_url` |

### 11. Open Access Status
| API | Field Path |
|-----|-----------|
| **Crossref** | Check `license[0].URL` |
| **OpenAlex** | `open_access.is_oa` |
| **CORE** | Assumed (in CORE) |
| **Semantic Scholar** | `isOpenAccess` |
| **Unpaywall** | `is_oa` and `oa_status` |

## Commonalities & Conflicts

### Strong Fields (Available in Most APIs)
- ✅ **DOI** - Present in all APIs (format varies)
- ✅ **Title** - Present in all APIs
- ✅ **Year/Publication Year** - Present in all APIs
- ✅ **Publisher** - Present in most (absent in Semantic Scholar)
- ✅ **Journal Name** - Present in most

### Medium-Strength Fields (Available in Some APIs)
- ⚠️ **Authors** - Present in all but Unpaywall
  - Problem: Different formats (full name vs abbreviated, different orders)
  - Solution: Crossref provides structured `given`/`family` names
  
- ⚠️ **Abstract** - Present in Crossref, CORE, sometimes OpenAlex
  - Problem: Semantic Scholar and Unpaywall often null
  - Solution: Prefer Crossref or CORE
  
- ⚠️ **Volume/Issue** - Present in Crossref, OpenAlex, CORE
  - Problem: Semantic Scholar and Unpaywall don't provide these
  - Solution: Make optional

### Weak Fields (Rarely Available)
- ❌ **DOI Landing URL** - Available in most but constructed needed
- ❌ **License/Open Access Info** - Variable across APIs

### 11. Keywords/Topics
| API | Field Path | Quality | Format |
|-----|-----------|---------|--------|
| **OpenAlex** | `keywords[].display_name` | ⭐⭐⭐⭐⭐ Excellent | Array of scored keywords |
| **OpenAlex** | `topics[].display_name` | ⭐⭐⭐⭐⭐ Excellent | Array of topics with hierarchy |
| **Crossref** | `subject[]` | ⭐⭐ Poor | Empty for this paper |
| **CORE** | `fieldOfStudy` | ❌ Not provided | Null |
| **Semantic Scholar** | `fieldsOfStudy` | ❌ Not provided | Null |
| **Unpaywall** | NOT PROVIDED | ❌ Not provided | - |
| **IEEE Xplore** | TBD | TBD | - |

**OpenAlex Example:**
```json
"keywords": [
  {"display_name": "Entrepreneurship", "score": 0.75},
  {"display_name": "Business", "score": 0.66},
  {"display_name": "Digital transformation", "score": 0.62}
],
"topics": [
  {"display_name": "Innovation and Knowledge Management", "score": 0.98},
  {"display_name": "Big Data and Business Intelligence", "score": 0.97},
  {"display_name": "Digital Transformation in Industry", "score": 0.96}
]
```

## Recommendation for Keywords
**OpenAlex is the best source** for keywords and topics:
- Provides both `keywords` (specific terms) and `topics` (broader categories)
- Includes confidence scores (0-1) for relevance
- Topics have hierarchical structure (domain → field → subfield)
- Rich semantic information for research categorization

1. **Primary**: Crossref (most complete metadata)
2. **Fallback**: OpenAlex (good structured data)
3. **Fallback**: CORE (good for OA content)
4. **Fallback**: Unpaywall (OA availability info)
5. **Last resort**: Semantic Scholar (limited metadata)

## Data Quality Issues

| API | Issue | Solution |
|-----|-------|----------|
| **Crossref** | Abstract has HTML/XML tags | Parse/strip tags |
| **OpenAlex** | Abstract often null | Use Crossref abstract |
| **Semantic Scholar** | Abstract often blocked by publisher | Use Crossref abstract |
| **All** | Author name normalization | Parse to Last, First format |
| **Semantic Scholar** | Abbreviated author names | Cannot expand reliably |

