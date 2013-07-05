""" mxURL - A URL datatype.

    Copyright (c) 2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""
from URL import *
from URL import __version__

#
# Make URLs pickleable
#

# Shortcut for pickle (reduces the pickle's length)
def _URL(url,

         RawURL=RawURL):

    return RawURL(url)

# Module init
class _modinit:

    ### Register the type
    import copy_reg
    def pickle_URL(url):
        return _URL,(url.string,)
    copy_reg.pickle(URLType,
                    pickle_URL,
                    _URL)

del _modinit
