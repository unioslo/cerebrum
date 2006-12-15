"""
Tutorial - Passing variables

This tutorial shows you how to pass GET/POST variables to methods.
"""

import os
import cherrypy
import locale

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
    locale.setlocale(locale.LC_ALL,'no_NO')
    path = os.path.dirname(os.path.realpath(__file__))
    readConf(os.path.join(path, 'cherrypy.conf.template'))
    readConf(os.path.join(path, 'cherrypy.conf'))
    cherrypy.server.start()

# arch-tag: 298feaea-53a6-11da-9370-e22a2f127752
