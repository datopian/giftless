"""Basic Streaming Transfer Adapter

This transfer adapter offers 'basic' transfers by streaming uploads / downloads
through the Git LFS HTTP server. It can use different storage backends (local,
cloud, ...). This module implements the local storage backend, but defines an
interface through which additional streaming backends can be implemented.
"""

import os
import shutil
from abc import ABC
from typing import Any, BinaryIO, Dict, Optional

from flask import Response, request, url_for
from flask_classful import route
from webargs.flaskparser import parser  # type: ignore

from giftless.auth.identity import Permission
from giftless.exc import InvalidPayload, NotFound
from giftless.schema import ObjectSchema
from giftless.transfer import PreAuthorizingTransferAdapter, ViewProvider, exc
from giftless.util import get_callable
from giftless.view import BaseView


class VerifiableStorage(ABC):
    """A storage backend that supports object verification API

    All streaming backends should be 'verifiable'.
    """
    def verify_object(self, prefix: str, oid: str, size: int) -> bool:
        """Check that object exists and has the right size

        This method should not throw an error if the object does not exist, but return False
        """
        pass


class StreamingStorage(VerifiableStorage, ABC):
    """Interface for streaming storage adapters
    """
    def get(self, prefix: str, oid: str) -> BinaryIO:
        pass

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        pass

    def exists(self, prefix: str, oid: str) -> bool:
        pass

    def get_size(self, prefix: str, oid: str) -> int:
        pass

    def verify_object(self, prefix: str, oid: str, size: int):
        """Verify that an object exists
        """
        try:
            return self.get_size(prefix, oid) == size
        except exc.ObjectNotFound:
            return False


class LocalStorage(StreamingStorage):
    """Local storage implementation

    # TODO: do we need directory hashing?
    #       seems to me that in a single org/repo prefix this is not needed as we do not expect
    #       thousands of files per repo or thousands or repos per org
    """
    def __init__(self, path: str = None, **_):
        if path is None:
            path = 'lfs-storage'
        self.path = path
        self._create_path(self.path)

    def get(self, prefix: str, oid: str) -> BinaryIO:
        path = self._get_path(prefix, oid)
        if os.path.isfile(path):
            return open(path, 'br')
        else:
            raise NotFound("Requested object was not found")

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        path = self._get_path(prefix, oid)
        directory = os.path.dirname(path)
        self._create_path(directory)
        with open(path, 'bw') as dest:
            shutil.copyfileobj(data_stream, dest)
            return dest.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        return os.path.isfile(self._get_path(prefix, oid))

    def get_size(self, prefix: str, oid: str) -> int:
        if self.exists(prefix, oid):
            return os.path.getsize(self._get_path(prefix, oid))
        return 0

    def _get_path(self, prefix: str, oid: str) -> str:
        return os.path.join(self.path, prefix, oid)

    @staticmethod
    def _create_path(path):
        if not os.path.isdir(path):
            os.makedirs(path)


class VerifyView(BaseView):
    """Verify an object

    This view is actually not basic_streaming specific, and is used by other
    transfer adapters that need a 'verify' action as well.
    """

    route_base = '<organization>/<repo>/objects/storage'

    def __init__(self, storage: VerifiableStorage):
        self.storage = storage

    @route('/verify', methods=['POST'])
    def verify(self, organization, repo):
        schema = ObjectSchema()
        payload = parser.parse(schema)

        self._check_authorization(organization, repo, Permission.READ_META, oid=payload['oid'])

        prefix = os.path.join(organization, repo)
        if not self.storage.verify_object(prefix, payload['oid'], payload['size']):
            raise InvalidPayload("Object does not exist or size does not match")
        return Response(status=200)

    @classmethod
    def get_verify_url(cls, organization: str, repo: str, oid: Optional[str] = None) -> str:
        """Get the URL for upload / download requests for this object
        """
        op_name = f'{cls.__name__}:verify'
        url: str = url_for(op_name, organization=organization, repo=repo, oid=oid, _external=True)
        return url


