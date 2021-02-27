Getting Started
===============

### Running a local example

1. Create a new project on Github or any other platform.
Here, we create a project named `example-proj-datahub-io`.

2. Add any data file to it.
The goal is to track this possible large file with
git-lfs and use Giftless as the local server. In our example,
we create a CSV named `research_data_factors.csv`.


3. Create a file named `giftless.yaml` in your project root directory with the
following content in order to have a local server:

```yaml
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: giftless.storage.local_storage:LocalStorage
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write
```

4. Export it:

```bash
$ export GIFTLESS_CONFIG_FILE=giftless.yaml
```

5. Start the Giftless server (by docker or Python).

6. Initialize your git repo and connect it with the
remote project:

```bash
git init
git remote add origin YOUR_REMOTE_REPO
```

7. Track files with git-lfs:

```bash
git lfs track 'research_data_factors.csv'
git lfs track
git add .gitattributes #you should have a .gitattributes file at this point
git add "research_data_factors.csv"
git commit -m "Tracking data files"
```
  * You can see a list of tracked files with `git lfs ls-files`

8. Configure `lfs.url` to point to your local Giftless server instance:

```bash
git config -f .lfsconfig lfs.url http://127.0.0.1:5000/<user_or_org>/<repo>/
# in our case, we used http://127.0.0.1:5000/datopian/example-proj-datahub-io/;
# make sure to end your lfs.url with /
```

9. The previous configuration will produce changes into `.lfsconfig` file.
Add it to git:

```bash
git add .lfsconfig
git commit -m "New git-lfs server endpoint"
# if you don't see any changes, run git rm --cached *.csv and then re-add your files, then commit it
git lfs push origin master
```

