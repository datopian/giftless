Giftless - a Pluggable Git LFS Server
=====================================

[![Build Status](https://travis-ci.org/datopian/giftless.svg?branch=master)](https://travis-ci.org/datopian/giftless)
[![Maintainability](https://api.codeclimate.com/v1/badges/58f05c5b5842c8bbbdbb/maintainability)](https://codeclimate.com/github/datopian/giftless/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/58f05c5b5842c8bbbdbb/test_coverage)](https://codeclimate.com/github/datopian/giftless/test_coverage)

Giftless is a Python implementation of a [Git LFS][1] Server. It is designed
with flexibility in mind, to allow pluggable storage backends, transfer
methods and authentication methods.

Giftless supports the *basic* Git LFS transfer mode with the following
storage backends:

* Local storage
* [Google Cloud Storage](https://cloud.google.com/storage)
* [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/)
  with direct-to-cloud or streamed transfers
* [Amazon S3 Storage](https://aws.amazon.com/s3/)

In addition, Giftless implements a custom transfer mode called `multipart-basic`,
which is designed to take advantage of many vendors' multipart upload
capabilities. It requires a specialized Git LFS client to use, and is currently
not supported by standard Git LFS.

See the [giftless-client](https://github.com/datopian/giftless-client) project
for a compatible Python Git LFS client.

Additional transfer modes and storage backends could easily be added and
configured.

[1]: https://git-lfs.github.com/

Documentation
-------------
* [Installation Guide](https://giftless.datopian.com/en/latest/installation.html)
* [Getting Started](https://giftless.datopian.com/en/latest/quickstart.html)
* [Full Documentation](https://giftless.datopian.com/en/latest/)
* [Developer Guide](https://giftless.datopian.com/en/latest/development.html)

License
-------
Copyright (C) 2020-2024, Datopian / Viderum, Inc.

Giftless is free / open source software and is distributed under the terms of
the MIT license. See [LICENSE](LICENSE) for details.
