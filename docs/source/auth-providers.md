Authentication and Authorization Providers
==========================================

## Overview
Authentication and authorization in Giftless are pluggable and can easily be customized. 
While Giftless typically bundles together code that handles both authentication and to 
some degree authorization, the two concepts should be understood separately first in order
to understand how they are handled by Giftless. 

* *Authentication* (sometimes abbreviated here and in the code as `authn`) relates to 
validating the identity of the entity (person or machine) sending a request to Giftless
* *Authorization* (sometimes abbreviated as `authz`) relates to deciding, once an 
identity has been established, whether the requesting party is permitted to perform 
the requested operation 

``` note:: In this guide and elsewhere we may refer to *auth* as a way of referring to 
   both authentication and authorization in general, or where distinction between the two
   concepts is not important.
```

## Provided Auth Modules
Giftless provides the following authentication and authorization modules by default:

* `giftless.auth.jwt:JWTAuthenticator` - uses [JWT tokens](https://jwt.io/) to both identify
  the user and grant permissions based on scopes embedded in the token payload.
* `giftless.auth.allow_anon:read_only` - grants read-only permissions on everything to every
  request; Typically, this is only useful in testing environments or in very limited 
  deployments.
* `giftless.auth.allow_anon:read_write` - grants full permissions on everything to every
  request; Typically, this is only useful in testing environments or in very limited 
  deployments.

## Configuring Authenticators
Giftless allows you to specify one or more auth module via the `AUTH_PROVIDERS` configuration 
key. This accepts a *list* of one or more auth modules. When a request comes in, auth modules will 
be invoked by order, one by one, until an identity is established. 

For example:
```yaml
AUTH_PROVIDERS:
  - factory: giftless.auth.jwt:factory
    options: 
      algorithm: HS256
      private_key: s3cret,don'ttellany0ne
  - giftless.auth.allow_anon:read_only
```

The config block above defines 2 auth providers: first, the `JWT` auth provider will be 
tried. If it manages to produce an identity (i.e. the request contains an acceptable JWT
token), it will be used. If the request does not cotain a `JWT` token, Giftless will fall
back to the next provider - in this case, the `allow_anon:read_only` provider which will
allow read-only access to anyone. 

This allows servers to be set up to accept different authorization paradigms.

You'll notice that each item in the `AUTH_PROVIDERS` list can be either an object with
`factory` and `options` keys - in which case Giftless will load the auth module by 
calling the `factory` Python callable (in the example above, the `factory` function in 
the `giftless.auth.jwt` Python module); Or, in simpler cases, it can be just a string 
(as in the case of our 2nd provider), which will be treated as a `factory` value with
no options.

Read below for the `options` possible for specific auth modules. 

## JWT Authenticator
This authenticator authenticates users by accepting a well-formed [JWT token](https://jwt.io/)
in the Authorization header as a Bearer type token, or as the value of the `?jwt=` query 
parameter. Tokens must be signed by the right key, and also match in terms of audience, 
issuer and key ID if configured, and of course have valid course expiry / not before times.

### Piggybacking on `Basic` HTTP auth
The JWT authenticator will also accept JWT tokens as the password for the `_jwt` user in `Basic` HTTP
`Authorization` header payload. This is designed to allow easier integration with clients that only support
Basic HTTP authentication. 

You can disable this functionality or change the expected username using the `basic_auth_user` configuration option.

### Configuration Options
The following options are available for the `jwt` auth module:

* `algorithm` (`str`): JWT algorithm to use, e.g. `HS256` (default) or `RS256`. Must match the algorithm
  used by your token provider
* `public_key` (`str`): Public key string, used to verify tokens signed with any asymmetric algorithm (i.e. all 
  algorithms except `HS*`); Optional, not needed if a symmetric algorithm is in use.
* `public_key_file` (`str`): Path to file containing the public key. Specify as an alternative to `public_key`.  
* `private_key` (`str`): Private key string, used to verify tokens signed with a symmetric algorithm (i.e. `HS*`); 
  Optional, not needed if an asymmetric algorithm is in use. 
* `public_key_file` (`str`): Path to file containing the private key. Specify as an alternative to `private_key`. 
* `leeway` (`int`): Key expiry time leeway in seconds (default is 60); This allows for a small clock time skew
  between the key provider and Giftless server
* `key_id` (`str`): Optional key ID string. If provided, only keys with this ID will be accepted. 
* `basic_auth_user` (`str`): Optional HTTP Basic authentication username to look for when piggybacking on Basic
  authentication. Default is `_jwt`. Can be set to `None` to disable inspecting `Basic` auth headers. 

#### Options only used when module used for generating JWT tokens
The following options are currently only in use when the module is used for generating tokens for 
self-signed requests (i.e. not as an `AUTH_PROVIDER`, but as a `PRE_AUTHORIZED_ACTION_PROVIDER`):

* `default_lifetime` (`int`): lifetime of token in seconds 
* `issuer` (`str`): token issuer (optional)
* `audience` (`str`): token audience (optional)

### JWT Authentication Flow
A typical flow for JWT is:

0. There is an external *trusted* system that can generate and sign JWT tokens and 
   Giftless is configured to verify and accept tokens signed by this system
1. User is logged in to this external system
2. A JWT token is generated and signed by this system, granting permission to specific 
   scopes applicable to Giftless
3. The user sends the JWT token along with any request to Giftless, using either
the `Authorization: Bearer ...` header or the `?jwt=...` query parameter
4. Giftless validates and decodes the token, and proceeds to grant permissions 
based on the `scopes` claim embedded in the token.  

To clarify, it is up to the 3rd party identity / authorization provider to decide, 
based on the known user identity, what scopes to grant. 

### Scopes
Beyond authentication, JWT tokens may also include authorization payload
in the "scopes" claim.

Multiple scope strings can be provided, and are expected to have the
following structure:

    obj:{org}/{repo}/{oid}:{subscope}:{actions}

or:

    obj:{org}/{repo}/{oid}:{actions}

Where:

* `{org}` is the organization of the target object 
* `{repo}` is the repository of the target object. Omitting or replacing with `*` 
  designates we are granting access to all repositories in the organization
* `{oid}` is the Object ID. Omitting or replacing with `*` designates we are granting 
  access to all objects in the repository
* `{subscope}` can be `metadata` or omitted entirely. If `metadata` is specified, 
  the scope does not grant access to actual files, but to metadata only - e.g. objects 
  can be verified to exist but not downloaded.
* `{actions}` is a comma separated list of allowed actions. Actions can be `read`, `write` 
  or `verify`. If omitted or replaced with a `*`, all actions are permitted.

### Examples
Some examples of decoded tokens (note that added comments are not valid JSON):

```js
{
  "exp": 1586253890,           // Token expiry time
  "sub": "a-users-id",         // Optional user ID
  "iat": 1586253590,           // Optional, issued at
  "nbf": 1586253590,           // Optional, not valid before
  "name": "User Name",         // Optional, user's name
  "email": "user@example.com", // Optional, user's email
  "scopes": [
    // read a specific object
    "obj:datopian/somerepo/6adada03e86b154be00e25f288fcadc27aef06c47f12f88e3e1985c502803d1b:read",

    // read the same object, but do not limit to a specific prefix
    "obj:6adada03e86b154be00e25f288fcadc27aef06c47f12f88e3e1985c502803d1b:read",

    // full access to all objects in a repo
    "obj:datopian/my-repo/*",

    // Read only access to all repositories for an organization
    "obj:datopian/*:read",

    // Metadata read only access to all objects in a repository
    "obj:datopian/my-repo:meta:verify",
  ]
}
```

Typically, a token will include a single scope - but multiple scopes are
allowed.

### Rejected and Ignored Tokens
This authenticator will pass on the attempt to authenticate if no token was
provided, or it is not a JWT token, or if a key ID is configured and a
provided JWT token does not have the matching "kid" head claim (this allows
chaining multiple JWT authenticators if needed).

However, if a matching but invalid token was provided, a `401 Unauthorized`
response will be returned. "Invalid" means a token with audience or issuer
mismatch (if configured), an expiry time in the past, or a "not before"
time in the future, or, of course, an invalid signature.

### Additional Parameters
The `leeway` parameter allows for providing a leeway / grace time to be
considered when checking expiry times, to cover for clock skew between
servers.

## Understanding Authentication and Authorization Providers

This part is more abstract, and will help you understand how Giftless handles 
authentication and authorization in general. If you want to create a custom auth 
module, or better understand how provided auth modules work, read on. 

Giftless' authentication and authorization module defines two key interfaces for handling
authentication and authorization:

### Authenticators
Authenticator classes are subclasses of `giftless.auth.Authenticator`. One or more 
authenticators can be configured at runtime, and each authenticator can try to obtain a 
valid user identity from a given HTTP request. 

Once an identity has been established, an `Identity` (see below) object will be returned,
and it is the role of the Authenticator class to populate this object with information about
the user, such as their name and email, and potentially, information on granted permissions. 

Multiple authenticators can be chained, so that if one authenticator cannot find a valid 
identity in the request, the next authenticator will be called. If no authenticator manages
to return a valid identity, by default a `401 Unauthorized` response will be returned for 
any action, but this behavior can be modified via the `@Authentication.no_identity_handler`
decorator. 

### Identity
Very simply, an `Identity` object encapsulates information about the current user making the
request, and is expected to have the following interface:

```python
class Identity:
    name: Optional[str] = None
    id: Optional[str] = None
    email: Optional[str] = None

    def is_authorized(self, organization: str, repo: str, permission: Permission, oid: Optional[str] = None) -> bool:
        """Tell if user is authorized to perform an operation on an object / repo
        """
        pass
```

Most notably, the `is_authorized` method will be used to tell whether the user, represented by 
the Identity object, is authorized to perform an action (one of the `Permission` values specified
below) on a given entity. 

Authorizer classes may use the default built-in `DefaultIdentity`, or implement an `Identity` 
subclass of their own. 

#### Permissions
Giftless defines the following permissions on entites:

```python
class Permission(Enum):
    READ = 'read'
    READ_META = 'read-meta'
    WRITE = 'write'
```

For example, if `Permission.WRITE` is granted on an object or a repository, the user will
be allowed to write objects matching the granted organization / repository / object scope.
