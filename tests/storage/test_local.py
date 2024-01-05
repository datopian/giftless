"""Tests for the local storage backend."""
import shutil
from collections.abc import Generator
from pathlib import Path

import pytest

from giftless.storage.local_storage import LocalStorage

from . import StreamingStorageAbstractTests


@pytest.fixture
def storage_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a unique temp dir for testing storage."""
    tdir = None
    try:
        tdir = tmp_path / "giftless_tests"
        tdir.mkdir(parents=True)
        yield tdir
    finally:
        if tdir and tdir.is_dir():
            shutil.rmtree(tdir)


@pytest.fixture
def storage_backend(storage_dir: str) -> LocalStorage:
    """Provide a local storage backend for all local tests."""
    return LocalStorage(path=storage_dir)


class TestLocalStorageBackend(StreamingStorageAbstractTests):
    def test_local_path_created_on_init(self, storage_dir: Path) -> None:
        """Test that the local storage path is created on module init."""
        storage_path = storage_dir / "here"
        assert not storage_path.exists()
        LocalStorage(path=str(storage_path))
        assert storage_path.exists()
