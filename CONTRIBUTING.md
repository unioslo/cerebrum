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

Cerebrum is sometimes messy, but we work on fixing this.


## Logging

Write short and clear log messages, and use string interpolation for variable
content.

Some guidelines:

- Use string interpolation: `logging.info('foo=%r', foo)`, not
  `logging.info('foo=%r' % (foo, ))`.

- Only log serializable arguments: `logging.info('foo=%s', repr(foo))` if `foo`
  is not serializable.

- Clarify what values you log, e.g.: `account_name=jokim` and
  `person_id=1234`.

- Use Cerebrum terms, or what is commonly used elsewhere in Cerebrum.

- Follow
  [GDPR](https://www.regjeringen.no/no/tema/lov-og-rett/innsikt/ny-personopplysningslov/).
  Don't log personal information, unless really, really necessary. When logging
  details about persons, prefer to log the person's `entity_id`, or some other
  identities, and not their birth numbers. This includes at the *DEBUG* level.

- Log exception tracebacks if caught.  Tracebacks can be omitted for really,
  really known and expected exceptions, otherwise log a message with the
  appropriate level (usually `ERROR`) and with `exc_info=True`.

Log levels: For now, the production environment logs at level *DEBUG*. This
might change in the future.

- **CRITICAL**: Only for emergencies where sysadmins need to take action
  immediately.

  This is typically when a batch script or daemon process crashes.

- **ERROR**: Whenever something that *should* succeed doesn't succeed.
  Everything logged at this level or higher should be followed up by a person.
  Examples:

  - Tried to communicate with an external system, but the system is unreachable.

  - Tried to communicate with a system, but the system returns an error

  - Tried to process a request, but an exception was raised.

- **WARNING**: Used for somewhat expected errors, and situations that should be
  *noticed*.  A warning indicates that something is odd or wrong, but it may not
  require follow-up.

  Examples:

  - A user was omitted from batch import/export because of bad data.

- **INFO**: Details that document state changes. Examples:

  - All changes to internal/external systems.

  - Start and stop of scripts (`contrib/`).

  - Vital details
  
  - Milestones in the process

- **DEBUG**: Useful details for debugging, but not for daily
  operations, a.k.a. *the rest*. Still, no sensitive data, please.

Please don't blindly reuse existing logging in Cerebrum. There are a lot of
mess we haven't fixed yet. :)
