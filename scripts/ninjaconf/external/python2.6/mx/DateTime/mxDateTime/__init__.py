""" mxDateTime - Date and time handling routines and types

    Copyright (c) 2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.
"""
try:
    from mxDateTime import *
    from mxDateTime import __version__
except ImportError, why:
    print "*** You don't have the (right) mxDateTime binaries installed !"
    raise ImportError, why
    #from mxDateTime_Python import *
    #from mxDateTime_Python import __version__
    
# Python part of the intialization
try:
    import time
    setnowapi(time.time)
    del time
    
except NameError:
    pass
