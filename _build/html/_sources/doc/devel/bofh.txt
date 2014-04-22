.. namespace:: develbofh

=========================================
Bofhd - development
=========================================

.. contents:: Contents


Introduction
============

Bofhd is the server used for remote administration in Cerebrum.  It
provides both user authentication and authorization.


Configuring and extending bofhd
=================================
``config.dat`` contains a list of the modules that should be loaded
into bofhd on startup.  It contains a number of lines of the format:
``module_file`` module_file does not have a .py ending, and must
contain a class named ``BofhdExtension``.

The following methods must be implemented (see
``Cerebrum/modules/no/bofhd_module_example.py`` for an example):

- ``def get_commands(self, uname)``
- ``def get_help_strings(self)``
- ``def get_format_suggestion(self, cmd)``

bofhds global dict ``all_commands`` is built up by first searching the
bofhd module, and then all modules in the configfile.  Thus, a command
in a module may override the default implementation.


Parameters and commands
-----------------------

As one can see from the ``bofhd_module_example``, commands are defined
with the ``Command`` class.  It formats the definitition of avilable
commans in a way that the client can understand.  See
bofhd_get_commands_ for details.  The first argument to Command
defines what the user has to type trigger the command, while the rest
defines the types of each argument.  It may also specify that a prompt
function should be used (for interactive commands where the next
question depends on the answer to the previous one).


bofhd_uio_cmds.py
--------------------

The bofhd module that currently has the most features is
``Cerebrum/modules/no/uio/bofhd_uio_cmds.py``.  Its original purpose
was to support the jbofh client, but other clients has started using
it as well.

- ``get_commands()`` has a special feature where it doesn't enable a
  given command in the client if the user logged in is not allowed to
  run the command.

The module is nearly 5000 lines, and will hopefylle be cleaned up
sometime in the hopefully near future:

- rename all commands to something like ``client_*``.  Extract the
  part that actually does something to a new function with the old
  name, and use this from the ``client_`` function.  Thus separating
  presentation and logic.

- A number of useful ``_get`` methods should be moved up to a new
  utility class in ``Cerebrum/modules``.

- Some of the more generic methods should be moved up.

- The remaining commands should probably be split into smaller classes.

Example
========
This example shows the ``Cerebrum/modules/no/bofhd_module_example.py``
module:

    .. include:: ../,ceresrc/Cerebrum/modules/no/bofhd_module_example.py
       :literal:


Explanation
------------
We'll briefly explain some parts of the above example.

First note that we define the dict ``all_commands`` as an empty dict.
This dict will map the name of a function, callable through
``run_comand`` to a function in this module.

The line ``all_commands['user_info']`` defines a ``Command`` that
should result in a call to the ``user_info`` method.  The ``Command``
constructor takes a tuple of the user-entered commands that should map
to this method, and a list of class instances indicating the type of
expected parameter.  It may also use the keyword-argument ``fs`` to
define a ``FormatSuggestion`` which tells the client how it may format
the return value of this method.  Please see the documentation on
these classes for the full details.

The ``get_help_strings`` method defines one group of commands,
``user``, and help for one command in this group ``user_info``.  Since
this function takes an ``account_name`` as argument, one arg_help is
also defined.  The string ``account_name`` is not refered in the
construction of the ``AccountName`` object, but if you look at its
implementation, you will se that it is the default value for its
``help_ref``.  If the default help string is not apropriate for the
argument, an alternative ``help_ref`` may be specified in the
``AccountName`` constructor.

``get_format_suggestion`` simply uses the ``Command`` object
constructed earlier to figure out which ``FormatSuggestion`` to return
for a given method-name.


Authorization
=============
Authorization in bofh is handled by the module
``Cerebrum.modules.bofhd.auth``.  The class ``BofhdAuth`` defines a
number of ``can_*`` methods that are called by bofhd when a client
tries to perform an operation.  The methods returns True on success,
and throws a ``PermissionDenied`` error on failure.

