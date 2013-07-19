================================================================
Cerebrum / BOFH / BOFHD startup scripts and configuration system
================================================================

Rationale
=========

The idea is to try to keep all the configuration in just one place.

Using ~/.cerebrumrc makes it possible to:

* Not pollute the environment variables

* Provide a Cerebrum environment that other scripts can utilize


Installation instructions
=========================

* Put cerebrumrc in your home folder as ~/.cerebrumrc.

* Put bofhd.sh and bofh.sh somewhere in the path, for an easy way of running
  BOFHD and BOFH.

* Optionally, put ../viewconf/viewconf.sh, ../cerepy/cerepy.sh and
  ../cerepyrun/cerepyrun.sh in the path too, for easy listing of the
  configuration files, a way of running the python interpreter and a way of
  running other python scripts (like the ones in cerebrum/contrib) with the
  cerebrum environment settings.

* Edit ~/.cerebrumrc and set your preferred configuration values.

You can now start bofh and bofhd, without having to relate to cerepath.py.

If setting values in ~/.cerebrumrc is not enough, it is possible to
create a file like::

  ~/.cerebrum/uio/cerepath.py

...and it will be used automatically.

There is only example configuration for UIO and UIA in ~/.cerebrumrc but by
following the existing pattern you can add configuration for any institution.


Dependencies
============

Depends on the /cerebrum folder and /local/bin/python that both exists on
cere-utv01.uio.no.


Starting BOFHD
==============

Examples:

* Start BOFHD with the "uio" settings::

    bofhd.sh

* Start BOFHD with the "uia" settings::

    CI=uia bofhd.sh

* View the contents of all involved cereconf.py files::

    CI=uio viewconf.sh

Create aliases for additional comfort.

