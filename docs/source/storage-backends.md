Storage Backends
================

Storage Backend classes are responsible for managing and interacting with the
system that handles actual file storage, be it a local file system or a remote,
3rd party cloud based storage.

Storage Adapters can implement one or more of several interfaces, which defines
the capabilities provided by the backend, and which
[transfer adapters](transfer-adapters.md) the backend can be used with.

## Types of Storage Backends

Each storage backend adapter can implement one or more of the following interfaces:

* **`StreamingStorage`** - provides APIs for streaming object upload / download
through the Giftless HTTP server. Works with the `basic_streaming` transfer
adapter.
* **`ExternalStorage`** - provides APIs for referring clients to upload / download
objects using an external HTTP server. Works with the `basic_external` transfer
adapter. Typically, these backends interact with Cloud Storage providers.
* **`MultipartStorage`** - provides APIs supporting the special `multipart-basic`
transfer mode. Typically, these backends interact with Cloud Storage providers.
* **`VerifiableStorage`** - provides API for verifying that an object was uploaded
properly. Most concrete storage adapters implement this interface.

## Configuring the Storage Backend

Storage backend configuration is provided as part of the configuration
of each Transfer Adapter. For example:

```yaml
TRANSFER_ADAPTERS:
  basic:  # <- the name of the transfer mode, you can have more than one
    factory: giftless.transfer.basic_external:factory
    options:
      storage_class: giftless.storage.google_cloud:GoogleCloudStorage
      storage_options:

    # add an example here
```

Built-In Storage Backends
-------------------------

### Microsoft Azure Blob Storage

#### `giftless.storage.azure:AzureBlobStorage`

Modify your `giftless.yaml` file according to the following config:

```bash
    $ cat giftless.yaml

    TRANSFER_ADAPTERS:
      basic:
        factory: giftless.transfer.basic_external:factory
        options:
          storage_class: ..storage.azure:AzureBlobsStorage
          storage_options:
            connection_string: GetYourAzureConnectionStringAndPutItHere==
            container_name: lfs-storage
            path_prefix: large-files
```

### Google Cloud Storage

#### `giftless.storage.google_cloud:GoogleCloudStorage`

To use Google Cloud Storage as a backend, you'll first need:
* A Google Cloud Storage bucket to store objects in
* an account key JSON file (see [here](https://console.cloud.google.com/apis/credentials/serviceaccountkey)).

The key must be associated with either a user or a service account, and should have
read / write permissions on objects in the bucket.

If you plan to access objects from a browser, your bucket needs to have
[CORS enabled](https://cloud.google.com/storage/docs/configuring-cors).

You can deploy the account key JSON file and provide the path to it as
the `account_key_file` storage option:

```yaml
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: giftless.storage.google_cloud:GoogleCloudStorage
      storage_options:
        project_name: my-gcp-project
        bucket_name: git-lfs
        account_key_file: /path/to/credentials.json
```

Alternatively, you can base64-encode the contents of the JSON file and provide
it inline as `account_key_base64`:

```yaml
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: giftless.storage.google_cloud:GoogleCloudStorage
      storage_options:
        project_name: my-gcp-project
        bucket_name: git-lfs
        account_key_base64: S0m3B4se64RandomStuff.....ThatI5Redac7edHeReF0rRead4b1lity==
```

If you have Workload Identity configured, you can omit the account key
entirely, in which case you will need to supply `serviceaccount_email`
instead to define which Google service account to bind to.  That service
account must have the ability to issue tokens in order to generate
signed URLs.
### Amazon S3 Storage

#### `giftless.storage.amazon_s3:AmazonS3Storage`
Modify your `giftless.yaml` file according to the following config:

```bash
    $ cat giftless.yaml

    TRANSFER_ADAPTERS:
      basic:
        factory: giftless.transfer.basic_external:factory
        options:
          storage_class: giftless.storage.amazon_s3:AmazonS3Storage
          storage_options:
            bucket_name: bucket-name
            path_prefix: optional_prefix
```

#### boto3 authentication
`AwsS3Storage` supports 3 ways of authentication defined in more detail in
[docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html):
1. Environment variables
2. Shared credential file (~/.aws/credentials)
3. AWS config file (~/.aws/config)
4. Instance metadata service on an Amazon EC2 instance that has an IAM role configured (usually used in production).

### Running updated yaml config with uWSGI

After configuring your `giftless.yaml` file, export it:

```bash
$ export GIFTLESS_CONFIG_FILE=giftless.yaml
```

You will need uWSGI running. Install it with your preferred package manager.
Here is an example of how to run it:

```bash
    # Run uWSGI in HTTP mode on port 8080
    $ uwsgi -M -T --threads 2 -p 2 --manage-script-name \
        --module giftless.wsgi_entrypoint --callable app --http 127.0.0.1:8080
```

#### Notes

* If you plan to access objects directly from a browser (e.g. using a JavaScript based Git LFS client library),
  your GCS bucket needs to be [CORS enabled](https://cloud.google.com/storage/docs/configuring-cors).

### Local Filesystem Storage

#### `giftless.storage.local:LocalStorage`

TBD