To answer the various ``can_*`` questions, the auth module defines a
datamodel shown in fig_auth_.

The various operations that can be performed, such as set_password,
create_user etc. are stored in ``auth_operation``.  Since it is common
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
.. _XML-RPC: http://www.xml-rpc.com/

Messages and responses are implemented using XML-RPC_, an open
standard that allows clients to call methods on a server.  The method
calls and the return values are encoded as XML.  All of this is
automatically handled by xmlrpclib which is included in Python.

XML-RPC was originally built for HTTP, but can also be used on top of
other protocols.

The advantage of using XML-RPC is that it is an open standard, and it
allows returing numbers, strings, dates, lists and dicts.


XML-RPC over HTTPS
-------------------
.. _HTTPS: http://www.ietf.org/rfc/rfc2818.txt

The request->response behavior of a typical bofh client makes HTTP a
suitable protocol for transfer of the XML-RPC messages.  However, for
security reasons, HTTPS_ is used.

In the future, we might decide to use another transfer protocol.  This
should only require minor changes to clients/servers.


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
called using the run_command wrapper that takes care of session-id
validation and asserting that commands performed on multiple users are
treated as an atomic operation.

The commands that may be called are prefixed with bofhd\_ in the server
source.  Most commands require authentication, which is passed with
the session-id parameter, and retrieved with login.


bofhd_login(uname, password)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   login user with uname and password, return a session id


bofhd_logout(session_id)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   tells bofhd to forget who session_id belongs to


.. _bofhd_get_commands:
  -
.. TODO: her er det noe kluss mhp. linker i html vs xml filen.  *Grave i det senere*


bofhd_get_commands(session_id)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   This command returns a tuple of tuples describing the commands
   available in the server for the user with the corresponding sessionid.
   The result is a dict formated as follows::

     {
       'group_create': (('group', 'create'), [
          {'prompt': 'Enter the new group name', 'help_ref': 'group_name_new', 
           'type': 'groupName'}, 
          {'prompt': 'Enter description', 'help_ref': 'string_description', 
           'type': 'simpleString', 'optional': 1}]), 
       'user_create': (('user', 'create'), 'prompt_func')
     }

   Each key represent a function that may be called with
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


bofhd_get_format_suggestion(cmd)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

   tells the command-line client how to format a response to a given
   command.  The data is returned by
   ``Cerebrum.modules.bofhd.cmd_param.FormatSuggestion.get_format``:

   .. sysinclude::
     :vardef: ext_fsug scripts/ext_doc.py --module ,ceresrc/Cerebrum/modules/bofhd/cmd_param.py --func_template scripts/func_doc.template

   .. sysinclude:: %(ext_fsug)s --func FormatSuggestion:get_format

bofhd_get_motd(client_id=None, client_version=None)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   return message of the day as a string.


bofhd_help(session_id, \*group)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   gives help for the command indicates by the list group.

   - With no args, returns general help.  
   - if ``arg[0]`` is ``arg_help``, returns help string for the parameter help-ref indicated by ``arg[1]``.
   - if only one argument, return help string for the command-group indicated by ``arg[1]``.
   - if two arguments, return help string for the command indicated by ``arg[1:2]``.
   

bofhd_run_command(session_id, cmd, \*args)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   Runs the command cmd, provided by a bofhd plugin.  If one or more of
   the arguments in args is a list, the command will be ran several times
   for each element, and commit/rollback will be performed after all
   operations has completed sucessfully.


bofhd_call_prompt_func(session_id, cmd, \*args)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   Allows the comand-line client to tell the server what the user has
   typed so far, and provides information about the next thing to prompt
   for.  Typically used in user creation where one has to select what
   person owns the account from a list.

bofhd_get_default_param(session_id, cmd, \*args)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   Used by the command-line client to ask for a suggestion for a
   default-parameter for a given function.  TODO: is this used?

..
