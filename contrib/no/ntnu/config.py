# -*- coding: iso-8859-1 -*-

import ConfigParser
import logging
import logging.config

# Read configuration
conf = ConfigParser.ConfigParser()
conf.read(('sync.conf.template', 'sync.conf'))

# Set up logging
logging.config.fileConfig('log.conf')
