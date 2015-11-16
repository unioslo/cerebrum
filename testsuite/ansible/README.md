# Ansible playbook for Cerebrum

This playbook is used to run unit tests and database integration tests of
Cerebrum.

It is used to assert that all the necessary packages are installed, configures
the database, and runs the tests that it is asked to run.

## Requirements

Certain requirements cannot be solved by Ansible, for obvious reasons:. This
includes setting up system auths/authz, and installing Python, Ansible, etc.

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

 - `makedb`
 - `virtualenv_info`

TODO: Not sure if makedb will work remotely?

### Lookup plugins

 - `file_overload` (`with_file_overload`)

### Filter plugins

 - prefix - prefix a string or list of strings
 - postfix - postfix a string or list of strings
 - stdout - capture stdout from a command result
 - stderr - capture stderr from a command result
 - rc_or  - capture rc from a command result
 - tmpfile - generate a unique temporary name to use remotely
 - dest    - fetch path/dest from a task result


## Roles

This folder contains multiple roles.

### `postgres`

Sets up a host as postgres db host.

TODO: Better setup – allow the host to run on a different host than the
cerebrum-host?

### `cerebrum-test`

Sets up a test host, test environment and runs tests.

#### Playbooks

- `crbtest_local.yml` - targets the host `localhost`, wihtout using ssh.
- `crbtest_remote.yml` - targets hosts in the group `cerebrum-test-node`.

TODO: Is this the right way to separate host groups?

#### Tags

- host

  Sets up a host with the required packages from epel, and a postgres database
  with ident authentication.

- env

  Sets up a test environment with python-virtualenv, installs
  test utils, Cerebrum-dependencies and installs and configures Cerebrum.

- test

  Runs tests.

#### Interesting variables

See the documentation in `vars/main.yml` of each role.

- `config` (tags: host, env, test)

  The name of an optional sub-folder where ansible will look for override
  templates and files.

  Whenever we use the `with_file_overload` lookup plugin, we'll look for
  alternate files in a sub-folder with this name.


## Creating a test configuration

Static files and templates for the default configuration should be located in
`cerebrum-test/templates` and `cerebrum-test/files`. If you need use other
templates or files for a specific test setup, those should be located in a
subfolder with a unique name *name*. To use those files, the following pattern
should be used:

1. Set global fact/variable *config* to the value *name* that you gave your
   subfolder(s).
2. When fetching the file, use the *with_file_overload* lookup plugin:

    - name: Process template.j2 from template/{{config}}/ or template/
      action: sometask template={{ item }}
      with_file_overload:
        - file: 'template.j2'
        - base: 'templates',
        - alt: "{{ config | default(None) }}"
      register: _result_of_sometask

Note: If you need to inspect the result (`_result_of_sometask`), note that
the actual results are dicts in a list, `_result_of_sometask.results`.
