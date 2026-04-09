"""Base API class with common functionality"""

import requests
import requests.adapters
import threading
from abc import ABC, abstractmethod
from typing import Any
from obsidianki.cli.config import console

_original_send = requests.adapters.HTTPAdapter.send


def _interruptible_send(self, request, **kwargs):
    """Wrap HTTPAdapter.send in a daemon thread so Ctrl+C works during blocking I/O."""
    result = [None]
    exc = [None]

    def _do():
        try:
            result[0] = _original_send(self, request, **kwargs)
        except BaseException as e:
            exc[0] = e

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    while t.is_alive():
        t.join(0.1)
    if exc[0] is not None:
        raise exc[0]
    return result[0]


requests.adapters.HTTPAdapter.send = _interruptible_send  # type: ignore[assignment]


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