class ObjectsView(BaseView):

    route_base = '<organization>/<repo>/objects/storage'

    def __init__(self, storage: StreamingStorage):
        self.storage = storage

    def put(self, organization, repo, oid):
        """Upload a file to local storage

        For now, I am not sure this actually streams chunked uploads without reading the entire
        content into memory. It seems that in order to support this, we will need to dive deeper
        into the WSGI Server -> Werkzeug -> Flask stack, and it may also depend on specific WSGI
        server implementation and even how a proxy (e.g. nginx) is configured.
        """
        self._check_authorization(organization, repo, Permission.WRITE, oid=oid)
        stream = request.stream
        self.storage.put(prefix=f'{organization}/{repo}', oid=oid, data_stream=stream)
        return Response(status=200)

    def get(self, organization, repo, oid):
        """Get an file open file stream from local storage
        """
        self._check_authorization(organization, repo, Permission.READ, oid=oid)
        path = os.path.join(organization, repo)
        if self.storage.exists(path, oid):
            file = self.storage.get(path, oid)
            return Response(file, direct_passthrough=True, status=200)
        else:
            raise NotFound("The object was not found")

    @classmethod
    def get_storage_url(cls, operation: str, organization: str, repo: str, oid: Optional[str] = None) -> str:
        """Get the URL for upload / download requests for this object
        """
        op_name = f'{cls.__name__}:{operation}'
        url: str = url_for(op_name, organization=organization, repo=repo, oid=oid, _external=True)
        return url


class BasicStreamingTransferAdapter(PreAuthorizingTransferAdapter, ViewProvider):

    def __init__(self, storage: StreamingStorage, action_lifetime: int):
        self.storage = storage
        self.action_lifetime = action_lifetime

    def upload(self, organization: str, repo: str, oid: str, size: int, extra: Optional[Dict[str, Any]] = None) -> Dict:
        response = {"oid": oid,
                    "size": size}

        prefix = os.path.join(organization, repo)
        if not self.storage.exists(prefix, oid) or self.storage.get_size(prefix, oid) != size:
            response['actions'] = {
                "upload": {
                    "href": ObjectsView.get_storage_url('put', organization, repo, oid),
                    "header": self._preauth_headers(organization, repo, actions={'write'}, oid=oid),
                    "expires_in": self.action_lifetime
                },
                "verify": {
                    "href": VerifyView.get_verify_url(organization, repo),
                    "header": self._preauth_headers(organization, repo, actions={'verify'}, oid=oid,
                                                    lifetime=self.VERIFY_LIFETIME),
                    "expires_in": self.VERIFY_LIFETIME
                }
            }
            response['authenticated'] = True

        return response

    def download(self, organization: str, repo: str, oid: str, size: int,
                 extra: Optional[Dict[str, Any]] = None) -> Dict:
        response = {"oid": oid,
                    "size": size}

        prefix = os.path.join(organization, repo)
        if not self.storage.exists(prefix, oid):
            response['error'] = {
                "code": 404,
                "message": "Object does not exist"
            }

        elif self.storage.get_size(prefix, oid) != size:
            response['error'] = {
                "code": 422,
                "message": "Object size does not match"
            }

        else:
            response['actions'] = {
                "download": {
                    "href": ObjectsView.get_storage_url('get', organization, repo, oid),
                    "header": self._preauth_headers(organization, repo, actions={'read'}, oid=oid),
                    "expires_in": self.action_lifetime
                }
            }
            response['authenticated'] = True

        return response

    def register_views(self, app):
        ObjectsView.register(app, init_argument=self.storage)
        VerifyView.register(app, init_argument=self.storage)


def factory(storage_class, storage_options, action_lifetime):
    """Factory for basic transfer adapter with local storage
    """
    storage = get_callable(storage_class, __name__)
    return BasicStreamingTransferAdapter(storage(**storage_options), action_lifetime)
