================================================================
Cerebrum / BOFH / BOFHD startup scripts and configuration system
================================================================

Rationale
=========

The idea is to keep all the configuration in only one place, if possible.

Installation instructions
=========================

* Put cerebrumrc in your home folder as ~/.cerebrumrc.

* Put bofhd.sh and bofh.sh somewhere in the path.

* Edit ~/.cerebrumrc and set your preferred configuration values.

You can now start bofh and bofhd, without relating to cerepath.py, unless you want to.

If setting values in ~/.cerebrumrc is not enough, it is possible to create a file like::

  ~/.cerebrum/uio/cerepath.py

...and it will be used automatically.

There is only example configuration for UIO and UIA in ~/.cerebrumrc but by following the existing pattern you can add configuration for any institution.


Dependencies
============

Depends on the /cerebrum folder and /local/bin/python that both exists on cere-utv01.uio.no.


Starting BOFHD
==============

Examples:

* Start BOFHD with the "uio" settings::

    bofhd.sh

* Start BOFHD with the "uia" settings::

    CEREBRUM_INST=uia bofhd.sh

Create aliases for additional comfort.
