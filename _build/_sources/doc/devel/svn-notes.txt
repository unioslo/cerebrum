===========================
SVN usage in Cerebrum
===========================
.. section-numbering::

Reposirory
=============

The main sourcecode repository for Cerebrum can be found at
`Sourceforge <http://sourceforge.net/svn/?group_id=60830>`_.  To check
out the current sourcecode, simply::

  svn co https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk/cerebrum cerebrum

**If you plan to commit code to Cerebrum, please read** `Coding
conventions for Cerebrum <codestyle.html>`_

Repository structure
========================

The Cerebrum SVN repository was converted from CVS using
`cvs2svn <http://cvs2svn.tigris.org/cvs2svn.html>`_ v1.5.0.  The resulting structure looked like this::

  branches/
     GREG_EWING            -- Cerebrum/extlib/Plex/
     ntnu
     VINAY_SAJIP           -- Cerebrum/extlib/logging.py
  tags/
     initial
     LOGGING_0_4_6
     ntnu_started_separate_work
     PLEX_1_1_3
     REL_0_0_1
     REL_0_0_2
     REL_0_0_3
     REL_0_9_0
     REL_0_9_1
  trunk/
     cerebrum

The structure with ``tags``, ``branches`` and ``trunk`` directories at
the top-level directory is a common SVN convention.  

Cerebrum development primarily happens in ``trunk``.  Tags and
branches are currently used rarely.  

Unless you have a good reason not to, you should allways check out
``https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk/cerebrum``.
This way you will allways work on most resent version of the source
code.


SVN introduction
==================

`SVN <http://subversion.tigris.org/>`_ is a version control system.
An extensive introduction to SVN is available as a book in `pdf and
html <http://svnbook.red-bean.com/>`_.  If you only plan to do simple
checkout, the example below is probably sufficient.  If you plan to do
more extensive work, you should consider atleast reading `Chapter
2. Basic Usage
<http://svnbook.red-bean.com/nightly/en/svn.tour.html>`_.

Users experienced with CVS, can read
`Subversion for CVS Users <http://svnbook.red-bean.com/nightly/en/svn.forcvs.html>`_ or
`CVS to SVN Crossover Guide <http://svn.collab.net/repos/svn/trunk/doc/user/cvs-crossover-guide.html>`_
for an overview of some of the differences.

A typical SVN session may look something like this::

  # Access help information
  ~/tmp/svn@dresden> svn help co
  checkout (co): Check out a working copy from a repository.
  usage: checkout URL[@REV]... [PATH]
  ...

  # Check out the repository:
  ~/tmp/svn@dresden>   svn co --username runefro https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk/cerebrum cerebrum
  A    cerebrum/java
  A    cerebrum/java/jbofh
  A    cerebrum/java/jbofh/fix_jbofh_jar.py
  ...
   U   cerebrum
  Checked out revision 7291.

  # Look at the contents
  ~/tmp/svn@dresden> cd cerebrum/
  ~/tmp/svn/cerebrum@dresden> ls
  adserver  Cerebrum   INSTALL README   ...

  # Simple change
  ~/tmp/svn/cerebrum@dresden> echo test >> README
  ~/tmp/svn/cerebrum@dresden> svn status
  M      README
  ~/tmp/svn/cerebrum@dresden> svn diff README
  Index: README
  ===================================================================
  --- README      (revision 7291)
  +++ README      (working copy)
  @@ -48,3 +48,4 @@
     The documentation for the core api can be read using pydoc.
   
   arch-tag: d628597f-d5cd-432a-8c67-62a1e0407c92
  +test
  ~/tmp/svn/cerebrum@dresden> svn commit -m "added test" README
  Authentication realm: <https://cerebrum.svn.sourceforge.net:443> SourceForge Subversion area
  Password for 'runefro': 
  Sending        README
  Transmitting file data .
  Committed revision 7292.

Unfortunately, sourceforge does not support the ``svn+ssh`` protocol,
thus the ssh-based authorized-keys authentication does not work.  It
does, however cache the credentials used when committing, so that you
on the second commit will not have to enter your password (note that
if you do not specify a file/directory name to commit/diff/update, all
files and directories will be affected)::

  ~/tmp/svn/cerebrum@dresden> svn commit -m "more test" README
  Sending        README
  Transmitting file data .
  Committed revision 7293.

To see the difference between your checked out version and the newest version::

  ~/tmp/svn/cerebrum2@dresden> svn diff -rBASE:HEAD README
  Index: README
  ===================================================================
  --- README      (working copy)
  +++ README      (revision 7294)
  @@ -50,3 +50,4 @@
   arch-tag: d628597f-d5cd-432a-8c67-62a1e0407c92
   test
   test2
  +test3

Update your repository::

  ~/tmp/svn/cerebrum2@dresden> svn update README
  U    README
  Updated to revision 7294.



Other tips & hints
-----------------------
Emacs users may find `vc-svn.el
<http://svn.collab.net/repos/svn/trunk/contrib/client-side/vc-svn.el>`_
useful to get things like "Ctrl-x v =" working.  This module is also
available elsewhere, but this one works with emacs 21.3.1 (add
``(add-to-list 'vc-handled-backends 'SVN)`` to .emacs).
