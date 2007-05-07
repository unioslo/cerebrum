"""
Tutorial - Passing variables

This tutorial shows you how to pass GET/POST variables to methods.
"""

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
        cherrypy.config.update(file = file)

if __name__ == '__main__':
    readConf(config.cherrypy_template)
    readConf(config.cherrypy)
    cherrypy.server.start()

# arch-tag: 298feaea-53a6-11da-9370-e22a2f127752
