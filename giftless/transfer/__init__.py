"""Transfer adapters

See https://github.com/git-lfs/git-lfs/blob/master/docs/api/basic-transfers.md
for more information about what transfer APIs do in Git LFS.
"""
from abc import ABC
from functools import partial
from typing import Callable, Dict, List, Optional, Set, Tuple

from giftless.auth import Authentication, authentication
from giftless.util import get_callable

_registered_adapters: Dict[str, 'TransferAdapter'] = {}


class TransferAdapter(ABC):
    """A transfer adapter tells Git LFS Server how to respond to batch API requests
    """
    def upload(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        raise NotImplementedError("This transfer adapter is not fully implemented")

    def download(self, organization: str, repo: str, oid: str, size: int) -> Dict:
        raise NotImplementedError("This transfer adapter is not fully implemented")

    def get_action(self, name: str, organization: str, repo: str) -> Callable[[str, int], Dict]:
        """Shortcut for quickly getting an action callable for transfer adapter objects
        """
        return partial(getattr(self, name), organization=organization, repo=repo)


class PreAuthorizingTransferAdapter(TransferAdapter, ABC):
    """A transfer adapter that can pre-authohrize one or more of the actions it supports
    """
    _auth_module: Optional[Authentication] = None

    def set_auth_module(self, auth_module: Authentication):
        self._auth_module = auth_module

    def _preauth_headers(self, org: str, repo: str, actions: Optional[Set[str]] = None,
                         oid: Optional[str] = None) -> Dict[str, str]:
        if not (self._auth_module and self._auth_module.preauth_handler):
            return {}

        identity = self._auth_module.get_identity()
        if identity is None:
            return {}

        return self._auth_module.preauth_handler.get_authz_header(identity, org, repo, actions, oid)


class ViewProvider:
    """ViewProvider transfer adapters can register additional views with the Flask app

    A ViewProvider is an optional added interface to TransferAdapter implementations.
    It allows the adapter to also register additional routes -> views with the
    py-git-lfs-server Flask app.
    """
    def register_views(self, app):
        pass


def init_flask_app(app):
    """Initialize a flask app instance with transfer adapters.

    This will:
    - Instantiate all transfer adapters defined in config
    - Register any Flask views provided by these adapters
    """
    config = app.config.get('TRANSFER_ADAPTERS', {})
    adapters = {k: _init_adapter(v) for k, v in config.items()}
    for k, adapter in adapters.items():
        register_adapter(k, adapter)

    for adapter in (a for a in _registered_adapters.values() if isinstance(a, ViewProvider)):
        adapter.register_views(app)


def register_adapter(key: str, adapter: TransferAdapter):
    """Register a transfer adapter
    """
    _registered_adapters[key] = adapter


def match_transfer_adapter(transfers: List[str]) -> Tuple[str, TransferAdapter]:
    for t in transfers:
        if t in _registered_adapters:
            return t, _registered_adapters[t]
    raise ValueError("Unable to match any transfer adapter: {}".format(transfers))


def _init_adapter(config: Dict) -> TransferAdapter:
    """Call adapter factory to create a transfer adapter instance
    """
    factory = get_callable(config['factory'])  # type: Callable[..., TransferAdapter]
    adapter: TransferAdapter = factory(**config.get('options', {}))
    if isinstance(adapter, PreAuthorizingTransferAdapter):
        adapter.set_auth_module(authentication)
    return adapter
