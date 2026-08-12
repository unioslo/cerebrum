Cerebrum documentation
======================

*Cerebrum* is a Python/RDBMS framework upon which user administration systems
can be built.

.. toctree::
   :titlesonly:

   config/index
   devel/index
   logging/index
   maintenance/index

.. toctree::
   :caption: Services
   :maxdepth: 1

   bofhd/index
   job-runner/index

.. toctree::
   :caption: Model

   model/index
   changelog/index
   email/index

.. toctree::
   :caption: Features
   :maxdepth: 1

   gpg/index
   systems/index

.. toctree::
   :caption: Modules
   :maxdepth: 1
   :glob:

   modules/*


About this documentation
=========================
While the documents in this directory can be read as-is, they are a lot more
readable when built using *sphinx*!

Requirements
-------------

- sphinx
- sphinx-rtd-theme


Build
------
::

    cd docs/   # here

    # Start with a clean build, especially when altering the toc!
    make clean

    # build a html document tree
    make html

    # host the document tree
    python -m http.server -d build/html/


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
