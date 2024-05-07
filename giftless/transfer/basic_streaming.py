"""Basic Streaming Transfer Adapter.

This transfer adapter offers 'basic' transfers by streaming uploads /
downloads through the Git LFS HTTP server. It can use different
storage backends (local, cloud, ...). This module defines an interface
through which additional streaming backends can be implemented.
"""

import posixpath
from typing import Any, BinaryIO, cast

import marshmallow
from flask import Flask, Response, current_app, request, url_for
from flask_classful import route
from webargs.flaskparser import parser

from giftless.auth.identity import Permission
from giftless.exc import InvalidPayload, NotFound
from giftless.schema import ObjectSchema
from giftless.storage import StreamingStorage, VerifiableStorage
from giftless.transfer import PreAuthorizingTransferAdapter
from giftless.util import add_query_params, get_callable, safe_filename
from giftless.view import BaseView, ViewProvider


class VerifyView(BaseView):
    """Verify an object.

    This view is actually not basic_streaming specific, and is used by other
    transfer adapters that need a 'verify' action as well.

    TODO @athornton: then how about we make it a mixin, which will
    make the test structures a little less weird?
    """

    route_base = "objects/storage"

    def __init__(self, storage: VerifiableStorage) -> None:
        self.storage = storage

    @route("/verify", methods=["POST"])
    def verify(self, organization: str, repo: str) -> Response:
        schema = ObjectSchema(unknown=marshmallow.EXCLUDE)
        payload = parser.parse(schema)

        self._check_authorization(
            organization, repo, Permission.READ_META, oid=payload["oid"]
        )

        prefix = posixpath.join(organization, repo)
        if not self.storage.verify_object(
            prefix, payload["oid"], payload["size"]
        ):
            raise InvalidPayload(
                "Object does not exist or size does not match"
            )
        return Response(status=200)

    @classmethod
    def get_verify_url(
        cls, organization: str, repo: str, oid: str | None = None
    ) -> str:
        """Get the URL for upload / download requests for this object."""
        # Use the legacy endpoint when enabled
        # see giftless.view.BaseView:register for details
        legacy = "Legacy" if current_app.config["LEGACY_ENDPOINTS"] else ""
        op_name = f"{legacy}{cls.__name__}:verify"
        url: str = url_for(
            op_name,
            organization=organization,
            repo=repo,
            oid=oid,
            _external=True,
        )
        return url


class ObjectsView(BaseView):
    """Provides methods for object storage management."""

    route_base = "objects/storage"

    def __init__(self, storage: StreamingStorage) -> None:
        self.storage = storage

    def put(self, organization: str, repo: str, oid: str) -> Response:
        """Upload a file to local storage.

        TODO @rufuspollock: For now, I am not sure this actually
        streams chunked uploads without reading the entire content
        into memory. It seems that in order to support this, we will
        need to dive deeper into the WSGI Server -> Werkzeug -> Flask
        stack, and it may also depend on specific WSGI server
        implementation and even how a proxy (e.g. nginx) is
        configured.
        """
        self._check_authorization(
            organization, repo, Permission.WRITE, oid=oid
        )
        stream = request.stream
        self.storage.put(
            prefix=f"{organization}/{repo}",
            oid=oid,
            data_stream=cast(BinaryIO, stream),
        )
        return Response(status=200)

    def get(self, organization: str, repo: str, oid: str) -> Response:
        """Get an open file stream from local storage."""
        self._check_authorization(organization, repo, Permission.READ, oid=oid)
        path = posixpath.join(organization, repo)

        filename = request.args.get("filename")
        filename = safe_filename(filename) if filename else None
        disposition = request.args.get("disposition")

        headers = {}
        if filename and disposition:
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        elif disposition:
            headers = {"Content-Disposition": disposition}

        if self.storage.exists(path, oid):
            file = self.storage.get(path, oid)
            mime_type = self.storage.get_mime_type(path, oid)
            headers["Content-Type"] = mime_type
            return Response(
                file, direct_passthrough=True, status=200, headers=headers
            )
        else:
            raise NotFound("The object was not found")

    @classmethod
    def get_storage_url(
        cls,
        operation: str,
        organization: str,
        repo: str,
        oid: str | None = None,
    ) -> str:
        """Get the URL for upload / download requests for this object."""
        # Use the legacy endpoint when enabled
        # see giftless.view.BaseView:register for details
        legacy = "Legacy" if current_app.config["LEGACY_ENDPOINTS"] else ""
        op_name = f"{legacy}{cls.__name__}:{operation}"
        url: str = url_for(
            op_name,
            organization=organization,
            repo=repo,
            oid=oid,
            _external=True,
        )
        return url


class BasicStreamingTransferAdapter(
    PreAuthorizingTransferAdapter, ViewProvider
):
    """Provides Streaming Transfers."""

    def __init__(
        self, storage: StreamingStorage, action_lifetime: int
    ) -> None:
        super().__init__()
        self.storage = storage
        self.action_lifetime = action_lifetime

    def upload(
        self,
        organization: str,
        repo: str,
        oid: str,
        size: int,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        response = {"oid": oid, "size": size}

        prefix = posixpath.join(organization, repo)
        if (
            not self.storage.exists(prefix, oid)
            or self.storage.get_size(prefix, oid) != size
        ):
            response["actions"] = {
                "upload": {
                    "href": ObjectsView.get_storage_url(
                        "put", organization, repo, oid
                    ),
                    "header": self._preauth_headers(
                        organization, repo, actions={"write"}, oid=oid
                    ),
                    "expires_in": self.action_lifetime,
                },
                "verify": {
                    "href": VerifyView.get_verify_url(organization, repo),
                    "header": self._preauth_headers(
                        organization,
                        repo,
                        actions={"verify"},
                        oid=oid,
                        lifetime=self.VERIFY_LIFETIME,
                    ),
                    "expires_in": self.VERIFY_LIFETIME,
                },
            }
            response["authenticated"] = self._provides_preauth

        return response

    def download(
        self,
        organization: str,
        repo: str,
        oid: str,
        size: int,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        response = {"oid": oid, "size": size}

        prefix = posixpath.join(organization, repo)
        if not self.storage.exists(prefix, oid):
            response["error"] = {
                "code": 404,
                "message": "Object does not exist",
            }

        elif self.storage.get_size(prefix, oid) != size:
            response["error"] = {
                "code": 422,
                "message": "Object size does not match",
            }

        else:
            download_url = ObjectsView.get_storage_url(
                "get", organization, repo, oid
            )
            preauth_url = self._preauth_url(
                download_url, organization, repo, actions={"read"}, oid=oid
            )

            if extra and "filename" in extra:
                params = {"filename": extra["filename"]}
                preauth_url = add_query_params(preauth_url, params)

            response["actions"] = {
                "download": {
                    "href": preauth_url,
                    "header": {},
                    "expires_in": self.action_lifetime,
                }
            }
            response["authenticated"] = self._provides_preauth

        return response

    def register_views(self, app: Flask) -> None:
        ObjectsView.register(app, init_argument=self.storage)
        VerifyView.register(app, init_argument=self.storage)


def factory(
    storage_class: Any, storage_options: Any, action_lifetime: int
) -> BasicStreamingTransferAdapter:
    """Build a basic transfer adapter with local storage."""
    storage = get_callable(storage_class, __name__)
    return BasicStreamingTransferAdapter(
        storage(**storage_options), action_lifetime
    )
