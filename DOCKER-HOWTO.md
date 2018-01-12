Docker Howto/Introduction
=========================

### Prerequisites:

For running locally, the following tools needs to be installed:

- `docker`
- `docker-compose`

These should NOT be installed by the package manager of your
operating system as they are usually outdated, see here instead:

Docker:

https://linuxconfig.org/docker-installation-on-rhel-7-linux (RHEL)
https://www.docker.com/community-edition#/download (Others)

Docker-compose:

https://docs.docker.com/compose/install/

The docker-compose dependency could easily be avoided, but is kept for now
for sake of ease.

### Generating test-reports:

`./docker-manage get-test-report <instance-name>`

### Starting a test-watcher:

`./docker-manage start-ptw <instance-name>`

### Which tests to run:

All "instances" requires a folder in `./testsuite/docker/test-config`.

The `pytest.ini`-file within the instance-folder will be used, see how
this is done in one of the existing instance-folders if setting up a new one.

### Starting a dev-shell:

This will be the equivalent of today's `cerepy`, with a few bonus features, namely:

- Better autocompletion (thanks to ipython).
- Automatic reloading of changes in cereconf, without needing to restart the shell.

You need to sync your cerebrum_config repo in order to use the dev-shell, or simply
copy a working set of config-files into
`./testsuite/docker/cerebrum_config/<instance-name>`.

- Run `docker-manage sync-config <path-to-cerebrum_config-repo>`
- Keep the sync-config process alive while developing
- Run `docker-manage start-dev-shell <instance-name>`

Note that there must exist a folder named `/etc/<instance-name>` inside
your `cerebrum_config`-repo for this to work properly.


This is not that useful until a decent amount of test-fixtures have been
produced, but now at least it's ready to go when the time comes.

### CI-setup

The testsuite can now run in parallel inside multiple containers on a
CI-server. Currently, the Jenkinsfile in this repo is set up to do so,
by running `./testsuite/docker/scripts/ci-test-runner`.
