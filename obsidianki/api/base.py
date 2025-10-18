"""Base API class with common functionality"""

import requests
from abc import ABC, abstractmethod
from typing import Any
from obsidianki.cli.config import console


class BaseAPI(ABC):
    """Base class for API clients with common error handling and request logic"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.headers = {}

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with common error handling"""
        try:
            kwargs.setdefault('timeout', self.timeout)
            kwargs.setdefault('headers', self.headers)

            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            raise

    def _parse_response(self, response: requests.Response, default: Any = None) -> Any:
        """Parse response with fallback handling"""
        try:
            return response.json()
        except ValueError:
            return response.text if default is None else default

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the API connection is working"""
        pass