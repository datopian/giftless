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
An ordered list of custom WSGI middleware configuration. See [Using WSGI Middleware](#using-wsgi-middleware) below for details and examples.

#### `PRE_AUTHORIZED_ACTION_PROVIDER`
Configures an additional single, special auth provider, which implements the `PreAuthorizedActionAuthenticator` 
interface. This is used by Giftless when it needs to generate URLs referencing itself, and wants to pre-authorize
clients using these URLs. By default, the JWT auth provider is used here.

There is typically no need to override the default behavior. 

#### `DEBUG`
If set to `true`, enables more verbose debugging output in logs.

## Using WSGI Middleware
Another way Giftless allows customizing its behavior is using standard 
[WSGI middleware](https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface#WSGI_middleware). 
This includes both publicly available middleware libraries, or your own custom
WSGI middleware code. 

To enable a WSGI middleware, add it to the `MIDDLEWARE` config section
like so:

```yaml
MIDDLEWARE:
  - class: wsgi_package.wsgi_module:WSGICallable
    args: []  # List of ordered arguments to pass to callable
    kwargs: {}  # key-value pairs of keyword arguments to pass to callable
```

Where:
* `class` is a `<full module name>:<class or factory>` reference to a WSGI module
and class name, or a callable that returns a WSGI object
* `args` is a list of arguments to pass to the specified callable
* `kwargs` are key-value pair of keyword arguments to pass to the specified callable. 

The middleware module must be installed in the same Python environment as Giftless
for it to be loaded. 

See below for some useful examples of adding functionality using WSGI middleware. 

### HOWTO: Fixing Generated URLs when Running Behind a Proxy
If you have Giftless running behind a reverse proxy, and available
publicly at a custom hostname / port / path / scheme that is not known to
Giftless, you might have an issue where generated URLs are not accessible. 

This can be fixed by enabling the `ProxyFix` Werkzeug middleware, which
is already installed along with Giftless:

```yaml
MIDDLEWARE:
  - class: werkzeug.middleware.proxy_fix:ProxyFix
    kwargs:
      x_host: 1
      x_port: 1
      x_prefix: 1
```

In order for this to work, you must ensure your reverse proxy (e.g. nginx) 
sets the right `X-Forwarded-*` headers when passing requests. 

For example, if you have deployed giftless in an endpoint that is available to 
clients at `https://example.com/lfs`, the following nginx configuration is 
expected, in addition to the Giftless configuration set in the `MIDDLEWARE` 
section:

```
    location /lfs/ {
        proxy_pass http://giftless.internal.host:5000/;
        proxy_set_header X-Forwarded-Prefix /lfs;
    }
```

This example assumes Giftless is available to the reverse proxy at
`giftless.internal.host` port 5000. In addition, `X-Forwarded-Host`, 
`X-Forwarded-Port`, `X-Forwarded-Proto` are automatically set by nginx by
default.  

### HOWTO: CORS Support
If you need to access Giftless from a browser, you may need to ensure 
Giftless sends proper [CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) 
headers, otherwise browsers may reject responses from Giftless. 

There are a number of CORS WSGI middleware implementations available on PyPI,
and you can use any of them to add CORS headers control support to Giftless. 

For example, you can enable CORS support using 
[wsgi-cors-middleware](https://github.com/moritzmhmk/wsgi-cors-middleware):

```bash
(.venv) $ pip install wsgi_cors_middleware
```
(NOTE: when using the Giftless Docker image, there is no need to install this
middleware as it is already installed)

And then add the following to your config file:

```yaml
MIDDLEWARE:
  - class: wsgi_cors_middleware:CorsMiddleware
    kwargs:
      origin: https://www.example.com
      headers: ['Content-type', 'Accept', 'Authorization']
      methods: ['GET', 'POST', 'PUT']
```
