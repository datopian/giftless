Getting Up and Running
======================

This guide will introduce you to the basics of Giftless by getting it up and running locally, and seeing how it can 
interact with a local git repository. 

## Installing and Running Locally

Install Giftless to a local virtual environment. You will need Python 3.7 or newer:

```shell
# Create and active a virtual environment
mkdir giftless && cd giftless
python -m venv .venv
source .venv/bin/active  

# Install Giftless 
pip install giftless
# The following line is required due to a bug in one of our dependencies:
pip install -Ur https://raw.githubusercontent.com/datopian/giftless/master/requirements.txt
```

**NOTE**: This is a non-production installation of Giftless, using Flask's built-in development server.
Check out the [installation guide](installation.md) for other installation options.

Once done, verify that Giftless can run:
```shell
# Run Giftless using the built-in development server
export FLASK_APP=giftless.wsgi_entrypoint
flask run
```

You should see something like: 

```shell
Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```

This means Giftless is up and running with some default configuration on *localhost* port *5000*, with
the default configuration options. 

Hit Ctrl+C to stop Giftless.

## Basic Configuration 
To configure Giftless, create a file named `giftless.conf.yaml` in the current directory with the
following content:

```yaml
# Giftless configuration
AUTH_PROVIDERS:
  - giftless.auth.allow_anon:read_write
```

This will override the default read-only access mode, and allow open and full access to anyone, to any object stored 
with Giftless. Clearly this is not useful in a production setting, but for a local test this will do fine. 

Run Giftless again, pointing to this new configuration file:
```shell
export GIFTLESS_CONFIG_FILE=giftless.conf.yaml
flask run
```

## Interacting with local `git`
We will now proceed to show how Giftless can interact with a local `git` repository, as a demonstration of how Git LFS 
works.

Keep Giftless running and open a new terminal window or tab. 

### Install the `lfs` Git extension
While having a local installation of `git-lfs` is not required to run Giftless, you will need 
it to follow this guide. 

Run:
```shell
git lfs
```

If you see an error indicating that `'lfs' is not a git command`, follow the 
[Git LFS installation instructions here](https://git-lfs.github.com/). On Linux, you may be able
to simply install the `git-lfs` package provided by your distro. 

### Create a local "remote" repository
For the purpose of this tutorial, we will create a fake "remote" git repository on your local disk. This is analogous 
to a real-world remote repository such as GitHub or any other Git remote, but is simpler to set up.

```shell
mkdir fake-remote-repo && cd fake-remote-repo
git init --bare
cd ..
```

Of course, you may choose to use any other remote repository instead - just remember to replace the repository URL 
in the upcoming `git clone` command. 

### Create a local repository and push some file
Clone the remote repository we have just created to a local repository:

```shell
git clone fake-remote-repo local-repo
cd local-repo
```

Create some files and add them to git:
```shell
# This README file will be committed to Git as usual
echo "# This is a Giftless test" > README.md
# Let's also create a 1mb binary file which we'll want to store in Git LFS 
dd if=/dev/zero of=1mb-blob.bin bs=1024 count=1024
git add README.md 1mb-blob.bin
```

Tell `git-lfs` to track `.bin` files:
```shell
git lfs track "*.bin"
```

This will actually create a file named `.gitattributes` in the root of your
repository, with the following content:

```shell
cat .gitattributes 
*.bin filter=lfs diff=lfs merge=lfs -text
```

You need to have git tracking this file as well, and commit everything we have staged so far:
```shell
git add .gitattributes
git commit -m "Adding some files to track"
```

Tell Git LFS where to find the Giftless server. We will do that by using the `git config` command to write to the 
`.lfsconfig` file: 
```shell
git config -f .lfsconfig lfs.url http://127.0.0.1:5000/my-organization/test-repo
```

**NOTE**: `my-organization/test-repo` is an organization / repository prefix under which your files will be stored. 
Giftless requires all files to be stored under such prefix.  

Finally, let's push our tracked files to Git LFS:
```shell
git push origin master
```

Switch over to the shell in which Giftless is running, and you will see log messages indicating that a file has just 
been pushed to storage and verified. This should be similar to:

```
INFO 127.0.0.1 - - "POST /my-organization/test-repo/objects/batch HTTP/1.1" 200 -
INFO 127.0.0.1 - - "PUT /my-organization/test-repo/objects/storage/30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58 HTTP/1.1" 200 -
INFO 127.0.0.1 - - "POST /my-organization/test-repo/objects/storage/verify HTTP/1.1" 200 -
```

To further verify that the file has been stored by Giftless, we can list the files in our local Giftless storage 
directory:

```shell
$ ls -lR ../lfs-storage/
...snip...
../lfs-storage/my-organization/test-repo:
total 1024
-rw-rw-r-- 1 shahar shahar 1048576 Feb 28 12:08 30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58
```

You will notice a 1mb file stored in `../lfs-storage/my-organization/test-repo` - this is identical to our `1mb-blob.bin`
file, but it is stored with its SHA256 digest as its name. 

## Summary

You have now seen Giftless used as both a Git LFS server, and as a storage backend. This should give you a basic sense
of how to run Giftless, and how Git LFS servers interact with Git. 

In a real-world scenario, you would typically have Giftless serve as the Git LFS server but not as a storage backend - 
storage will be off-loaded to a Cloud Storage service which has been configured for this purpose.  
