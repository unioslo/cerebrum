=========================
bofhd response formatting
=========================
Bofhd commands (i.e. ``bofhd_run_command(session_id, cmd, *args)`` XMLRPC remote
procedure calls) will generally return structured data to clients.

To provide some assistance for interactive cli clients, a special data structure
called ``FormatSuggestion`` can accompany these commands.  The `format
suggestions`_ typically contains one or more template strings that can be used
to format and display the structured response data from a given command.

Not all commands will have format suggestions.  A given command will:

- either not use format suggestions and return a pre-formatted string
- or use format suggestions and return a dictionary or list of dictionaries

Clients can fetch format suggestions for a given command with the
``bofhd_get_format_suggestion(cmd)`` XMLRPC remote procedure call.


Format suggestions
------------------
A format suggestion is a dictionary with the following keys and values:

``hdr``
    An optional header line (string)

``str_vars``
    Either a string, a tuple or a list of tuples.

    If ``str_vars`` is **a string**, it will be outputted directly.

    If ``str_vars`` is **a tuple**, it should contain two or three items:

    1. A format string (e.g. ``"foo=%s, bar=%s"``)
    2. A list of references to keys in the bofh response to use for formatting
       the string (e.g. ``['foo_value', 'bar_value']``)
    3. An optional sub header

    If ``str_vars`` is **a list of tuples**, each tuple should be on the format
    mentioned.  Each tuple should only be formatted and added to the output if
    *all* the reference keys exists in the bofh response.


Example
-------
Let's assume that the server responds with the following format suggestion dict
for a given command:

.. code:: python

    {'str_vars': [
         ("name: %s", ('name',)),
         ("pos:  %d,%d", ('x', 'y')),
         ("size: %d by %d", ('width', 'height')), ]}


If a call to the command returns:

.. code:: python

    {'name': 'foo', 'x': 50, 'y': 100, 'width': 10, 'height': 20}

Then the result of using the format suggestion to print the result, should
output:

.. code:: text

    name: foo
    pos:  50,100
    size: 10 by 20

If either 'x' or 'y' is missing in a response, the second line should *not* be
printed -- *all* the listed references in each ``str_vars`` tuple *must* be present
for the format suggestion to be printed.

Note a response may contain multiple dicts too. The response:

.. code:: python

    [
      {'name': 'foo', 'width': 10, 'height': 20},
      {'name': 'bar', 'x': 70, 'y': 100},
    ]

Should result in:

.. code:: text

    name: foo
    size: 10 by 20
    name: bar
    pos: 70,100
