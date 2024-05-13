Shadowing GitHub LFS
====================

This guide shows how to use Giftless as the LFS server for an existing GitHub repository (not using GitHub LFS). Thanks to a handful tricks it also acts as a full remote HTTPS-based `git` repository, making this a zero client configuration setup.

This guide uses `docker compose`, so you need to [install it](https://docs.docker.com/compose/install/). It also relies on you using HTTPS for cloning GitHub repos. The SSH way is not supported.

### Running docker containers
To run the setup, `git clone https://github.com/datopian/giftless`, step into the `examples/github-lfs` and run `docker compose up`.

This will run two containers:
- `giftless`: Locally built Giftless server configured to use solely the [GitHub authentication provider](auth-providers.md#github-authenticator) and a local docker compose volume as the storage backend.
- `proxy`: An [Envoy reverse proxy](https://www.envoyproxy.io/) which acts as the frontend listening on a local port 5000, configured to route LFS traffic to `giftless` and pretty much anything else to `[api.]github.com`. **The proxy listens at an unencrypted HTTP**, setting the proxy to provide TLS termination is very much possible, but isn't yet covered (your turn, thanks for the contribution!).

Feel free to explore the `compose.yaml`, which contains all the details.

### Cloning a GitHub repository via proxy
The frontend proxy forwards the usual `git` traffic to GitHub, so go there and pick/create some testing repository where you have writable access and clone it via the proxy hostname (just change `github.com` for wherever you host):
```shell
git clone http://localhost:5000/$YOUR_ORG/$YOUR_REPO
```
When you don't use a credential helper, you might get asked a few times for the same credentials before the call gets through. [Make sure to get one](https://git-scm.com/doc/credential-helpers) before it drives you insane.

Thanks to the [automatic LFS server discovery](https://github.com/git-lfs/git-lfs/blob/main/docs/api/server-discovery.md) this is all you should need to become LFS-enabled!

### Pushing binary blobs
Let's try pushing some binary blobs then! See also [Quickstart](quickstart.md#create-a-local-repository-and-push-some-file).
```shell
# create some blob
dd if=/dev/urandom of=blob.bin bs=1M count=1
# make it tracked by LFS
git lfs track blob.bin
# the LFS tracking is written in .gitattributes, which you also want committed
git add .gitattributes blob.bin
git commit -m 'Hello LFS!'
# push it, assuming the local branch is main
# this might fail for the 1st time, when git automatically runs 'git config lfs.locksverify false'
git push -u origin main
```

This should eventually succeed, and you will find the LFS digest in place of the blob on GitHub and the binary blob on your local storage:
```shell
docker compose exec -it giftless find /lfs-storage
/lfs-storage
/lfs-storage/$YOUR_ORG
/lfs-storage/$YOUR_ORG/$YOUR_REPO
/lfs-storage/$YOUR_ORG/$YOUR_REPO/deadbeefb10bb10bad40beaa8c68c4863e8b00b7e929efbc6dcdb547084b01
```

Next time anyone clones the repo (via the proxy), the binary blob will get properly downloaded. Failing to use the proxy hostname will make `git` use GitHub's own LFS, which is a paid service you are obviously trying to avoid.

### Service teardown

Finally, to shut down your containers, break (`^C`) the current compose run and clean up dead containers with:
```shell
docker compose down [--volumes]
```
Using `--volumes` tears down the `lfs-storage` volume too, so make sure it's what you wanted.