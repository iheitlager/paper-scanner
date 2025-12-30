"""
Journal Lookup Helper - Load and query journal definitions.

Provides a JournalLookup class that loads journal definitions from YAML,
normalizes journal names, and returns journal metadata (name, acronym, ISO4).
"""
from pathlib import Path
from typing import Optional, Tuple
import yaml

from paper_scanner.core.iso4 import ISO4Generator


class JournalLookup:
    """Load and query journal definitions from YAML.
    
    Provides methods to:
    - Load journal definitions from YAML file
    - Normalize journal names for matching
    - Look up journal metadata by name
    - Return journal triplets (name, acronym, iso4)
    """

    def __init__(self, definitions_path: Optional[str] = None):
        """Initialize journal lookup.
        
        Args:
            definitions_path: Path to journal_definitions.yml
                            If None, uses etc/journal_definitions.yml relative to project root
        
        Raises:
            FileNotFoundError: If definitions file not found
        """
        self.iso4_gen = ISO4Generator()
        self.journals = {}
        self._load_definitions(definitions_path)

    def _load_definitions(self, definitions_path: Optional[str]) -> None:
        """Load journal definitions from YAML file.
        
        Args:
            definitions_path: Path to YAML file or None to use default
        
        Raises:
            FileNotFoundError: If file not found
            ValueError: If invalid journal definitions format
        """
        if definitions_path:
            path = Path(definitions_path)
        else:
            # Look for etc/journal_definitions.yml relative to project root
            current = Path(__file__)
            # Navigate up: journals.py → documents → tools → paper_scanner → src → project_root
            project_root = current.parent.parent.parent.parent.parent
            path = project_root / "etc" / "journal_definitions.yml"
        
        if not path.exists():
            raise FileNotFoundError(
                f"Journal definitions file not found at: {path}"
            )
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'journals' not in data:
                raise ValueError(
                    f"Invalid journal definitions format in {path}"
                )
            
            # Store journals by normalized name for fast lookup
            for journal_name, metadata in data['journals'].items():
                normalized_name = self._normalize(journal_name)
                self.journals[normalized_name] = {
                    'name': journal_name,
                    'acronym': metadata.get('acronym', ''),
                    'iso4': metadata.get('iso4', ''),
                }
        except yaml.YAMLError as e:
            raise ValueError(
                f"Error parsing journal definitions: {e}"
            )

    def lookup(self, journal_name: str) -> Tuple[str, str, str]:
        """Look up a journal by name.
        
        Args:
            journal_name: Journal name (case and whitespace insensitive)
        
        Returns:
            Tuple of (journal_name, acronym, iso4)
        
        Raises:
            ValueError: If journal not found in definitions
        """
        if not journal_name or not isinstance(journal_name, str):
            raise ValueError(f"Invalid journal name: {repr(journal_name)}")
        
        # Try exact match first
        normalized = self._normalize(journal_name)
        
        if normalized in self.journals:
            entry = self.journals[normalized]
            return (entry['name'], entry['acronym'], entry['iso4'])
        
        # Not found
        raise ValueError(
            f"Journal not found: '{journal_name}'. "
            f"Available journals: {len(self.journals)}"
        )

    def lookup_with_generation(self, journal_name: str) -> Tuple[str, str, str]:
        """Look up journal, generating ISO4 if needed.
        
        Attempts to find the journal in definitions first.
        If found, returns stored metadata.
        Falls back to ISO4 generation if needed (for partial matches).
        
        Args:
            journal_name: Journal name
        
        Returns:
            Tuple of (journal_name, acronym, iso4)
        
        Raises:
            ValueError: If not found in definitions
        """
        name, acronym, iso4 = self.lookup(journal_name)
        
        # If no ISO4 stored, generate it
        if not iso4:
            iso4 = self.iso4_gen.generate(name) or name
        
        return (name, acronym, iso4)

    def list_journals(self) -> list[str]:
        """Get list of all journal names in definitions.
        
        Returns:
            List of journal names
        """
        return [entry['name'] for entry in self.journals.values()]

    def get_journal_count(self) -> int:
        """Get number of journals in definitions.
        
        Returns:
            Number of journals loaded
        """
        return len(self.journals)

    @staticmethod
    def _normalize(journal_name: str) -> str:
        """Normalize journal name for matching.
        
        - Convert to lowercase
        - Strip whitespace
        - Collapse internal spaces
        
        Args:
            journal_name: Journal name to normalize
        
        Returns:
            Normalized name
        """
        if not journal_name:
            return ""
        return " ".join(journal_name.strip().lower().split())
