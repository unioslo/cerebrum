""" mx.URL -- A URL datatype.

    Relies on mx.TextTools and mx.Tools.

    Copyright (c) 1998-2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""
import string,mimetypes

from mx import Tools,TextTools

#
# Import the C extension module
#
from mxURL import *
from mxURL import __version__

#
# Registry for the URL object provided by mxURL:
#
def register_scheme(scheme,uses_netloc, uses_params, uses_query, uses_fragment,
                    uses_relative):

    """ Adds a new scheme to the URL objects scheme registry. The uses_*
        fields must be 0 or 1 according to the schemes possibilities.
        
    """
    schemes[scheme] = (uses_netloc, uses_params, uses_query, uses_fragment,
                       uses_relative)

#
# Registry for the URL object provided by mxURL:
#
def register_mimetype(extension,major='*',minor='*'):

    """ Adds a new mimetype to the registry used by mxURL.

        extension must be a file name extension including the
        delimiting dot (e.g. ".html"). The function will overwrite any
        existing entry for the given extension.

    """
    assert extension[0] == '.'
    mimemap[extension] = '%s/%s' % (major,minor)

#
# Add some extra MIME types that are not included in the distribution
# version of mimetypes.py (not until Python 1.5 at least).
#
mimemap.update({
    '.shtml': 'text/html',
    '.phtml': 'text/html',
    '.pcx': 'image/pcx',
    '.txt': 'text/plain',
    '.css': 'text/css',
    '.pyo': 'application/x-python-code',
    '.c': 'text/x-c',
    '.h': 'text/x-c',
    '.cpp': 'text/x-c',
    '.cxx': 'text/x-c',
    '.hxx': 'text/x-c',
    '.xml': 'text/xml',
    '.xsl': 'application/xml',
    '.dll': 'application/octet-stream',
    '.pyd': 'application/octet-stream',
})

### Module init stuff

class _modinit:

    # Reserved URL chars as defined by RFC2396
    unsafe_charset = TextTools.set(\
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789'
        '-_.!~*\'()',0)

    # Modified version of the above set which includes even fewer
    # characters (esp. dots and quotes are not included)
    rpc_unsafe_charset = TextTools.set(\
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789'
        '-_()',0)

def escape(urltext,unsafe_charset=_modinit.unsafe_charset,

           ord=ord,len=len,
           setsplitx=TextTools.setsplitx,join=TextTools.join):

    """ Escape all special chars in a URL text using the %xx-encoding.

        The urltext is considered not being part of the URL itself but
        only a subpart.

        XXX Recode in C for speed.

    """
    hl = setsplitx(urltext,unsafe_charset)
    if len(hl) > 1:
        for i in range(1,len(hl),2):
            text = ''
            for c in hl[i]:
                text = text + '%%%02X' % ord(c)
            hl[i] = text
        return join(hl,'')
    return urltext

def unescape(urltext,

             charsplit=TextTools.charsplit,
             join=TextTools.join,chr=chr,atoi=string.atoi,
             irange=irange,len=len,trange=trange):

    """ Unescape a URL text part containing %xx-character encodings

        XXX Recode in C for speed.

    """
    hl = charsplit(urltext,'%')
    if len(hl) > 1:
        for i,text in irange(hl,trange(1,len(hl))):
            hl[i] = chr(atoi(text[:2],16)) + text[2:]
        return join(hl,'')
    return urltext

# Aliases
urlencode = escape
urldecode = unescape
quote = escape
unquote = unescape

def rpcencode(name,args=(),kws=None,prefix='',encode=1,

              urlencode=urlencode,join=TextTools.join,
              rpc_unsafe_charset=_modinit.rpc_unsafe_charset,
              irange=irange,tuple=tuple):

    """ Return a string encoding a call of name with the given string
        arguments given in tuple args and dict kws (may be None).

        kws may also be None if no keywords are needed.

        Arguments and keywords are converted to strings (if not
        already given as strings) and may *not* contain ',' or '='
        characters, since these are used to separate the arguments in
        the argument list.

        The resulting string is prefixed with prefix and then
        urlencoded if encode is true (default).

        The encoding scheme used looks like this:
        * no arguments: 'name()'
        * one argument: 'name(arg0)'
        * >1 argument: 'name(arg0,arg1,arg2,...)'
        * arguments and keywords: 'name(arg0,arg1,kw0=val0,kw1=val1,...)'

    """
    if args:
        arguments = map(str,args)
    else:
        arguments = []

    if kws:
        l = kws.items()
        for i,item in irange(l):
            l[i] = '%s=%s' % item
        arguments[len(arguments):] = l

    if not arguments:
        rpc = prefix+name+'()'
    else:
        rpc = '%s%s(%s)' % (prefix,name,join(arguments,','))

    if encode:
        return urlencode(rpc,unsafe_charset=rpc_unsafe_charset)
    else:
        return rpc

def rpcdecode(url,prefix='',decode=1,

              splitat=TextTools.splitat,charsplit=TextTools.charsplit,
              len=len,tuple=tuple,urldecode=urldecode):

    """ Decode a RPC encoded function/method call.

        Returns a tuple (name,args,kws) where args is a tuple of
        string arguments and kws is a dictionary containing the given
        keyword parameters or None. All parameters are returned as
        strings; it is up to the caller to decode them into
        e.g. integers, etc.

        If prefix is given and found it is removed from the name prior
        to returning it. decode can be set to false to prevent the url
        from being urldecoded prior to processing.

        The decode function also supports the syntax 'method' instead
        of 'method()' for calls without arguments.

    """
    if decode:
        url = urldecode(url)
    # Decode the method: method[(arg0,arg1,...,kw0=val0,kw1=val1,...)]
    name,rawargs = splitat(url,'(')
    if rawargs:
        # Cut out the pure argument part, ignoring any character after 
        # the final ')'
        rawargs,rest = splitat(rawargs,')',-1)
        # Argument list: split at ','
        args = charsplit(rawargs,',')
        if '=' in rawargs:
            kws = {}
            for i,arg in reverse(irange(args)):
                if '=' in arg:
                    k,v = splitat(arg,'=')
                    kws[k] = v
                    del args[i]
        else:
            kws = None
        args = tuple(args)
    else:
        args = ()
        kws = None
    if prefix:
        if name[:len(prefix)] == prefix:
            name = name[len(prefix):]
        return name,args,kws
    else:
        return name,args,kws

def queryencode(items, prefix='?',

                urlencode=urlencode,join=TextTools.join,str=str):

    """ Takes a sequence of key,value items and formats a URL encoded
        query part out of it.

        Keys and values are converted to string prior to URL
        conversion.

        prefix is prepended to the resulting string. It defaults to
        '?' so that the returned value can directly be concatenated to
        a URL.

    """
    l = []
    append = l.append
    for k,v in items:
        append(urlencode(str(k)) + '=' + urlencode(str(v)))
    return prefix + join(l, '&')

def querydecode(query,

                charsplit=TextTools.charsplit,splitat=TextTools.splitat,
                urldecode=urldecode):

    """ Decodes a query string and returns a list of items (key, value).

        If query is prefixed with a question mark ('?'), this is
        silently ignored.

        Query parts which don't provide a value will get None assigned
        as value in the items list.

    """
    if query and query[0] == '?':
        query = query[1:]
    if not query:
        return []
    pairs = charsplit(query, '&')
    items = []
    for pair in pairs:
        if '=' in pair:
            key, value = splitat(pair, '=')
            key = urldecode(key)
            value = urldecode(value)
        else:
            key = urldecode(pair)
            value = None
        items.append((key, value))
    return items

def addscheme(url,

              URL=URL):

    """ Returns the URL url with scheme added according to common
        usage.
        
        If the url already provides a scheme, nothing is changed.
        Strings are turned into URL object by the function.

        These conventions are used:
        www. -> http://www.
        ftp. -> ftp://ftp.
        [/.] -> file:[/.]
        none of these -> http://
        
    """
    url = URL(url)
    if not url.scheme:
        if url.string[:4] == 'www.':
            return url.recode(scheme='http')
        elif url.string[:4] == 'ftp.':
            return url.recode(scheme='ftp')
        elif url.string[:1] in ('/','.'):
            return url.recode(scheme='file')
        else:
            return url.recode(scheme='http')
    return url

