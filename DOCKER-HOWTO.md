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

### Generating test-reports:

`docker-compose run --rm <service-name>`

### Starting a test-watcher:

Where `<service-name>` is a service defined inside `docker-compose.yml`:

`docker-compose run --rm <service-name> /src/testsuite/docker/container-scripts/start-ptw.sh`

### Starting a dev-shell:

Where `<service-name>` is a service defined inside `docker-compose.yml`:

`docker-compose run --rm <service-name> /src/testsuite/docker/container-scripts/start-dev-shell.sh`


This is not that useful until a decent amount of test-fixtures have been
produced, but now at least it's ready to go when the time comes.

When running `./testsuite/docker/scripts/sync-dev-config.sh` you can
also sync your cerebrum_config-repo into the running docker container.

This script will detect changes to your cerebrum_config repo, and reload
the config inside the running shell.

### CI-setup

The testsuite can now run in parallel inside multiple containers on a
CI-server. Currently, the Jenkinsfile in this repo is set up to do so,
by running `./testsuite/docker/scripts/ci-test-runner`.
