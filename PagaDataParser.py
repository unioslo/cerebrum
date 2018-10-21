# -*- coding: utf-8-*-
from __future__ import unicode_literals
import xml.sax


import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

#init the logger.
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)


class PagaDataParserClass(xml.sax.ContentHandler):
    """This class is used to iterate over all users in LT. """

    def __init__(self, filename, call_back_function):
        self.logger = logger
        self.call_back_function = call_back_function        
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name == 'data':
            pass
        elif name in ("tils", "gjest", "permisjon"):
            tmp = {}
            for k in attrs.keys():
                tmp[k] = unicode(attrs[k])
               
            self.p_data[name] = self.p_data.get(name, []) + [tmp]
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys(): 
                self.p_data[k] = unicode(attrs[k])
        else:
            logger.warn("WARNING: unknown element: %s" % name)

    def endElement(self, name):
        if name == "person":
            self.call_back_function(self.p_data)
