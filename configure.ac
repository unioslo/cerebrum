# Process this file with autoconf to produce a configure script.

# These variables are also in setup.py
AC_INIT("cerebrum", "0.1", "cerebrum-developers@usit.uio.no")

# Checks for programs.
AC_PROG_MAKE_SET
AM_MISSING_PROG(AUTOCONF, autoconf, $missing_dir)

AC_ARG_WITH(python,
	[  --with-python=NAME      which Python binary to use [[python]]],
	[python="$withval"], [python="python"])
# Which python binary should we use?
AC_PATH_PROG([PYTHON], [$python], [AC_MSG_ERROR([no Python binary found])])

# Top directory where python library is installed.  TBD: Should this
# rather be based on $exec_prefix?
AC_MSG_CHECKING([where to install Python modules])
PYTHONDIR="`prefix=\"$prefix\" $PYTHON -c '
from distutils import sysconfig
import os

pfx = os.getenv(\"prefix\")
if (not pfx) or pfx == \"NONE\":
   path = sysconfig.get_python_lib()
else:
   path = sysconfig.get_python_lib(prefix=pfx)
print path'`"
AC_MSG_RESULT([$PYTHONDIR])
AC_SUBST(PYTHONDIR)

CONFDIR=`eval "echo $sysconfdir/cerebrum"`
AC_SUBST(CONFDIR)

AC_CONFIG_FILES([
	Makefile
	testsuite/Makefile
	cerebrum_path.py
	])
AC_OUTPUT
