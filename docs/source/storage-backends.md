Storage Backends
================

Storage Backend classes are responsible for managing and interacting with the
system that handles actual file storage, be it a local file system or a remote, 
3rd party cloud based storage. 

Storage Adapters can implement one or more of several interfaces, which defines
the capabilities provided by the backend, and which 
[transfer adapters](transfer-adapters.md) the backend can be used with. 

### Types of Storage Backends

* **`StreamingStorage`** - provides APIs for streaming object upload / download
through the Giftless HTTP server. Works with the `basic_streaming` transfer 
adapter. 
* **`ExternalStorage`** - provides APIs for referring clients to upload / download
objects using an external HTTP server. Works with the `basic_external` transfer
adapter. Typically, these backends interact with Cloud Storage providers. 
* **`VerifiableStorage`** - provides API for verifying that an object was uploaded
properly. Most concrete storage adapters implement this interface. 

### Configuring the Storage Backend

Storage backend configuration is provided as part of the configuration
of each Transfer Adapter.

```yaml
TRANSFER_ADAPTERS:
  basic:
    # add an example here
``` 

Built-In Storage Backends
-------------------------

### `giftless.storage.azure:AzureBlobStorage` - Microsoft Azure Blob Storage

TBD

### `giftless.storage.google_cloud:GoogleCloudStorage` - Google Cloud Storage

TBD

### `giftless.storage.local:LocalStorage` - Local Filesystem Storage

TBD
