import cereconf
import os.path

def url(path):
    """Returns a full path for a path relative to the base installation.
       Example:
       url("group/search") could return "/group/search" for normal
       installations, but /~stain/group/search for test installations.
    """
    return cereconf.WEBROOT + "/" + path


def redirect(req, url, temporary=False, seeOther=False):
    """
    Immediately redirects the request to the given url. If the
    seeOther parameter is set, 303 See Other response is sent, if the
    temporary parameter is set, the server issues a 307 Temporary
    Redirect. Otherwise a 301 Moved Permanently response is issued.
    """
    from mod_python import apache

    if seeOther:
        status = apache.HTTP_SEE_OTHER
    elif temporary:
        status = apache.HTTP_TEMPORARY_REDIRECT
    else:
        status = apache.HTTP_MOVED_PERMANENTLY

    req.headers_out['Location'] = url
    req.status = status
    raise apache.SERVER_RETURN, status
    

