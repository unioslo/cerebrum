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

# should we make bofhd and jbofh?
AC_ARG_ENABLE(bofh,
        [  --disable-bofh   Disable make and install of jbofh and bofhd (enabled by default)],
        [if test "x$enableval" == "xno"; then
            bofh_enabled="no"
        else
            bofh_enabled="yes"
        fi],
        [bofh_enabled="yes"]
    )
AC_SUBST(bofh_enabled)

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
    clients/ceresync/Makefile
    clients/ceresync/config.py
    clients/cereweb/Makefile
    clients/cereweb/htdocs/Makefile
    clients/cereweb/htdocs/css/Makefile
    clients/cereweb/lib/Makefile
    clients/cereweb/lib/templates/Makefile
    servers/cerews/Makefile
	])
AC_OUTPUT

m4_if(dnl	Do not change this comment
   arch-tag: ee0d0ca0-48a5-4d8e-b645-134b4e0f9e07
)dnl
