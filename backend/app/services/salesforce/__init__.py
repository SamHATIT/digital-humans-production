"""
Salesforce Services Module
- MetadataFetcher: Fetch metadata via Tooling API
- MetadataPreprocessor: Analyze and summarize for LLM
- Marcus AS-IS V2: Optimized As-Is analysis pipeline
"""

from .metadata_fetcher import MetadataFetcher, SalesforceCredentials, FetchResult
from .metadata_preprocessor import MetadataPreprocessor, RedFlag, Severity, RedFlagType
from .marcus_as_is_v2 import fetch_and_preprocess_metadata, get_as_is_prompt_v2

__all__ = [
    # Fetcher
    "MetadataFetcher",
    "SalesforceCredentials",
    "FetchResult",
    # Preprocessor
    "MetadataPreprocessor",
    "RedFlag",
    "Severity", 
    "RedFlagType",
    # Marcus V2
    "fetch_and_preprocess_metadata",
    "get_as_is_prompt_v2"
]
