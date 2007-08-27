# -*- coding: iso-8859-1 -*-

import sys
import ConfigParser
import logging
import logging.config

# Read configuration
conf = ConfigParser.ConfigParser()
conf.read(('sync.conf.template', 'sync.conf'))

# Set up logging
logconfig='log.conf'
try:
    logging.config.fileConfig(logconfig)
except ConfigParser.NoSectionError,nse:
    print "Missing section in %s. Message was: %s" % (logconfig,nse)
    sys.exit(255)
