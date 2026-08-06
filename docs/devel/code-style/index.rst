=========================
Code style and standards
=========================

.. toctree::
   :caption: Code style
   :maxdepth: 1
   :glob:

   *

In short: Code style is not *strictly* enforced, but:

- Write pretty code

- Never use tab indents in Python code

- Follow PEPs to the best of your ability (`PEP-8`_, `PEP-257`_)

Apply all the linters.  The author recommends running ``flake8`` with plugins:
``naming``, ``pycodestyle``, ``pyflakes``.


Legacy code
===========
There are *a lot* of code style issues in the current code base.  We're fixing
this as we go.  Always prefer PEP-8 over consistency with the current code style
of a given module.

Legacy code should be fixed/re-formatted on major changes.  When re-writing
large parts of a module, it can be useful to fix all pre-existing code style
issues first, in a separate commit.


Things to consider
===================
… when writing code for Cerebrum.


Python 3
---------
Write code that will work with Python 3.  We're working on getting there, but
until we do, all code needs to work in both Python 2.7 and Python 3.6+.


Isolate dependencies
----------------------
Use of functionality from third party dependencies should be wrapped in helper
functions for stuff that we need.  This allows us to:

1. Replace the dependency when it is no longer maintained

2. Implement the functionality ourselves if needed

Good examples:

- ``aniso8601`` and ``pytz`` is only ever accessed directly from
  ``Cerebrum.utils.date``.

  We should be able to replace these with other libraries without really
  changing function signatures or behaviour in this utils module.

- ``unidecode`` is only ever used directly from
  ``Cerebrum.utils.transliterate``.

  As long as we keep the same transliteration objects, with similar behaviour,
  we should be able to replace this library quite easily.

- ``gpgme`` is only used from ``Cerebrum.utils.gpg``

  If needed, we could re-implement a similar gpg helper module with subprocess
  and gpg binaries.


Write documentation
-------------------
Modules, classes, functions, constants, and scripts should be typically be
documented by docstrings.  See :doc:`docstrings` for more details.


Write tests
------------
Write *unit tests* for your code.

- Use pytest_ to write tests

- *Don't* use ``Factory`` - unit tests should not depend on external factors,
  like configuration, environment, state, etc...

- Use fixtures to provide configuration

- Test modules with external dependenies should be *isolated*, so they can be
  easily omitted

Focus on writing tests for *common functionality*.

See :doc:`../unit-tests` for more details on writing tests.


Logging
========
See :doc:`/logging/how-to` for more info on logging in Cerebrum.


.. _flake-8: http://flake8.pycqa.org/
.. _pep-257: https://www.python.org/dev/peps/pep-0257/
.. _pep-8: https://www.python.org/dev/peps/pep-0008/
.. _pip: https://pip.pypa.io/en/stable/user_guide/
.. _pytest: https://docs.pytest.org/
.. _sphinx: http://www.sphinx-doc.org/
.. _tox: https://tox.readthedocs.io/
.. _virtualenv: https://virtualenv.pypa.io/
