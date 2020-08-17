"""Tests for the local storage backend
"""
import os
import pathlib
import shutil
from typing import Generator

import pytest

from giftless.storage.local_storage import LocalStorage

from . import StreamingStorageAbstractTests


@pytest.fixture()
def storage_dir(tmp_path) -> Generator[pathlib.Path, None, None]:
    """Create a unique temp dir for testing storage
    """
    dir = None
    try:
        dir = tmp_path / 'giftless_tests'
        dir.mkdir(parents=True)
        yield dir
    finally:
        if dir and os.path.isdir(dir):
            shutil.rmtree(dir)


@pytest.fixture()
def storage_backend(storage_dir) -> LocalStorage:
    """Provide a local storage backend for all local tests"""
    return LocalStorage(path=storage_dir)


class TestLocalStorageBackend(StreamingStorageAbstractTests):

    def test_local_path_created_on_init(self, storage_dir: pathlib.Path):
        """Test that the local storage path is created on module init
        """
        storage_path = str(storage_dir / 'here')
        assert not os.path.exists(storage_path)
        LocalStorage(path=storage_path)
        assert os.path.exists(storage_path)
