""" Get directory listing for various Internet protocols.

    XXX This submodule is still experimental.

    Copyright (c) 2001-2008, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

"""

# Python imports:
import urllib, ftplib, os, stat, exceptions
import posixpath

# Package local imports:
import URL

### FTP scheme

def ftp_listdir(ftp, url):

    path = url.path or '/'
    listing = ftp.nlst(path)
    files = []
    dirs = []
    for filename in listing:
        try:
            size = ftp.size(filename)
        except (ftplib.error_perm, ftplib.error_temp):
            size = -1
        if size >= 0:
            files.append(url + filename)
        else:
            dirs.append(url + filename)
    return dirs, files

# Cache for better performance
_ftp_cache = {}
_max_ftp_cache_size = 5

def ftp_open(url):

    connection = (url.host, url.port or ftplib.FTP_PORT, url.user, url.passwd)
    ftp = _ftp_cache.get(connection, None)
    if ftp is not None:
        if ftp._in_use:
            # Open a new connection
            ftp = None
        else:
            # Check the connection
            try:
                ftp.voidcmd('TYPE A')
            except ftplib.all_errors:
                ftp = None
    if ftp is None:
        ftp = ftplib.FTP()
        ftp.connect(url.host, url.port or ftplib.FTP_PORT)
        if url.user:
            ftp.login(url.user, url.passwd)
        else:
            # Anonymous
            ftp.login('anonymous', 'anonymous@internet.domain')
        # Manage the FTP cache
        if len(_ftp_cache) >= _max_ftp_cache_size:
            for k,v in _ftp_cache.items():
                if not v._in_use:
                    del _ftp_cache[k]
            if len(_ftp_cache) >= _max_ftp_cache_size:
                _ftp_cache.clear()
        # Note that we only store one FTP object per connection; this may
        # overwrite a previously cached version, which will then get
        # garbage collected after having finished
        _ftp_cache[connection] = ftp
    ftp._in_use = 1
    return ftp

def ftp_close(ftp):

    ftp._in_use = 0
    # Leave in cache for subsequent usage; timeouts are handled in ftp_open()

### File scheme

def file_listdir(url):

    path = url.path or '.'
    if os.path.isfile(path):
        return [], [path]
    listing = os.listdir(path)
    files = []
    dirs = []
    for filename in listing:
        if os.path.isdir(filename):
            dirs.append(url + filename)
        elif os.path.isfile(filename):
            files.append(url + filename)
    return dirs, files

### Generic API

def list(url):

    """ Returns a tuple (directories, files) providing a list of
        directory and file URLs which can be found at the
        given URL.

        The directory and file names are made absolute to URL's
        network location.

        Supported schemes are '' (no scheme = local file), 'file' and
        'ftp'.

    """
    url = URL.URL(url)
    scheme = url.scheme

    if scheme == 'ftp':
        ftp = ftp_open(url)
        try:
            values = ftp_listdir(ftp, url)
        finally:
            ftp_close(ftp)
        return values

    elif scheme == 'file' or scheme == '':
        return file_listdir(url)

    else:
        raise ValueError, 'unsupported scheme "%s"' % scheme
