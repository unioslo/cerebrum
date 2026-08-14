=======================
Cerebrum documentation
=======================

*Cerebrum* is a Python/RDBMS framework upon which user administration systems
can be built.


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

    cd docs/
    make html
    python -m http.server -d build/html/


Table of Contents
==================

.. toctree::
   :titlesonly:
   :maxdepth: 1

   config/index
   devel/index
   logging/index
   maintenance/index

.. toctree::
   :caption: Services
   :titlesonly:
   :maxdepth: 1

   bofhd/index
   job-runner/index

.. toctree::
   :caption: Model
   :titlesonly:
   :maxdepth: 1

   model/index
   changelog/index
   email/index

.. toctree::
   :caption: Features
   :titlesonly:
   :maxdepth: 1

   gpg/index
   systems/index

.. toctree::
   :caption: References
   :titlesonly:
   :maxdepth: 1

   genindex
   modindex
