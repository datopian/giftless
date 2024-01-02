Transfer Adapters
=================
Git LFS servers and clients can implement and negotiate different
[transfer adapters](https://github.com/git-lfs/git-lfs/blob/master/docs/api/basic-transfers.md).
Typically, Git LFS will only define a `basic` transfer mode and support that. `basic` is simple
and efficient for direct-to-storage uploads for backends that support uploading using
a single `PUT` request.

## `basic` Transfer Mode

### External Storage `basic` transfer adapter
The `basic_external` transfer adapter is designed to facilitate LFS `basic` mode transfers (the default transfer
mode of Git LFS) for setups in which the storage backends supports communicating directly with the Git LFS client. That
is, files will be uploaded or downloaded directly from a storage service that supports HTTP `PUT` / `GET` based access,
without passing through Giftless. With this adapter, Giftless will not handle any file transfers - it will only be
responsible for providing the client with access to storage.

This transfer adapter works with storage adapters implementing the `ExternalStorage` storage interface - typically these
are Cloud storage service based backends.

### Streaming `basic` transfer adapter
The `basic_streaming` transfer adapter facilitates LFS `basic` mode transfers in which Giftless also handles object
upload, download and verification requests directly. This is less scalable and typically less performant than
the `basic_external` adapter, as all data and potentially long-running HTTP requests must be passed through Giftless
and its Python runtime. However, in some situations this may be preferable to direct-to-storage HTTP requests.

`basic_streaming` supports local storage, and also streaming requests from some Cloud storage service backends such as
Azure and Google Cloud - although these tend to also support the `basic_external` transfer adapter.

## Multipart Transfer Mode
To support more complex, and especially multi-part uploads (uploads done using more
than one HTTP request, each with a different part of a large file) directly to backends
that support that, Giftless adds support for a non-standard `multipart-basic` transfer
mode.

**NOTE**: `basic-multipart` is a non-standard transfer mode, and will not be supported
by most Git LFS clients; For a Python implementation of a Git LFS client library that
does, see [giftless-client](https://github.com/datopian/giftless-client).

### Enabling Multipart Transfer Mode

You can enable multipart transfers by adding the following lines to your Giftless config
file:

```yaml
TRANSFER_ADAPTERS:
  # Add the following lines:
  multipart-basic:
    factory: giftless.transfer.multipart:factory
    options:
      storage_class: giftless.storage.azure:AzureBlobsStorage
      storage_options:
        connection_string: "somesecretconnectionstringhere"
        container_name: my-multipart-storage
```

You must specify a `storage_class` that supports multipart transfers (implements the `MultipartStorage`
interface). Currently, these are:
* `giftless.storage.azure:AzureBlobsStorage` - Azure Blob Storage

The following additional options are available for `multipart-basic` transfer adapter:

* `action_lifetime` - The maximal lifetime in seconds for signed multipart actions; Because multipart
uploads tend to be of very large files and can easily take hours to complete, we recommend setting this
to a few hours; The default is 6 hours.
* `max_part_size` - Maximal length in bytes of a single part upload. The default is 10MB.

See the specific storage adapter for additional backend-specific configuration options to be added under
`storage_options`.
