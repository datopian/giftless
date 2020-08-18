import binascii
import collections
import hashlib
import json
import os
from datetime import datetime
from typing import Any, BinaryIO, Dict, Optional

from google.cloud import storage  # type: ignore
from google.oauth2 import service_account  # type: ignore
from urllib.parse import quote

from giftless.storage import ExternalStorage, StreamingStorage

from .exc import ObjectNotFound


class GoogleCloudBlobStorage(StreamingStorage, ExternalStorage):
    """Google Cloud Storage backend supporting direct-to-cloud
    transfers.
    """

    def __init__(self, project_name: str, bucket_name: str,
                 api_key: Optional[str] = None,
                 account_json_path: Optional[str] = None,
                 path_prefix: Optional[str] = None, **_):
        self.bucket_name = bucket_name
        self.path_prefix = path_prefix
        self.api_key = api_key
        if os.getenv("GCP_CREDENTIALS"):
            ENV_GCP_CREDENTIALS = os.getenv("GCP_CREDENTIALS")
            parsed_crendentials = json.loads(ENV_GCP_CREDENTIALS)  # type: ignore
            self.credentials = service_account.Credentials.from_service_account_info(parsed_crendentials)
            self.storage_client = storage.Client(project=project_name, credentials=self.credentials)
        else:
            self.credentials = service_account.Credentials.from_service_account_file(account_json_path)
            self.storage_client = storage.Client.from_service_account_json(
                account_json_path)
        self._init_container()

    def get(self, prefix: str, oid: str) -> BinaryIO:
        bucket = self.storage_client.get_bucket(self.bucket_name)
        blob = bucket.get_blob(self._get_blob_path(prefix, oid))
        return blob.download_as_string()  # type: ignore

    def put(self, prefix: str, oid: str, data_stream: BinaryIO) -> int:
        bucket = self.storage_client.get_bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        blob.upload_from_file(data_stream)
        return data_stream.tell()

    def exists(self, prefix: str, oid: str) -> bool:
        bucket = self.storage_client.get_bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        return blob.exists()  # type: ignore

    def get_size(self, prefix: str, oid: str) -> int:
        bucket = self.storage_client.get_bucket(self.bucket_name)
        blob = bucket.blob(self._get_blob_path(prefix, oid))
        if blob.exists():
            return bucket.get_blob(self._get_blob_path(prefix, oid)).size  # type: ignore
        else:
            raise ObjectNotFound("Object does not exist")

    def get_upload_action(self, prefix: str, oid: str, size: int, expires_in: int,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        object_name = self._get_blob_path(prefix, oid)
        return {
            "actions": {
                "upload": {
                    "href": self._get_signed_url(object_name, http_method='PUT'),
                    "header": {
                        "x-ms-blob-type": "BlockBlob",
                    },
                    "expires_in": expires_in
                }
            }
        }

    def get_download_action(self, prefix: str, oid: str, size: int, expires_in: int,
                            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filename = extra.get('filename') if extra else None
        return {
            "actions": {
                "download": {
                    "href": self._get_signed_url(prefix, oid, expires_in, filename),
                    "header": {},
                    "expires_in": 900
                }
            }
        }

    def _get_blob_path(self, prefix: str, oid: str) -> str:
        """Get the path to a blob in storage
        """
        if not self.path_prefix:
            storage_prefix = ''
        elif self.path_prefix[0] == '/':
            storage_prefix = self.path_prefix[1:]
        else:
            storage_prefix = self.path_prefix
        return os.path.join(storage_prefix, prefix, oid)

    def _get_signed_url(self, object_name: str,
                        subresource=None, expiration=604800, http_method='GET',
                        query_parameters=None, headers=None) -> str:

        canonical_uri = '/{}'.format(object_name)

        datetime_now = datetime.utcnow()
        request_timestamp = datetime_now.strftime('%Y%m%dT%H%M%SZ')
        datestamp = datetime_now.strftime('%Y%m%d')

        client_email = self.credentials.service_account_email
        credential_scope = '{}/auto/storage/goog4_request'.format(datestamp)
        credential = '{}/{}'.format(client_email, credential_scope)

        if headers is None:
            headers = dict()
        host = '{}.storage.googleapis.com'.format(self.bucket_name)
        headers['host'] = host

        canonical_headers = ''
        ordered_headers = collections.OrderedDict(sorted(headers.items()))
        for k, v in ordered_headers.items():
            lower_k = str(k).lower()
            strip_v = str(v).lower()
            canonical_headers += '{}:{}\n'.format(lower_k, strip_v)

        signed_headers = ''
        for k, _ in ordered_headers.items():
            lower_k = str(k).lower()
            signed_headers += '{};'.format(lower_k)
        signed_headers = signed_headers[:-1]  # remove trailing ';'

        if query_parameters is None:
            query_parameters = dict()
        query_parameters['X-Goog-Algorithm'] = 'GOOG4-RSA-SHA256'
        query_parameters['X-Goog-Credential'] = credential
        query_parameters['X-Goog-Date'] = request_timestamp
        query_parameters['X-Goog-Expires'] = expiration
        query_parameters['X-Goog-SignedHeaders'] = signed_headers
        if subresource:
            query_parameters[subresource] = ''

        canonical_query_string = ''
        ordered_query_parameters = collections.OrderedDict(
            sorted(query_parameters.items()))
        for k, v in ordered_query_parameters.items():
            encoded_k = quote(str(k), safe='')
            encoded_v = quote(str(v), safe='')
            canonical_query_string += '{}={}&'.format(encoded_k, encoded_v)
        canonical_query_string = canonical_query_string[:-1]  # remove trailing '&'

        canonical_request = '\n'.join([http_method,
                                       canonical_uri,
                                       canonical_query_string,
                                       canonical_headers,
                                       signed_headers,
                                       'UNSIGNED-PAYLOAD'])

        canonical_request_hash = hashlib.sha256(
            canonical_request.encode()).hexdigest()

        string_to_sign = '\n'.join(['GOOG4-RSA-SHA256',
                                    request_timestamp,
                                    credential_scope,
                                    canonical_request_hash])

        # signer.sign() signs using RSA-SHA256 with PKCS1v15 padding
        signature = binascii.hexlify(
            self.credentials.signer.sign(string_to_sign)
        ).decode()

        scheme_and_host = '{}://{}'.format('https', host)
        signed_url = '{}{}?{}&x-goog-signature={}'.format(
            scheme_and_host, canonical_uri, canonical_query_string, signature)

        return signed_url

    def _init_container(self):
        """Create the storage container
        """
        self.storage_client.get_bucket(self.bucket_name)
