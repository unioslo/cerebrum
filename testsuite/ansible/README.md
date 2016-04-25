# Ansible playbook for Cerebrum

This playbook is used to run unit tests and database integration tests of
Cerebrum.

It is used to assert that:
 - all the necessary packages are installed
 - database is configured
 - dependencies are installed
 - Cerebrum is installed
 - Cerebrum is configured
 - database-schema is created and up to date

It will also run the tests that it is asked to run.

## Requirements

### Local host

The host that executes the ansible playbook must have the following packages
installed:

- python
- python-ansible

### Remote host

The host that executes the actual modules, requires the following packages:

- python
- yum-utils

All other dependencies should be installed by the roles that depends on them.


## Ansible extensions

The Cerebrum ansible playbooks depends on some custom modules and plugins, which
are defined within this folder.

### Modules

 - `makedb`: Set up database schema for Cerebrum
 - `virtualenv_info`: Gets info from a virtualenv, e.g. the path to site-packages

TODO: Not sure if makedb will work remotely?

### Filter plugins

 - prefix - prefix a string or list of strings
 - postfix - postfix a string or list of strings
 - stdout - capture stdout from a command result
 - stderr - capture stderr from a command result
 - rc\_or  - capture rc from a command result
 - tmpfile - generate a unique temporary name to use remotely
 - dest    - fetch path/dest from a task result


## Roles

This folder contains multiple roles.

### `postgres`

Set up a host as postgres db host.

TODO: Better setup – allow the host to run on a different host than the
cerebrum-host?

### `phpunit`

Install neccessary packages to use a host to run PHP unit tests. This doesn't
really belong here, but we currently have no better place to put this role.

TODO: Set up playbooks for other products in a separate repository.

### `cerebrum`

Set up a python environment, and installs Cerebrum

### `cerebrum-test`

Configure a cerebrum-environment as a test environment, and run tests.

## Playbooks

- `crbtest_local.yml` - targets the hosts in the group `localtests`, with
  `ansible_connection=local`. Use this playbook to run tests on a ci-node.
- `crbtest_remote.yml` - targets hosts in the group `cerebrum-test-node`. Use
  this playbook to set up a node as testnode.

## Tags

### host

Sets up a host with the required packages from epel, and a postgres database
with ident authentication.

All tasks or group of tags that requires specific user privilegies (`sudo`,
`sudo_user`) should be in tagged with this tag.

### env

Sets up a test environment with python-virtualenv, installs test utils,
Cerebrum-dependencies and installs and configures Cerebrum.

### test

Runs tests.


## Variables

See the documentation in `vars/main.yml` and `defaults/main.yml` of each role.

- `config` (tags: host, env, test)

  The name of an optional sub-folder where ansible will look for override
  templates and files.

  This variable is also used to create separate environments/namespaces on the
  test node.


### Mandatory

The following variables *must* be set:

- `cerebrum` `crb_src_dir`: The location of the Cerebrum source code
- `cerebrum` `virtualenv`: Where to install Cerebrum and dependencies
- `cerebrum-test` `workdir`: Where to place test reports and other files.


## Creating a test configuration

Static files and templates for the default configuration should be located in
`cerebrum-test/templates` and `cerebrum-test/files`. If you need use other
templates or files for a specific test setup, those should be located in a
subfolder with a unique name *name*. To use those files, the following pattern
should be used:

1. Set global fact/variable *config* to the value *name* that you gave your
   subfolder(s).
2. When fetching the file, use the *with_first_foun* lookup plugin:

    - name: Process template.j2 from template/{{config}}/ or template/
      action: sometask template={{ item }}
      with_first_found:
        - files:
          - template.j2
          paths:
          - templates/{{config}}
          - templates
