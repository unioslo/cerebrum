# Process this file with autoconf to produce a configure script.

# These variables are also in setup.py
AC_INIT("cerebrum", "0.1", "cerebrum-developers@usit.uio.no")

# Checks for programs.
AC_PROG_MAKE_SET
AM_MISSING_PROG(AUTOCONF, autoconf, $missing_dir)

# Top directory where python library is instaled
PYTHONDIR="$prefix/lib/python2.2/site-packages/"
AC_SUBST(PYTHONDIR)

CONFDIR=`eval "echo $sysconfdir/cerebrum"`
AC_SUBST(CONFDIR)

AC_CONFIG_FILES([
	Makefile
	testsuite/Makefile
	cerebrum_path.py
	])
AC_OUTPUT
