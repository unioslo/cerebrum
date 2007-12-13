#!/bin/sh

#
# Starts the import script with the required libs in CLASSPATH.  This
# is just an example.  The paths will probably be different on your 
# system.  For production, it is probably convenient to place all the jars
# in one directory.
#

ECP=/local/eclipse/plugins
AXIS_LIB_DIR=$ECP/org.apache.axis_1.3.0.v200608161946/lib

CLASSPATH=$AXIS_LIB_DIR/axis.jar:$AXIS_LIB_DIR/commons-discovery-0.2.jar:\
$AXIS_LIB_DIR/jaxrpc.jar:$AXIS_LIB_DIR/saaj.jar:$AXIS_LIB_DIR/wsdl4j-1.5.1.jar:\
$ECP/org.apache.commons_logging_1.0.4.v200608011657/lib/commons-logging-1.0.4.jar:\
$ECP/org.apache.jakarta_log4j_1.2.8.v200607172048/lib/log4j-1.2.8.jar:\
/tmp/ojdbc14.jar:/tmp/ephorte.jar:/tmp/ephorte-stubs.jar

java -cp $CLASSPATH no.uio.ephorte.ImportEphorteXML "$@"

