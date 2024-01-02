Specifications: Git LFS multipart-basic transfer mode
=====================================================

```
Version: 0.9.1
Date:    2020-10-09
Author:  Shahar Evron <shahar.evron@gmail.com>
```

This document describes the `multipart-basic` transfer mode for Git LFS. This is a protocol extension to Git LFS,
defining a new transfer mode to be implemented by Git LFS clients and servers.

Giftless is to be the first implementation of `multipart-basic`, but we hope that this transfer mode can be implemented
by other Git LFS implementations if it is found useful.

## Reasoning
Many storage vendors and cloud vendors today offer an API to upload files in "parts" or "chunks", using multiple HTTP
requests, allowing improved stability and performance. This is especially handy when files are multiple gigabytes in
size, and a failure during the upload of a file would require re-uploading it, which could be extremely time consuming.

The purpose of the `multipart-basic` transfer mode is to allow Git LFS servers and client facilitate direct-to-storage
uploads for backends supporting multipart or chunked uploads.

As the APIs offered by storage vendors differ greatly, `multipart-basic` transfer mode will offer abstraction over most
of these complexities in hope of supporting as many storage vendors as possible.

## Terminology
Throughout this document, the following terms are in use:
* *LFS Server* - The HTTP server to which the LFS `batch` request is sent
* *Client* or *LFS Client* - a client using the Git LFS protocol to push large files to storage via an LFS server
* *Storage Backend* - The HTTP server handling actual storage; This may or may not be the same server as the LFS
server, and for the purpose of this document, typically it is not. A typical implementation of this protocol would have
the Storage Backend be a cloud storage service such as Amazon S3 or Google Cloud Storage.

## Design Goals

