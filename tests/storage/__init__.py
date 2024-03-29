import io
from abc import ABC
from typing import Any, cast

import pytest

from giftless.storage import ExternalStorage, StreamingStorage
from giftless.storage.exc import ObjectNotFoundError

ARBITRARY_OID = (
    "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
)

# The layering is bad in giftless.storage, leading to some strange choices
# for storage classes here.  That should be refactored sometime.


class _CommonStorageAbstractTests(ABC):  # noqa: B024
    """Common tests for all storage backend types and interfaces."""

    def test_get_size(self, storage_backend: StreamingStorage) -> None:
        """Test getting the size of a stored object."""
        content = b"The contents of a file-like object"
        storage_backend.put("org/repo", ARBITRARY_OID, io.BytesIO(content))
        assert len(content) == storage_backend.get_size(
            "org/repo", ARBITRARY_OID
        )

    def test_get_size_not_existing(
        self, storage_backend: StreamingStorage
    ) -> None:
        """Test getting the size of a non-existing object raises an
        exception.
        """
        with pytest.raises(ObjectNotFoundError):
            storage_backend.get_size("org/repo", ARBITRARY_OID)

    def test_exists_exists(self, storage_backend: StreamingStorage) -> None:
        """Test that calling exists on an existing object returns True."""
        content = b"The contents of a file-like object"
        storage_backend.put("org/repo", ARBITRARY_OID, io.BytesIO(content))
        assert storage_backend.exists("org/repo", ARBITRARY_OID)

    def test_exists_not_exists(
        self, storage_backend: StreamingStorage
    ) -> None:
        """Test that calling exists on a non-existing object returns False."""
        assert not storage_backend.exists("org/repo", ARBITRARY_OID)


class _VerifiableStorageAbstractTests(ABC):  # noqa: B024
    """Mixin class for other base storage adapter test classes that implement
    VerifiableStorage.
    """

    def test_verify_object_ok(self, storage_backend: StreamingStorage) -> None:
        content = b"The contents of a file-like object"
        # put is part of StreamingStorage, not VerifiableStorage...but
        # StreamingStorage implements VerifiableStorage
        storage_backend.put("org/repo", ARBITRARY_OID, io.BytesIO(content))
        assert storage_backend.verify_object(
            "org/repo", ARBITRARY_OID, len(content)
        )

    def test_verify_object_wrong_size(
        self, storage_backend: StreamingStorage
    ) -> None:
        content = b"The contents of a file-like object"
        storage_backend.put("org/repo", ARBITRARY_OID, io.BytesIO(content))
        assert not storage_backend.verify_object(
            "org/repo", ARBITRARY_OID, len(content) + 2
        )

    def test_verify_object_not_there(
        self, storage_backend: StreamingStorage
    ) -> None:
        assert not storage_backend.verify_object("org/repo", ARBITRARY_OID, 0)


class StreamingStorageAbstractTests(
    _CommonStorageAbstractTests, _VerifiableStorageAbstractTests, ABC
):
    """Mixin for testing the StreamingStorage methods of a backend
    that implements StreamingStorage.

    To use, create a concrete test class mixing this class in, and
    define a fixture named ``storage_backend`` that returns an
    appropriate storage backend object.
    """

    def test_put_get_object(self, storage_backend: StreamingStorage) -> None:
        """Test a full put-then-get cycle."""
        content = b"The contents of a file-like object"
        written = storage_backend.put(
            "org/repo", ARBITRARY_OID, io.BytesIO(content)
        )

        assert len(content) == written

        fetched = storage_backend.get("org/repo", ARBITRARY_OID)
        fetched_content = b"".join(fetched)
        assert content == fetched_content

    def test_get_raises_if_not_found(
        self, storage_backend: StreamingStorage
    ) -> None:
        """Test that calling get for a non-existing object raises."""
        with pytest.raises(ObjectNotFoundError):
            storage_backend.get("org/repo", ARBITRARY_OID)


class ExternalStorageAbstractTests(
    _CommonStorageAbstractTests, _VerifiableStorageAbstractTests
):
    """Mixin for testing the ExternalStorage methods of a backend that
    implements ExternalStorage.

    To use, create a concrete test class mixing this class in, and
    define a fixture named ``storage_backend`` that returns an
    appropriate storage backend object.


    Again, perhaps this should be defined as an ABC?
    """

    def test_get_upload_action(self, storage_backend: ExternalStorage) -> None:
        action_spec = storage_backend.get_upload_action(
            "org/repo", ARBITRARY_OID, 100, 3600
        )
        upload = cast(dict[str, Any], action_spec["actions"]["upload"])
        assert upload["href"][0:4] == "http"
        assert upload["expires_in"] == 3600

    def test_get_download_action(
        self, storage_backend: ExternalStorage
    ) -> None:
        action_spec = storage_backend.get_download_action(
            "org/repo", ARBITRARY_OID, 100, 7200
        )
        download = cast(dict[str, Any], action_spec["actions"]["download"])
        assert download["href"][0:4] == "http"
        assert download["expires_in"] == 7200
