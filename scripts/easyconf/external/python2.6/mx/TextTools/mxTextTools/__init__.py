""" mxTextTools - A tools package for fast text processing.

    Copyright (c) 2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.
"""
from mxTextTools import *
from mxTextTools import __version__

# To maintain backward compatibility:
BMS = TextSearch
BMSType = TextSearchType
try:
    TextSearch('',None,FASTSEARCH)
except:
    FS = BMS
    FSType = BMS
else:
    def FS(match, translate=None):
        return TextSearch(match, translate, FASTSEARCH)
    FSType = TextSearchType