### Must:
* Abstract vendor specific API and flow into a generic protocol
* Remain as close as possible to the `basic` transfer API
* Work at least with the multi-part APIs of
  [Amazon S3](https://aws.amazon.com/s3/),
  [Google Cloud Storage](https://cloud.google.com/storage) and
  [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/),

### Nice / Should:
* Define how uploads can be resumed by re-doing parts and not-redoing parts that were uploaded successfully
(this may be vendor specific and not always supported)
* Offer a local storage adapter for testing purposes

## High Level Protocol Specs
* The name of the transfer is `multipart-basic`
* Batch requests are the same as `basic` requests except that `{"transfers": ["multipart-basic", "basic"]}` is the
  expected transfers value. Clients **must** retain `basic` as the fallback transfer mode to ensure compatiblity with
  servers not implementing this extension.
* `{"operation": "download"}` replies work exactly like `basic` download request with no change
* `{"operation": "upload"}` replies will break the upload into several `actions`:
  * `init` (optional), a request to initialize the upload
  * `parts` (optional), zero or more part upload requests
  * `commit` (optional), a request to finalize the upload
  * `abort` (optional), a request to abort the upload and clean up all unfinished chunks and state
  * `verify` (optional), a request to verify the file is in storage, similar to `basic` upload verify actions
* Just like `basic` transfers, if the file fully exists and is committed to storage, no `actions` will be provided
  in the reply and the upload can simply be skipped
* Authentication and authorization behave just like with the `basic` protocol.

### Request Objects
The `init`, `commit`, `abort` and each one of the `parts` actions contain a "request spec". These are similar to `basic`
transfer adapter `actions` but in addition to `href`, `header` and `expires_in` may also include `method` (optional) and `body`
(optional) attributes, to indicate the HTTP request method and body. This allows the protocol to be vendor agnostic,
especially as the format of `init` and `commit` requests tends to vary greatly between storage backends.

The default values for these fields depends on the action:
* `init` defaults to no body and `POST` method
* `commit` defaults to no body and `POST` method
* `abort` defaults to no body and `POST` method
* `parts` requests default to `PUT` method and should include the file part as body, just like with `basic` transfer
  adapters.

In addition, each `parts` request will include the `pos` attribute to indicate the position in bytes within the file in
which the part should begin, and `size` attribute to indicate the part size in bytes. If `pos` is omitted, default to
`0` (beginning of the file). If `size` is omitted, default to read until the end of file.

#### Request / Response Examples

##### Upload Batch Request
The following is a ~10mb file upload request:
```json
{
  "transfers": ["multipart-basic", "basic"],
  "operation": "upload",
  "objects": [
    {
      "oid": "20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e",
      "size": 10000000
    }
  ]
}
```

##### Upload Batch Response
The following is a response for the same request, given an imaginary storage backend:

```json
{
  "transfer": "multipart-basic",
  "objects": [
    {
      "oid": "20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e",
      "size": 10000000,
      "actions": {
        "parts": [
          {
            "href": "https://foo.cloud.com/storage/upload/20492a4d0d84?part=0",
            "header": {
              "Authorization": "Bearer someauthorizationtokenwillbesethere"
            },
            "pos": 0,
            "size": 2500000,
            "expires_in": 86400
          },
          {
            "href": "https://foo.cloud.com/storage/upload/20492a4d0d84?part=1",
            "header": {
              "Authorization": "Bearer someauthorizationtokenwillbesethere"
            },
            "pos": 2500000,
            "size": 2500000,
            "expires_in": 86400
          },
          {
            "href": "https://foo.cloud.com/storage/upload/20492a4d0d84?part=2",
            "header": {
              "Authorization": "Bearer someauthorizationtokenwillbesethere"
            },
            "pos": 5000000,
            "size": 2500000,
            "expires_in": 86400
          },
          {
            "href": "https://foo.cloud.com/storage/upload/20492a4d0d84?part=3",
            "header": {
              "Authorization": "Bearer someauthorizationtokenwillbesethere"
            },
            "pos": 7500000,
            "expires_in": 86400
          }
        ],
        "commit": {
          "href": "https://lfs.mycompany.com/myorg/myrepo/multipart/commit",
          "authenticated": true,
          "header": {
            "Authorization": "Basic 123abc123abc123abc123abc123=",
            "Content-type": "application/vnd.git-lfs+json"
          },
          "body": "{\"oid\": \"20492a4d0d84\", \"size\": 10000000, \"parts\": 4, \"transferId\": \"foobarbazbaz\"}",
          "expires_in": 86400
        },
        "verify": {
          "href": "https://lfs.mycompany.com/myorg/myrepo/multipart/verify",
          "authenticated": true,
          "header": {
            "Authorization": "Basic 123abc123abc123abc123abc123="
          },
          "expires_in": 86400
        },
        "abort": {
          "href": "https://foo.cloud.com/storage/upload/20492a4d0d84",
          "authenticated": true,
          "header": {
            "Authorization": "Basic 123abc123abc123abc123abc123="
          },
          "method": "DELETE",
          "expires_in": 86400
        }
      }
    }
  ]
}
```

As you can see, the `init` action is omitted as will be the case with many backend implementations (we assume
initialization, if needed, will most likely be done by the LFS server at the time of the batch request).

### Chunk sizing
It is up to the LFS server to decide the size of each file chunk.

### Uploaded Part Digest
Some storage backends will support, or even require, uploading clients to send a digest of the uploaded part as part
of the request. This is a useful capability even if not required, as it allows backends to validate each part
separately as it is uploaded.

To support this, `parts` request objects may include a `want_digest` value, which may be any value specified by
[RFC-3230](https://tools.ietf.org/html/rfc3230) or [RFC-5843](https://tools.ietf.org/html/rfc5843) (the design for this
feature is highly inspired by these RFCs).

RFC-3230 defines `contentMD5` as a special value which tells the client to send the Content-MD5 header with an MD5
digest of the payload in base64 encoding.

Other possible values include a comma-separated list of q-factor flagged algorithms, one of MD5, SHA, SHA-256 and
SHA-512. Of one or more of these are specified, the digest of the payload is to be specified by the client as part of
the Digest header, using the format specified by
[RFC-3230 section 4.3.2](https://tools.ietf.org/html/rfc3230#section-4.3.1).

Clients, when receiving a `parts` object with a `want_digest` value, must include in the request to upload the part
a digest of the part, using the `Content-MD5` HTTP header (if `contentMD5` is specified as a value), or `Digest` HTTP
header for any other algorithm / `want_digest` value.

#### Digest Control Examples

##### Examples of a batch response with `want_digest` in the reply
With "contentMD5":
```json
{
  "actions": {
    "parts": [
      {
        "href": "https://foo.cloud.com/storage/upload/20492a4d0d84?part=3",
        "header": {
          "Authorization": "Bearer someauthorizationtokenwillbesethere"
        },
        "pos": 7500001,
        "want_digest": "contentMD5"
      }
    ]
  }
}
```

With sha-256 as a preferred algorithm, and md5 as a less preferred option if sha-256 is not possible:
```json
{
  "actions": {
    "parts": [
      {
        "href": "https://foo.cloud.com/storage/upload/20492a4d0d84?part=3",
        "header": {
          "Authorization": "Bearer someauthorizationtokenwillbesethere"
        },
        "pos": 7500001,
        "want_digest": "sha-256;q=1.0, md5;q=0.5"
      }
    ]
  }
}
```

##### Example of part upload request send to the storage server
Following on the `want_digest` value specified in the last example, the client should now send the following headers
to the server when uploading the part:

```
HTTP/1.1 PUT /storage/upload/20492a4d0d84?part=3
Authorization: Bearer someauthorizationtokenwillbesethere
Digest: SHA-256=thvDyvhfIqlvFe+A9MYgxAfm1q5=,MD5=qweqweqweqweqweqweqwe=
```

Or if `contentMD5` was specified:

```
HTTP/1.1 PUT /storage/upload/20492a4d0d84?part=3
Authorization: Bearer someauthorizationtokenwillbesethere
Content-MD5: qweqweqweqweqweqweqwe=
```

### Expected HTTP Responses

For each of the `init`, `commit`, `abort` and `parts` requests sent by the client, the following responses are to be
expected:

* Any response with a `20x` status code is to be considered by clients as successful. This ambiguity is by design, to
support variances between vendors (which may use `200` or `201` to indicate a successful upload, for example).

* Any other response is to be considered as an error, and it is up to the client to decide whether the request should
be retried or not. Implementors are encouraged to follow standard HTTP error status code guidelines.

* An error such as `HTTP 409` on `commit` requests could indicates that not all the file parts have been uploaded
successfully, thus it is not possible to commit the file. In such cases, clients are encouraged to issue a new `batch`
request to see if any parts need re-uploading.

* An error such as `HTTP 409` on `verify` requests typically indicates that the file could not be verified. In this
case, clients may issue an `abort` request (if an `abort` action has been specified by the server), and then retry
the entire upload. Another approach here would be to retry the `batch` request to see if any parts are missing, however
in this case clients should take special care to avoid infinite re-upload loops and fail the entire process after a
small number of attempts.

#### `batch` replies for partially uploaded content
When content was already partially uploaded, the server is expected to return a normal reply but omit request and parts
which do not need to be repeated. If the entire file has been uploaded, it is expected that no `actions` value will be
returned, in which case clients should simply skip the upload.

However, if parts of the file were successfully uploaded while others weren't, it is expected that a normal reply would
be returned, but with less `parts` to send.

## Storage Backend Implementation Considerations

### Hiding initialization / commit complexities from clients
While `part` requests are typically quite similar between vendors, the specifics of multipart upload initialization and
commit procedures are very specific to vendors. For this reason, in many cases, it will be up to the LFS server to
take care of initialization and commit code. This is fine, as long as actual uploaded data is sent directly to the
storage backend.

For example, in the case of Amazon S3:
* All requests need to have an "upload ID" token which is obtained in an initial request
* When finalizing the upload, a special "commit" request need to be sent, listing all uploaded part IDs.

These are very hard to abstract in a way that would allow clients to send them directly to the server. In addition, as
we do not want to maintain any state in the server, there is a need to make two requests when finalizing the upload:
one to fetch a list of uploaded chunks, and another to send this list to the S3 finalization endpoint.

For this reason, in many cases storage backends will need to tell clients to send the `init` and `commit` requests
to the LFS server itself, where storage backend handler code will take care of initialization and finalization. It is
even possible for backends to run some initialization code (such as getting an upload ID from AWS S3) during the initial
`batch` request.

### Falling back to `basic` transfer for small files
Using multipart upload APIs has some complexity and speed overhead, and for this reason it is recommended that servers
implement a "fallback" to `basic` transfers if the uploaded object is small enough to handle in a single part.

Clients *should* support such fallback natively, as it "rides" on existing transfer method negotiation capabilities.

The server must simply respond with `{"transfer": "basic", ...}`, even if `mutipart-basic` was request by the client
and *is supported* by the server in order to achieve this.

### Request Lifetime Considerations
As multipart uploads tend to require much more time than simple uploads, it is recommended to allow for longer `"expires_in"`
values than one would consider for `basic` uploads. It is possible that the process of uploading a single object in multiple
parts may take several hours from `init` to `commit`.
