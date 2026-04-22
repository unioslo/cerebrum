======================
Bofhd XMLRPC protocol
======================
Bofhd is an `XMLRPC <https://www.xmlrpc.com/>`_ server, which exists to provide
*operators* and *end users* with a selection of management commands.

Bofhd was primarily written to support a command-line client, with the idea that
a client should be as simple as possible, and not be aware of any management
commands.

As an XMLRPC-server, it provides a selection of `remote procedures`_, which
provides the basis of the bofhd client/server interaction.  The *bofhd
management commands* themselves are implemented by server side command
extensions, and requests to run commands are performed with a
`bofhd_run_command`_ remote procedure call.


Sessions
=========
Bofhd authentication is performed by a simple login call.  A login will provide
a time-limited session-id which is to be used in remote procedures restricted to
authenticated users.


Remote procedures
==================
The most basic bofhd interactions will consist of:

1. Logging in (`bofhd_login`_)
2. Running a command (`bofhd_run_command`_)


``bofhd_login``
----------------
Signature:
::

    bofhd_login(username: str, password: str) -> str

This is an *unauthenticated* remote procedure, available to all clients.  It
validates a username and password, and returns a *session-id* for use in
*authenticated* remote procedures.


``bofhd_logout``
-----------------
Signature:
::

    bofhd_logout(session_id: str)

This remote procedure ends the given session, and should usually be called by
the client when the user ends the client interaction.


``bofhd_get_commands``
-----------------------
Signature:
::

    bofhd_get_commands(session_id: str) -> dict

This command returns a mapping of available commands, along with some metadata
for generic clients.

The result is filtered, and will only contain commands that are generally
available to the current session.

The result is dict formated as follows:
::

    {
        "<command-reference>": (
            ("<command-group>", "<command-name>"),
            # command-parameters:
            [
                {
                    "prompt": "<Display prompt>",
                    'help_ref': "<argument-name>",
                    'type': "<argument-type>",
                    'optional': 1,
                },
                ...
            ],
        ),
        ...
    }

Each key represent a remote procedure that may be called with
`bofhd_run_command`_.

``<command-reference>``
    This is the internal command name, and the name that should be given to
    `bofhd_run_command`_.

``<command-group>``, ``<command-name>``
    This is an optional display name given to the command, for use in clients.
    The ``<command-group>`` is a grouping-hint.

command parameters
    This is a list of all the required and optional parameters for the command.

    Note that all parameters are always positional, and any optional arguments
    will always apprear at the end.  Each argument may consist of:

    ``prompt``
        A prompt-string to display to an end user to query for an argument
        value.

    ``help_ref``
        Reference to a help text for this argument.  The help text can be
        fetched with `bofhd_help`_.

    ``type``
        The parameter group or type.  This argument is not too useful.

    ``optional``
        Indicates that the argument is optional.  This keyword is usually
        missing for required arguments.

    ``default``
        Indicate a default value for the argument.

    ``repeat``
        Indicate that the argument can be repeated.  This feature is deprecated.


``bofhd_get_format_suggestion``
--------------------------------
Signature:
::

    bofhd_get_format_suggestion(command_ref: str) -> list|dict

Get a formatting hint for a given command.  See `formatting <formatting.html>`_
for more info.


``bofhd_get_motd``
-------------------
Signature:
::

    bofhd_get_motd(client_id=None, client_version=None) -> str

Return a message of the day for the client.  This is an *unauthenticated* remote
procedure, and is usually fetched immediately upon connecting to the server, and
displayed to the user before login.


``bofhd_help``
---------------
Signature:
::

    bofhd_help(session_id, *args)

Get help texts from the server.  This remote procedure has a variable number of
arguments:

``bofhd_help(session_id)``
    Shows an intro the the help procedure call and help system.

``bofhd_help(session_id, <command-group>)``
    Get help on a given command group.

    Will provide a short help text, along with a list of commands and command
    signatures.

``bofhd_help(session_id, <command-group>, <command-name>)``
    Get help on a given command.

    Will provide a short help text, along with the command signature.

``bofhd_help(session_id, "arg_help", help_ref)``
    Get help on a named command argument.

    Will provide a short help text, along with the command signature.



``bofhd_run_command``
---------------------
Signature:
::

    bofhd_run_command(session_id, command_ref, *args)

Runs the named management command, with the provided arguments.

If the command succeeds, it will either return a simple text response, or a
dict/list of dicts with structured data.

If the command fails for any reason, an XMLRPC Fault response is returned to the
client.  No changes will be performed.

A third option - if an incorrect number of arguments were provided, is to return
a special prompt object.  The prompt object can either be a refence to the
missing parameter, or a special *prompt command* (see `bofhd_call_prompt_func`_
for details).

A legacy feature here, is the command tuple.  If any of the arguments provided
are lists, the command will run for all permutations of the listed arguments.
With this feature, changes are only commited if *all* the parametrized commands
complete successfully.


``bofhd_call_prompt_func``
---------------------------
Signature:
::

    bofhd_call_prompt_func(session_id, command_ref, *args)

This is a legacy feature for commands with complicated parameter signatures.  If
the number and composition of parameters depend on previous arguments, the
special prompt function can be used.

A command can return a request to query parameters one-by-one, validating each
one with a `bofhd_call_prompt_func`_ remote procedure call.

New commands generally omits this feature, and provides a series of commands
with different signatures in stead.


Parameters
===========
Bofhd does some extra serialization and escaping of certain parameter types.

For details, see ``Cerebrum.modules.bofhd.xmlutils:native_to_xmlrpc``.
