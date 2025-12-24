# Introduction
This spike is al about completing the citations. At this moment we have 3 handlers crossref, openalex and semanticscholar. The interface structure is sound and solid with two calls and a data structure, but it is too buggy. We are first going to add a fourth handler: manual. Second we are going to improve the processing through these four handlers, this includes a better caching and handling for 404 not found. Third we are going to implement cache invalidation, if last reference (can be set in the citation step, default 30 days) it is going to reconsider the source. This is to improve forward ciations.

Based on previous spike we came to the conclusion that having structured text is improving results tremendously and we need that automated review for a snowballing stepm which becomes otherwise too extensive to process.


## Manual Handler
A fourth handler to cache locally what we already know. In the end it is all about completing our study. Not to have a perfect automatic downloader.

- This is just a new handler. There will not be any downloading, just checking the cache and return what (both metadata, forward and backward citations) we have cached locally. 
- So all API calls should be disable.
- To make sure the cache is loaded. It is taking a bibtex, load it into the Papers/Citation model and secure it in the cache under `manual`
- A cli step `paper-processor cache load manual <file.bib>` is performing that loading
- A cli step `paper-processor cache clear manual` is removing all files (we just keep the bibtex)
- both steps `retrieve_metadata` and `citations` will be extended with this manual handler


### Bibtex file
We are going to use the following fields to capture citations based on DOI

```bibtex
@article{Smith2023,
  author = {Smith, John},
  title = {Example Paper},
  year = {2023},
  doi = {10.1234/example},
  abstract = {...},
  keywords = {..., ..., ...},
  
  % Custom fields for citation tracking
  cites = {10.1234/ref1, 10.1234/ref2, 10.1234/ref3},
  citedby = {10.1234/citing1, 10.1234/citing2},
  citedbycount = {15},
  lastchecked = {2024-12-24},

  % Study classification
  studytype = {empirical_case_study, empirical_qualitative}
}
```

the bibtex entry type is translated to papertype. This way we can make a overview. The PDF coupling will be done separately. Otherwise it becomes to complex.

# caching of non found entries - this is already implemented
We are going to improve the handlers with the mechanisms to also capture nonfound (404) entries. This will increase speed and reduce API calls further. If an API receives a 404, a dummy json like `{"ITEM" : "404 - NOT FOUND", "LAST-CHECKED": "YYYY-MM-DD", "URL": "...."}` will be created. During fetching if an cache hit is found, the handler will first check the `"ITEM": "404 - NOT FOUND"` and return empty, other wise it will return the cached item. I think this is generic, so we can extend fetcher by default. No need to improve every single handler. Note that the manual handler does not need this (since there are no API calls, the purpose of this not found caching, reduce load even further). No cache found is just returning None

# Cache invalidation - this is already inplemented
extend the JSONCache with expiration (ttl_days setting and ttl in get call). This will invalidate the cache entry after TTL, regular logic will download the item and store it again.

```python
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Union
import json

class Cache:
    def __init__(self, cache_dir: Path, default_ttl: Union[int, timedelta] = 30):
        """
        Initialize cache with configurable expiration.
        
        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live (int = days, timedelta = custom duration)
        """
        self.cache_dir = cache_dir
        self.default_ttl = timedelta(days=default_ttl) if isinstance(default_ttl, int) else default_ttl
        
    def get(self, key: str, ttl: Optional[Union[int, timedelta]] = None) -> Optional[Dict[str, Any]]:
        """
        Load cached value if it exists and hasn't exceeded its time-to-live.
        
        Args:
            key: The key to look up (e.g., DOI)
            ttl: Time-to-live (int = days, timedelta = custom duration, 0 = never expire, None = use default)
            
        Returns:
            Cached JSON data if found and not expired, None otherwise
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        # Convert ttl to timedelta
        if ttl == -1 # Never expire
            ttl_delta = None 
        elif ttl is None: # Take default
            ttl_delta = self.default_ttl
        else: # take what we got or transform into days
            ttl_delta = timedelta(days=ttl) if isinstance(ttl, int) else ttl

        # Check expiration only if ttl_delta is positive
        if ttl_delta and ttl_delta.total_seconds() > 0:
            file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if file_age > ttl_delta:
                cache_path.unlink()
                return None
        
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise CacheError(f"Error loading cache for {key}: {e}")
```