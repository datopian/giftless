"""Flask-Classful View Classes."""
from typing import Any, ClassVar, cast

from flask import Flask
from flask_classful import FlaskView
from webargs.flaskparser import parser

from giftless import exc, representation, schema, transfer
from giftless.auth import authentication as authn
from giftless.auth.identity import Permission


class BaseView(FlaskView):
    """Extends Flask-Classful's base view class to add some common
    custom functionality.
    """

    decorators: ClassVar = [authn.login_required]

    representations: ClassVar = {
        "application/json": representation.output_json,
        representation.GIT_LFS_MIME_TYPE: representation.output_git_lfs_json,
        "flask-classful/default": representation.output_git_lfs_json,
    }

    route_prefix: ClassVar = "<path:organization>/<repo>.git/info/lfs/"
    # [flask-classful bug/feat?] Placeholders in route_prefix not skipped for
    # building the final rule for methods with them (FlaskView.build_rule).
    base_args: ClassVar = ["organization", "repo"]

    trailing_slash = False

    @classmethod
    def register(cls, app: Flask, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("base_class") is None:
            kwargs["base_class"] = BaseView
        if (
            app.config["LEGACY_ENDPOINTS"]
            and kwargs.get("route_prefix") is None
            and not hasattr(cls, "_legacy_")  # break the cycle
        ):
            # To span any transition required for the switch to the current
            # endpoint URI, create a "Legacy" class "copy" of this view and
            # register it too, for both the views and their endpoints to
            # coexist.
            legacy_view = type(
                f"Legacy{cls.__name__}",
                (cls,),
                {
                    "route_prefix": "<organization>/<repo>/",
                    "_legacy_": True,
                },
            )
            legacy_view = cast(BaseView, legacy_view)
            legacy_view.register(app, *args, **kwargs)

        return super().register(app, *args, **kwargs)

    @classmethod
    def _check_authorization(
        cls,
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> None:
        """Check the current user is authorized to perform an action
        and raise an exception otherwise.
        """
        if not cls._is_authorized(organization, repo, permission, oid):
            raise exc.Forbidden(
                "You are not authorized to perform this action"
            )

    @staticmethod
    def _is_authorized(
        organization: str,
        repo: str,
        permission: Permission,
        oid: str | None = None,
    ) -> bool:
        """Check the current user is authorized to perform an action."""
        identity = authn.get_identity()
        return identity is not None and identity.is_authorized(
            organization, repo, permission, oid
        )


class BatchView(BaseView):
    """Batch operations."""

    route_base = "objects/batch"

    def post(self, organization: str, repo: str) -> dict[str, Any]:
        """Batch operations."""
        payload = parser.parse(schema.batch_request_schema)

        try:
            transfer_type, adapter = transfer.match_transfer_adapter(
                payload["transfers"]
            )
        except ValueError as e:
            raise exc.InvalidPayload(str(e)) from None

        permission = (
            Permission.WRITE
            if payload["operation"] == schema.Operation.upload
            else Permission.READ
        )
        try:
            self._check_authorization(organization, repo, permission)
        except exc.Forbidden:
            # User doesn't have global permission to the entire namespace,
            # but may be authorized for all objects
            if not all(
                self._is_authorized(organization, repo, permission, o["oid"])
                for o in payload["objects"]
            ):
                raise

        response: dict[str, Any] = {"transfer": transfer_type}
        action = adapter.get_action(
            payload["operation"].value, organization, repo
        )
        response["objects"] = [action(**o) for o in payload["objects"]]  # type: ignore[call-arg]

        if all(self._is_error(o, 404) for o in response["objects"]):
            raise exc.NotFound("Cannot find any of the requested objects")

        if all(self._is_error(o) for o in response["objects"]):
            raise exc.InvalidPayload(
                "Cannot validate any of the requested objects"
            )

        # TODO @rufuspollock: Check Accept header
        # TODO @athornton: do we need an output schema?  If so...should
        # we just turn this into a Pydantic app?

        return response

    @staticmethod
    def _is_error(obj: dict[str, Any], code: int | None = None) -> bool:
        try:
            return obj["error"]["code"] == code or code is None
        except KeyError:
            return False


class ViewProvider:
    """ViewProvider is a marker interface for storage and transfer
    adapters that can provide their own Flask views.

    This allows transfer and storage backends to register routes for
    accessing or verifying files, for example, directly from the
    Giftless HTTP server.
    """

    def register_views(self, app: Flask) -> None:
        pass
