# Using WSGI Middleware

Another way Giftless allows customizing its behavior is using standard
[WSGI middleware](https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface#WSGI_middleware).
This includes both publicly available middleware libraries, or your own custom
WSGI middleware code.

## Enabling Custom WSGI Middleware

To enable a WSGI middleware, add it to the `MIDDLEWARE` config section like so:

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

## Useful Middleware Examples

Here are some examples of solving specific needs using WSGI middleware:

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

```note:: when using the Giftless Docker image, there is no need to install this
   middleware as it is already installed)
```

And then add the following to your config file:

```yaml
MIDDLEWARE:
  - class: wsgi_cors_middleware:CorsMiddleware
    kwargs:
      origin: https://www.example.com
      headers: ['Content-type', 'Accept', 'Authorization']
      methods: ['GET', 'POST', 'PUT']
```
