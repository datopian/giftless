"""Miscellanea
"""
import importlib
from typing import Callable, Optional


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

    return getattr(module, callable_name)
