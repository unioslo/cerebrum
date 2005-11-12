"""
Tutorial - Passing variables

This tutorial shows you how to pass GET/POST variables to methods.
"""

import os
import cherrypy

import htdocs.index
cherrypy.root = htdocs.index

import lib.Error
def _cpOnError():
    try:
        raise
    except Exception, e:
        cherrypy.response.body = lib.Error.handle(e)
    
cherrypy.root._cpOnError = _cpOnError

if __name__ == '__main__':
    file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cherrypy.conf')
    cherrypy.config.update(file = file)
    cherrypy.server.start()

# arch-tag: 298feaea-53a6-11da-9370-e22a2f127752
