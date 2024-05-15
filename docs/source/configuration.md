Runtime Configuration
=====================

## Passing Configuration Options
Giftless can be configured by pointing it to a [`YAML`](https://yaml.org/)
configuration file when starting, or through the use of environment variables.

```note:: Changes to any configuration options will only take effect when Giftless is restarted.
```

### As a YAML file
Giftless will read configuration from a YAML file pointed by the `GIFTLESS_CONFIG_FILE`
environment variable.

```shell
# create a config file
cat <<EOF > giftless.conf.yaml
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write
EOF

# start giftless
export GIFTLESS_CONFIG_FILE=giftless.conf.yaml
uwsgi --module giftless.wsgi_entrypoint --callable app --http 127.0.0.1:8080
```

### As a YAML / JSON string passed as environment variable
If you prefer not to use a configuration file, you can pass the same YAML content as the
value of the `GIFTLESS_CONFIG_STR` environment variable:

```shell
export GIFTLESS_CONFIG_STR="
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write
"
# Proceed to start Giftless
```

Since YAML is a superset of JSON, you can also provide a more compact
JSON string instead:

```shell
export GIFTLESS_CONFIG_STR='{"AUTH_PROVIDERS":["giftless.auth.allow_anon:read_write"]}'
# Proceed to start Giftless
```

```important::
   If you provide both a YAML file (as ``GIFTLESS_CONFIG_FILE``) and a
   literal YAML string (as ``GIFTLESS_CONFIG_STR``), the two will be merged, with values
   from the YAML string taking precedence over values from the YAML file.
```

### By overriding specific options using environment variables
You can override some specific configuration options using environment variables, by
exporting an environment variable that starts with `GIFTLESS_CONFIG_` and appends
configuration object keys separated by underscores.

This capability is somewhat limited and only works if:
* The configuration option value is expected to be a string
* The configuration option value is not contained in an array
* None of the configuration object keys in the value's hierarchy contain characters that
are not accepted in environment variables, such as `-`

For example, the option specified in the configuration file as:

```yaml
TRANSFER_ADAPTERS:
  basic:
    options:
      storage_class: giftless.storage.azure:AzureBlobsStorage
```

Can be overridden by setting the following environment variable:
```shell
GIFTLESS_CONFIG_TRANSFER_ADAPTERS_BASIC_OPTIONS_STORAGE_CLASS="mymodule:CustomStorageBackend"
# Start giftless ...
```

### Using a `.env` file
If Giftless is started from a working directory that has a `.env` file, it will be loaded when Giftless is started
and used to set environment variables.

## Configuration Options
The following configuration options are accepted by Giftless:

#### `TRANSFER_ADAPTERS`
A set of transfer mode name -> transfer adapter configuration pairs. Controls transfer adapters and the storage backends
used by them.

See the [Transfer Adapters](transfer-adapters.md) section for a full list of built-in transfer adapters and their
respective options.

You can configure multiple Git LFS transfer modes, each with its own transfer adapter and configuration.
The only transfer mode that is configured by default, and that is required by the Git LFS standard, is
`basic` mode.

Each transfer adapter configuration value is an object with two keys:
* `factory` (required) - a string referencing a Python callable, in the form `package.module.submodule:callable`.
  This callable should either be an adapter class, or a factory callable that returns an adapter instance.
* `options` (optional) - a key-value dictionary of options to pass to the callable above.

#### `AUTH_PROVIDERS`
An ordered list of authentication and authorization adapters to load. Each adapter can have different
options.

Auth providers are evaluated in the order that they are configured when a request is received, until one of them
provides Giftless with a user identity. This allows supporting more than one authentication scheme in the same Giftless
instance.

See the [Auth Providers](auth-providers.md) section for a full list of supported auth providers and their
respective options.

Each auth provider can be specified either as a string of the form `package.module.submodule:callable`,
referencing a Python callable that returns the provider instance, or as an object with the following keys:
* `factory` - a string of the same form referencing a callable
* `options` - key-value pairs of arguments to pass to the callable

#### `MIDDLEWARE`
An ordered list of custom WSGI middleware configuration. See [Using WSGI Middleware](wsgi-middleware.md)
for details and examples.

#### `PRE_AUTHORIZED_ACTION_PROVIDER`
Configures an additional single, special auth provider, which implements the `PreAuthorizedActionAuthenticator`
interface. This is used by Giftless when it needs to generate URLs referencing itself, and wants to pre-authorize
clients using these URLs. By default, the JWT auth provider is used here.

There is typically no need to override the default behavior.

#### `LEGACY_ENDPOINTS`
This is a `bool` flag, default `true` (deprecated, use `false` where possible), that affects the base URI of all the service endpoints. Previously, the endpoints didn't adhere to the rules for [automatic LFS server discovery](https://github.com/git-lfs/git-lfs/blob/main/docs/api/server-discovery.md), which needed additional routing or client configuration.

The default base URI for all giftless endpoints is now `/<org_path>/<repo>.git/info/lfs` while the legacy one is `/<org>/<repo>`.
* `<org>` is a simple organization name not containing slashes (common for GitHub)
* `<org_path>` is a more versatile organization path which can contain slashes (common for GitLab)
* `<repo>` is a simple repository name not containing slashes

With `LEGACY_ENDPOINTS` set to `true`, **both the current and legacy** endpoints work simultaneously. When using the `basic_streamimg` transfer adapter, for backward compatibility it is the **legacy URI** that is being used for the object URLs in the batch API responses.

Setting `LEGACY_ENDPOINTS` to `false` makes everything use the current base URI, requests to the legacy URIs will get rejected.

#### `DEBUG`
If set to `true`, enables more verbose debugging output in logs.
