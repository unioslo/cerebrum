Coding conventions for Cerebrum
====================================

Code submitted to Cerebrum should conform to `PEP 8 -- Style Guide for
Python Code <http://www.python.org/peps/pep-0008.html>`_.  

The document is a bit long, so we repeat some of the main points here:

* tabs should not be used in Cerebrum (though PEP 8 allows it)
* follow the naming conventions for class, variable and method names.
  See ``Cerebrum/Entity.py`` for an example.
* avoid lines wider than 79 lines (there may be exceptions)
* It is recomended to follow `PEP 287 -- reStructuredText Docstring
  Format <http://www.python.org/dev/peps/pep-0287/>`_ if docstring
  formatting is desired.

Example (TODO-2006-12-03 runefro: expand and elaborate)::
    class Keeper(Storer):

        """
        Keep data fresher longer.

        Extend `Storer`.  Class attribute `instances` keeps track
        of the number of `Keeper` objects instantiated.
        """

        instances = 0
        """How many `Keeper` objects are there?"""

        def __init__(self):
            """
            Extend `Storer.__init__()` to keep track of
            instances.  Keep count in `self.instances` and data
            in `self.data`.
            """
            Storer.__init__(self)
            foo_bar = "test"


Editor configuration
======================

How to set up your editor to follow indentation and possibly other
parts of the coding conventions.

Emacs
--------
Add the following to ``$HOME/.emacs``::
  (setq-default indent-tabs-mode nil)

Usage of TODO keywords
========================

It is sometimes desireable to add a note in the source-code indicating
that something should be done at a later point.  The folowing keywords
should be used:

TODO
  "To do" indicates that we have some idea of how to resolve a given
  task, but don't have time to fix it right now.
TBD
  "To be decided" indicates that some issue needs to be resolved
  before the code in question can be modified.
FIXME
  Indicates a known bug/misfeature in the code that should be fixed.

It may sometimes be a bit unclear what keyword to use.  The main point
is to use one of these and avoid inventing new.

It is recomended to include a date and name when adding these keywords
to make tracking easier.  For example::

   TODO-2006-12-03 runefro: the code above may not behave correctly
   during a lunar eclipse
