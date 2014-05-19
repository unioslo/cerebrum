# Ansible playbook for Cerebrum

This playbook is used to run unit tests and database integration tests of
Cerebrum.

It is used to assert that all the necessary packages are installed, configures
the database, and runs the tests that it is asked to run.

## Requirements

The host that runs these tests needs the following packages, which cannot (or
should not) be installed with ansible, for obvious reasons:

- python
- python-ansible
- python-psycopg2 (for the ansible postgresql modules)
- yum-utils (for the ansible yum module)

Other requirements are listed in the test documentation and in the ansible
playbook for setting up the host.


## Creating a test configuration

Static files and templates for the default configuration should be located in
`cerebrum-test/templates` and `cerebrum-test/files`. If you need use other
templates or files for a specific test setup, those should be located in a
subfolder with a unique name *name*. To use those files, the following pattern
should be used:

1. Set global fact/variable *config* to the value *name* that you gave your
   subfolder(s).
2. When fetching the file, use this `with_first_found` pattern:

    - name: Name of task
      action: sometask with={{ item }}
      with_first_found:
        - "../templates/{{ config|default('.') }}/template.j2"
        - "../templates/template.j2"

