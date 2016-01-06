# Postgres role

This role asserts that the postgres server is installed, configured and running.


## Config vars

Postgres role settings (the `pg_` facts) are documented in
`postgres/vars/main.yml`, along with their default values.

In addition, this role uses the `debug` fact to enable or disable debug tasks.
The tasks are enabled if the `debug` fact is defined.


## Tags

### host

Enable or disable the `setup_postgres` tasks, and other 'host setup' tasks
in other roles.

NOTE: For any of these tasks to do changes, you'll need to run the playbook
with:
```bash
ansible-playbook <file> --ask-sudo-pass
```

### env

Enable or disable the `setup_database` tasks, and other 'environment setup'
tasks in other roles.

### pg

Enable or disable tasks from this role.

### pg-conf

Enable or disable the postgres config tasks?
