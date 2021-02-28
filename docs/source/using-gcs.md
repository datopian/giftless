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

**IMPORTANT**: Using Google Cloud may incur some charges. It is recommended to remove any resources created during
this tutorial. 

## Set up a GCS Bucket and a Service Account
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

```yaml
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: giftless.storage.google_cloud:GoogleCloudStorage
      storage_options:
        project_name: my-gcp-project
        bucket_name: git-lfs
        account_key_file: /path/to/credentials.json
```

Alternatively, you can base64-encode the contents of the JSON file and provide
it inline as `account_key_base64`: 

```yaml
TRANSFER_ADAPTERS:
  basic:
    factory: giftless.transfer.basic_streaming:factory
    options:
      storage_class: giftless.storage.google_cloud:GoogleCloudStorage
      storage_options:
        project_name: my-gcp-project
        bucket_name: git-lfs
        account_key_base64: S0m3B4se64RandomStuff.....ThatI5Redac7edHeReF0rRead4b1lity==
```

After configuring your `giftless.yaml` file, export it:

```bash
$ export GIFTLESS_CONFIG_FILE=giftless.yaml
```

You will need uWSGI running. Install it with your preferred package manager.
Here is an example of how to run it:
    
```bash
    # Run uWSGI in HTTP mode on port 8080
    $ uwsgi -M -T --threads 2 -p 2 --manage-script-name \
        --module giftless.wsgi_entrypoint --callable app --http 127.0.0.1:8080
```

## Upload and download files using local `git`

## Conclusion
This was nice. 

See the full list of options for the Google Cloud Storage backend [here](storage-backends.md#google-cloud-storage)

## Additional Notes

* If you plan to access objects from a browser, your bucket needs to be 
  [CORS enabled](https://cloud.google.com/storage/docs/configuring-cors).
