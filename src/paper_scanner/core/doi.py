import hashlib
import re


class DOI:
    """
    DOI class that normalizes and provides multiple representations.
    
    Accepts any DOI format in __init__ and normalizes to stem (core DOI without prefix/URL).
    Provides methods to get URL, prefix, safe filename format, and string representations.

    More information here: https://en.wikipedia.org/wiki/Digital_object_identifier
    Or see the DOI Handbook: https://doi.org/10.1000/182
    """

    def __init__(self, doi: str):
        """
        Initialize DOI with any format and normalize to stem.
        
        Args:
            doi: DOI string in any format (URL, doi:, doi., or raw stem)
        """
        if doi is None or not doi.strip():
            raise ValueError("DOI cannot be empty or None")
        self.stem = self._normalize_to_stem(doi)


    def _normalize_to_stem(self, doi: str) -> str:
        """
        Normalize any DOI format to stem (core DOI without prefix/URL).
        
        Validates DOI structure:
        - Must contain exactly one "/" separating prefix and suffix
        - Prefix must start with "10."
        - Both prefix and suffix must be non-empty
        
        Args:
            doi: DOI in any format
            
        Returns:
            Normalized DOI stem (e.g., "10.1234/example")
            
        Raises:
            ValueError: If DOI format is invalid
        """
        normalized = doi.strip().lower()

        # Remove URL prefixes
        if normalized.startswith("https://doi.org/"):
            normalized = normalized[len("https://doi.org/"):]
        elif normalized.startswith("http://doi.org/"):
            normalized = normalized[len("http://doi.org/"):]
        elif normalized.startswith("doi:"):
            normalized = normalized[len("doi:"):]
        elif normalized.startswith("doi."):
            normalized = normalized[len("doi."):]

        # Validate prefix/suffix structure
        if "/" not in normalized:
            raise ValueError(f"Invalid DOI format: '{doi}' - must contain prefix/suffix separated by '/'")

        parts = normalized.split("/", 1)  # Split on first "/" only
        self.prefix, self.suffix = parts[0], parts[1]

        # Validate both prefix and suffix are non-empty
        if not self.prefix or not self.suffix:
            raise ValueError(f"Invalid DOI format: '{doi}' - prefix and suffix cannot be empty")

        # Validate prefix starts with "10."
        if not self.prefix.startswith("10."):
            raise ValueError(f"Invalid DOI prefix: '{self.prefix}' - must start with '10.'")

        return normalized

    @property
    def url(self) -> str:
        """Get DOI as URL format."""
        return f"https://doi.org/{self.prefix}/{self.suffix}"

    @property
    def uri(self, delimiter: str = ":") -> str:
        """Get DOI with prefix format (default: doi:)."""
        return f"doi{delimiter}{self.prefix}/{self.suffix}"

    @property
    def safe(self) -> str:
        """Get DOI in filename-safe format (replace /.: with _)."""
        return re.sub(r'[/.:()]+', '_', self.stem)

    @property
    def md5(self) -> str:
        """Get MD5 hash of the normalized DOI stem."""
        return hashlib.md5(self.stem.encode()).hexdigest()

    def __str__(self) -> str:
        """Return the normalized DOI stem."""
        return self.stem

    def __repr__(self) -> str:
        """Return string representation."""
        return f"DOI({self.stem!r})"


