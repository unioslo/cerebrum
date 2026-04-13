====================
Bofhd - development
====================

.. admonition:: Needs review

   This is an old, and slightly unstructured document.

   It should probably be split into separate documents, and structured a bit
   better.


.. contents:: Contents
.. section-numbering::


Introduction
============
Bofhd is the server used for remote administration in Cerebrum.  It
provides both user authentication and authorization.


Configuring and extending bofhd
=================================
``config.dat`` contains a list of the modules that should be loaded
into bofhd on startup.  The file contains one bofhd command class per line, and
each command module is an import specification for loading the class.

See ``Cerebrum.utils.module`` for details on the class import format.


Parameters and commands
-----------------------
The ``Cerebrum.modules.bofhd.bofhd_core`` implements the base command class for
bofhd.

ommands are implemented as simple methods in a command subclass, and are
exposed as remote procedures by mapping it using a ``Command`` object in the
command class ``all_commands`` attribute.


``bofhd_uio_cmds.py``
---------------------
The bofhd module that currently has the most features is
``Cerebrum/modules/no/uio/bofhd_uio_cmds.py``.  Its original purpose
was to support the jbofh client, but other clients has started using
it as well.


Authorization
=============
Base authorization in bofhd is handled by the module
``Cerebrum.modules.bofhd.auth``.  The class ``BofhdAuth`` defines a
number of ``can_*`` methods that must be called by their respective commands in
their command implementation.  The methods returns True on success, and throws a
``PermissionDenied`` error on failure.

Most ``can_*``-methods support an optional ``query_run_any``-method.  When this
is set to true, the method should only return ``True`` or ``False`` to indicate
whether a given user should *see* the related commands in their clients.

Different command classes will use different ``BofhdAuth`` subclasses for
authorization.  Some institutions will have their own "global" authorization
classes. In these cases, the institution will also need:

1. A separate BofhdFooAuth-subclass, with the proper global auth class mixed in.
2. A separate BofhdFooCommand-subclass, with ``authz`` set to the custom
   BofhdFooAuth-class


BofhdAuth data model
--------------------
To answer the various ``can_*`` questions, the auth module defines a
datamodel shown in fig_auth_.

The various operations that can be performed, such as ``set_password``,
``create_user`` etc. are stored in ``auth_operation``.  Since it is common
to grant permission to more than one operation at a time,
auth_operations are grouped into an ``auth_operation_set``.

``auth_op_target`` stores the targets that an operation may be
performed on.  A target has a ``target_type`` that may be one of host,
disk, group, global_host or global_group.  For a host
``auth_op_target_attrs`` may contain a regexp indicating which disks
on the host the target actually covers.  global_host/global_group will
not affect BOFHD_SUPERUSER_GROUP or its members.

``auth_role`` maps an ``auth_operation_set`` to an ``auth_op_target``
for a given entity_id.  The current implementation of ``BofhdAuth``
allows entity_id to point to an account or a group.

Modification of the above mentioned tables are done by a number of
helper classes.  Please see their class documentation for details.


- ``BofhdAuthOpSet``
- ``BofhdAuthOpTarget``
- ``BofhdAuthRole``

.. _fig_auth :

Figure: Diagram of the databaseschema for authorization

.. image:: ../figures/bofhd_auth.png


Communication protocol
======================
The current bofhd protocol is a typical request-response protocol,
where the client is allowed to send messages, which the server replies
to.  The server does not contact the client on its own.

Protocol encoding
-----------------
.. _XML-RPC: https://www.xmlrpc.com/

Messages and responses are implemented using XML-RPC_, an open
standard that allows clients to call methods on a server.  The method
calls and the return values are encoded as XML.  All of this is
automatically handled by xmlrpclib which is included in Python.

XML-RPC was originally built for HTTP, but can also be used on top of
other protocols.

The advantage of using XML-RPC is that it is an open standard, and it
allows returing numbers, strings, dates, lists and dicts.


Extension to XML-RPC
--------------------
XML-RPC does not allow transfer of NULL values.  Bofhd allows this by
encoding them as :None.  This means that any string starting with :,
must be escaped.  For details, see
``Cerebrum.modules.bofhd.xmlutils:native_to_xmlrpc``.


Communicating with bofhd
------------------------
Bofhd was primarily written to support a command-line client.  The
client should be as simple as possible, and it should be possible to
add new commands without updating the client.

Bofhd itself only support a few commands.  Extensions to bofhd are
called using the ``run_command`` wrapper that takes care of session-id
validation and asserting that commands performed on multiple users are
treated as an atomic operation.

The commands that may be called are prefixed with ``bofhd_`` in the server
source.  Most commands require authentication, which is passed with the
session-id parameter, and retrieved with login.


``bofhd_login(uname, password)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validate username and password, return a ``session_id``


``bofhd_logout(session_id)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tells bofhd to forget the given ``session_id``


``bofhd_get_commands(session_id)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This command returns a tuple of tuples describing the commands
available on the server for the user with the corresponding ``session_id``.

The result is a dict formated as follows::

    {
        'group_create': (
            ('group', 'create'), [
                {
                    'prompt': 'Enter the new group name',
                    'help_ref': 'group_name_new', 
                    'type': 'groupName',
                }, 
                {
                    'prompt': 'Enter description',
                    'help_ref': 'string_description', 
                    'type': 'simpleString',
                    'optional': 1,
                },
            ],
        ), 
        'user_create': (('user', 'create'), 'prompt_func'),
    }

Each key represent a remote procedure that may be called with
``run_command``.  The value, ``v`` is a ``list``.  ``v[0]`` is a
list, normally of length 2 that tells jbofh what command-line
commands that should trigger this command.

``v[1]`` can be the string 'prompt_func', which will make the
client ask the server what to do for each argument entered.  More
on this later.  ``v[1]`` may also be a tuple with hashes where
each hash describes how an argument should be passed, and the
number of hashes indicate the number of required arguments.  The
hash consist of:

- ``prompt``: The prompt-string to display
- ``help_ref``: References a help-string for this argument.  The actual help text can be fetched with ``bofhd_help``.
- ``type``: indicate the datatype.  This argument is currently ignored.
- ``optional``: indicate that the argument is optional
- ``default``: indicate a defaul value for the argument
- ``repeat``: indicate that the argument is repeatable.  Obsolete.


``bofhd_get_format_suggestion(cmd)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tells the command-line client how to format a response to a given
command.  The data is returned by
``Cerebrum.modules.bofhd.cmd_param.FormatSuggestion.get_format``:

``bofhd_get_motd(client_id=None, client_version=None)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Return a message of the day as a string.


``bofhd_help(session_id, *group)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
gives help for the command indicates by the list group.

- With no args, returns general help.
- if ``arg[0]`` is ``arg_help``, returns help string for the parameter help-ref indicated by ``arg[1]``.
- if only one argument, return help string for the command-group indicated by ``arg[1]``.
- if two arguments, return help string for the command indicated by ``arg[1:2]``.

``bofhd_run_command(session_id, cmd, *args)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runs the command cmd, provided by a bofhd plugin.  If one or more of
the arguments in args is a list, the command will be ran several times
for each element, and commit/rollback will be performed after all
operations has completed sucessfully.


``bofhd_call_prompt_func(session_id, cmd, *args)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows the comand-line client to tell the server what the user has
typed so far, and provides information about the next thing to prompt
for.  Typically used in user creation where one has to select what
person owns the account from a list.
