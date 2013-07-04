""" Constants for writing tag tables

    These are defined in mxte.h and imported here via the C extension.
    See the documentation for details about the various constants.

    Copyright (c) 2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""
### Module init.

def _module_init():

    from mx.TextTools.mxTextTools import mxTextTools
    global id2cmd

    id2cmd = {}

    # Fetch symbols from the C extension and add them to this module
    ns = globals()
    for name, value in vars(mxTextTools).items():
        if name[:7] == '_const_':
            cmd = name[7:]
            ns[cmd] = value
            if value == 0:
                id2cmd[0] = 'Fail/Jump'
            else:
                id2cmd[value] = cmd

_module_init()
