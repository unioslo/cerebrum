# Contributing to Cerebrum

Thanks for reading this! :)

If you disagree with something in here, send us a proposal through a *pull
request*.


## Coding standards

We strive for:

- Readability

- Follow the [PEP8](https://www.python.org/dev/peps/pep-0008/) guidelines.

- Follow [PEP257](https://www.python.org/dev/peps/pep-0257/) for docstrings.

- Writing code that is ready for python3

- New code should pass `flake8` (or `pep8`?).


Cerebrum is sometimes messy, but we work on fixing this.


## Logging

In general, write log messages that are easy to parse and use by the ELK suite
(Elasticsearch, Logstash and Kibana), both for debugging, tracing and
statistics.

Some guidelines:

- Log identities that are easy to copy-paste to bofhd, e.g. `account:jokim` and
  `person_id:1234`.

- Use Cerebrum terms, or what is commonly used elsewhere in Cerebrum.

- Follow
  [GDPR](https://www.regjeringen.no/no/tema/lov-og-rett/innsikt/ny-personopplysningslov/).
  Don't log personal information, unless really, really necessary. When logging
  details about persons, prefer to log the person's `entity_id`, or some other
  identities, and not their birth numbers. This includes at the *DEBUG* level.

Log levels: For now, the production environment logs at level *DEBUG*. This
might change in the future.

- **CRITICAL**: Only for emergencies where sysadmins need to take action
  immediately. 
  
  TODO: Crashes?

- **ERROR**: Only use when really in trouble, and sysadmins need to take action
  ASAP. Examples:

  - When an integration doesn't work.

  For exceptions, prefer to use `logger.exception` for including the
  stacktrace, as long as the exception is not expected.

- **WARNING**: Used for errors that are not critical, but where sysadmins still
  need to take a look at it. Errors that should not be handled by sysadmins
  should rather be set to *INFO*.

  Examples:

  - When a single user can't be handled in an integration, but the rest works.

- **INFO**: Details that document state changes. Examples:

  - All changes to external systems.

  - Start and stop of scripts (`contrib/`), with parameters.

  - Vital details
  
  - Milestones in the process

  - Non-critical errors where Cerebrum or its sysadmins shouldn't do anything?
    E.g. bad data for a single entity from a source system.

- **DEBUG**: Details only necessary for debugging, but not for daily
  operations, a.k.a. *the rest*. Still, no sensitive data, please.


Please don't blindly reuse existing logging in Cerebrum. There are a lot of
mess we haven't fixed yet. :)
