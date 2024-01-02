Using Google Cloud Storage as Backend
=====================================
This guide will walk you through configuring Giftless to use Google Cloud Storage (GCS) as a storage backend. Using a
cloud-based storage service such as GCS is highly recommended for production workloads and large files.

Our goal will be to run a local instance of Giftless, and interact with it using local `git` just as we did in the
[quickstart guide](quickstart.md), but our LFS tracked files will be uploaded to, and downloaded from, GCS directly -
Giftless will not be handling any file transfers.

A list of all provided storage backends is available [here](storage-backends.md).

### Prerequisites

* To use GCS you will need a Google Cloud account, and a Google Cloud project.
Follow the [Google Cloud Storage quickstart guide](https://cloud.google.com/storage/docs/quickstart-console) to create
these.
* To follow this guide you will need to have the `gcloud` SDK installed locally and configured to use your project.
Follow the [installation guide](https://cloud.google.com/sdk/docs/install), and then [authorize your gcloud
  installation](https://cloud.google.com/sdk/docs/authorizing) to access your project.
* If you already had `gcloud` installed before this tutorial, make sure you have configured `gcloud` to
use the correct account and project before following this guide.

```important:: Using Google Cloud may incur some charges. It is recommended to remove any resources created during
   this tutorial.
```

## Set up a GCS Bucket and Service Account
GCS stores files (or "objects") in containers named *buckets*. Giftless will need read/write access to such a bucket via
a *service account* - a software-only account with specific permissions.

**NOTE**: If you are familiar with Google Cloud Storage and are only interested in configuring Giftless to use it, and
have a bucket and service account key at ready, you can skip this part.

### Create a GCP service account
Create a GCP service account in the scope of our project:

```shell
gcloud iam service-accounts create giftless-test \
  --display-name "Giftless Test Account"
```
Then, run:
```shell
gcloud iam service-accounts list
```

The last command should list out the project's service account. Look for an email address
of the form:

    giftless-test@<yourproject>.iam.gserviceaccount.com

This address is the identifier of the account we have just created - we will need it in the next steps.

### Create a GCS bucket and grant access to it
Create a bucket named `giftless-storage`:

```shell
gsutil mb gs://giftless-storage
```

Then grant our service account access to the bucket:

```shell
gsutil iam ch \
  serviceAccount:giftless-test@<yourproject>.iam.gserviceaccount.com:objectCreator,objectViewer \
  gs://giftless-storage
```

Replace `giftless-test@<yourproject>.iam.gserviceaccount.com` with the email address copied above. This will grant
the account read and write access to any object in the bucket, but will not allow it to modify the bucket itself.

### Download an account key
In order to authenticate as our service account, Giftless will need a GCP Account Key JSON file. This can be created
by running:

```shell
gcloud iam service-accounts keys create giftless-gcp-key.json \
  --iam-account=giftless-test@<yourproject>.iam.gserviceaccount.com
```

(again, replace `giftless-test@<yourproject>.iam.gserviceaccount.com` with the correct address)

This will create a file in the current directory named `giftless-gcp-key.json` - this is a secret key and should not be
shared or stored in a non-secure manner.

## Configure Giftless to use GCS

To use Google Cloud Storage as a storage backend and have upload and download requests be sent directly to GCS without
passing through Giftless, we need to configure Giftless to use the `basic_external` transfer adapter with
`GoogleCloudStorage` as storage backend.

Assuming you have followed the [getting started](quickstart.md) guide to set up Giftless, edit your configuration
YAML file (previously named `giftless.conf.yaml`) and add the `TRANSFER_ADAPTERS` section:

```yaml
# Giftless configuration
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write

TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_external:factory
    options:
      storage_class: giftless.storage.google_cloud:GoogleCloudStorage
      storage_options:
        project_name: giftless-tests
        bucket_name: giftless-storage
        account_key_file: giftless-gcp-key.json
```
Then, set the path to the configuration file, and start the local development server:

```shell
export GIFTLESS_CONFIG_FILE=giftless.conf.yaml
flask run
```

## Upload and download files using local `git`

Follow the [quick start guide section titled "Interacting with git"](<quickstart:Interacting with Git>)
to see that you can push LFS tracked files to your Git repository. However, you will notice a few differences:

* The `git push` command may be slightly slower this time, as our 1mb file is upload to Google Cloud via the Internet
  and not over the loopback network.
* The Giftless logs will show only two lines, and not three - something like:

      INFO 127.0.0.1 - - "POST /my-organization/test-repo/objects/batch HTTP/1.1" 200 -
      INFO 127.0.0.1 - - "POST /my-organization/test-repo/objects/storage/verify HTTP/1.1" 200 -

  This is because the `PUT` request to do the actual upload was sent directly to Google Cloud by `git-lfs`, and not to
  your local Giftless instance.
* You will not see any files stored locally this time

Behind the scenes, what happens with this setup is that when the Git LFS client asks Giftless to upload an object,
Giftless will respond by providing the client with a URL to upload the file(s) to. This URL will be a pre-signed GCP
URL, allowing temporary, limited access to write the specific file to our GCP bucket. The Git LFS client will then
proceed to upload the file using that URL, and then call Giftless again to verify that the file has been uploaded
properly.

### Check that your object is in GCS
You can check that the object has been uploaded to your GCS bucket by running:

```shell
gsutil ls gs://giftless-storage/my-organization/test-repo/
```
You should see something like:
```shell
gs://giftless-storage/my-organization/test-repo/30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58
```

### Download Objects from Git LFS
To see how downloads work with Git LFS and Giftless, let's create yet another local clone of our repository. This
simulates another user pulling from the same repository on a different machine:

```shell
cd ..
git clone fake-remote-repo other-repo
cd other-repo
```

You should now see that the `1mb-blob.bin` file exists in the other local repository, and is 1mb in size. The Gitless
logs should show one more line, detailing the request made by `git-lfs` to request access to the file in storage. The
file itself has been pulled from GCS.

## Summary
In this guide, we have seen how to configure Giftless to use GCP as a storage backend. We have seen that Giftless, and
other Git LFS servers, do not need (and in fact typically should not) serve as a file storage service, but in fact
serve as a "gateway" to our storage backend.

The Google Cloud Storage backend has some additional options. See the full list of options for the Google Cloud
Storage backend [here](storage-backends.html#google-cloud-storage)
