#!/usr/bin/env python

# If available, we import cerebrum_path which adds some directories
# to our sys.path.
try:
    import cerebrum_path
except ImportError, e:
    pass

import os
import cherrypy
import config

import htdocs.index
cherrypy.root = htdocs.index

import lib.Error
def _cpOnError():
    try:
        raise
    except Exception, e:
        cherrypy.response.body = lib.Error.handle(e)
    
cherrypy.root._cpOnError = _cpOnError

def readConf(file):
    if os.path.exists(file):
    print "Using config %s" % file
        if cherrypy.__version__.startswith('3'):
            cherrypy.config.update(file)
        else:
            cherrypy.config.update(file = file)

if __name__ == '__main__':
    readConf(config.cherrypy_template)
    readConf(config.cherrypy)
    if cherrypy.__version__.startswith('3'):
        cherrypy.server.start(cherrypy.root)
    else:
        cherrypy.server.start()

# arch-tag: 298feaea-53a6-11da-9370-e22a2f127752
