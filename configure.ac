# Process this file with autoconf to produce a configure script.

# These variables are also in setup.py
AC_INIT("cerebrum", "0.1", "cerebrum-developers@usit.uio.no")

# Checks for programs.
AC_PROG_MAKE_SET
AM_MISSING_PROG(AUTOCONF, autoconf, $missing_dir)
AC_PROG_INSTALL

AC_ARG_WITH(python,
	[  --with-python=NAME      which Python binary to use [[python]]],
	[python="$withval"], [python="python"])
# Which python binary should we use?
AC_PATH_PROG([PYTHON], [$python], [], [$PATH])

if test -z "$PYTHON" ; then
   AC_ERROR(no Python binary found.  It is required to run Cerebrum.)
fi

# What about cheetah compiler?
AC_ARG_WITH(cheetah,
	[  --with-cheetah=NAME     which Cheetah binary to use [[cheetah]]],
	[cheetah="$withval"], [cheetah="cheetah"])
# Which cheetah binary should we use?
AC_PATH_PROG([CHEETAH], [$cheetah], [], [$PATH])

if test -z "$CHEETAH" ; then
   AC_MSG_WARN(no Cheetah binary found.  Skipping web interface.)
fi

# where to put webpages?
AC_ARG_WITH(webroot,
	[  --with-webroot=NAME     where to place webpages [[PREFIX/var/www/htdocs]]],
	[webroot="$withval"], [webroot="$prefix/var/www/htdocs"])
AC_SUBST(webroot)


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

if test -z "$PYTHONDIR" ; then
   AC_ERROR(unable to calculate Python module installation prefix.)
fi

AC_MSG_RESULT([$PYTHONDIR])
AC_SUBST(PYTHONDIR)

CONFDIR=`eval "echo $sysconfdir/cerebrum"`
AC_SUBST(CONFDIR)

AC_CONFIG_FILES([
	Makefile
	testsuite/Makefile
    web/Makefile
    web/lib/Makefile
    web/lib/cereweb/Makefile
    web/lib/cereweb/templates/Makefile
    web/htdocs/htaccess
    web/htdocs/Makefile
    web/htdocs/css/Makefile
	cerebrum_path.py
	])
AC_OUTPUT
