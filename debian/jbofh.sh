#!/bin/sh
# simple script used to run jbofh in Debian

# The first existing directory is used for JAVA_HOME (if JAVA_HOME is not
# defined in $DEFAULT)
JDK_DIRS="$JAVA_HOME /usr/lib/j2re1.3 /usr/lib/kaffe"

# Look for the right JVM to use
for jdir in $JDK_DIRS; do
	if [ -r "$jdir/bin/java" -a -z "${JAVA_HOME}" ]; then
		JAVA_HOME="$jdir"
	fi
done
export JAVA_HOME

if [ "$JAVA_HOME" ] ; then
  if [ -z "$JAVACMD" ]; then
    JAVACMD="$JAVA_HOME/bin/java"
  fi

  $JAVACMD -jar /usr/share/cerebrum/jbofh/JBofh.jar "$@"

else
  echo "No JVM found to run jbofh"
  echo "Please install a JVM to run jbofh or "
  echo "set JAVA_HOME if it's not a JVM from a Debian Package."
  exit 1
fi
