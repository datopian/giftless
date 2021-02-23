"""Miscellanea
"""
import importlib
from typing import Any, Callable, Dict, Iterable, Optional
from urllib.parse import urlencode


def get_callable(callable_str: str, base_package: Optional[str] = None) -> Callable:
    """Get a callable function / class constructor from a string of the form
    `package.subpackage.module:callable`

    >>> type(get_callable('os.path:basename')).__name__
    'function'

    >>> type(get_callable('basename', 'os.path')).__name__
    'function'
    """
    if ':' in callable_str:
        module_name, callable_name = callable_str.split(':', 1)
        module = importlib.import_module(module_name, base_package)
    elif base_package:
        module = importlib.import_module(base_package)
        callable_name = callable_str
    else:
        raise ValueError("Expecting base_package to be set if only class name is provided")

    return getattr(module, callable_name)  # type: ignore


def to_iterable(val: Any) -> Iterable:
    """Get something we can iterate over from an unknown type

    >>> i = to_iterable([1, 2, 3])
    >>> next(iter(i))
    1

    >>> i = to_iterable(1)
    >>> next(iter(i))
    1

    >>> i = to_iterable(None)
    >>> next(iter(i)) is None
    True

    >>> i = to_iterable('foobar')
    >>> next(iter(i))
    'foobar'

    >>> i = to_iterable((1, 2, 3))
    >>> next(iter(i))
    1
    """
    if isinstance(val, Iterable) and not isinstance(val, (str, bytes)):
        return val
    return (val,)


def add_query_params(url: str, params: Dict[str, Any]) -> str:
    """Safely add query params to a url that may or may not already contain
    query params.

    >>> add_query_params('https://example.org', {'param1': 'value1', 'param2': 'value2'})
    'https://example.org?param1=value1&param2=value2'

    >>> add_query_params('https://example.org?param1=value1', {'param2': 'value2'})
    'https://example.org?param1=value1&param2=value2'
    """
    urlencoded_params = urlencode(params)
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}{urlencoded_params}'


def safe_filename(original_filename: str) -> str:
    """Returns a filename safe to use in HTTP headers, formed from the
    given original filename.

    >>> safe_filename("example(1).txt")
    'example1.txt'

    >>> safe_filename("_ex@mple 2%.old.xlsx")
    '_exmple2.old.xlsx'
    """
    valid_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.'
    return ''.join(c for c in original_filename if c in valid_chars)
