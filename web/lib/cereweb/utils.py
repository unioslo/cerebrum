import cereconf
import os.path
from Cerebrum.client import AbstractModel

def url(path):
    """Returns a full path for a path relative to the base installation.
       Example:
       url("group/search") could return "/group/search" for normal
       installations, but /~stain/group/search for test installations.
    """
    return cereconf.WEBROOT + "/" + path

_object_type_url_map = {
    AbstractModel.Account:      "account",
    AbstractModel.Group:        "group",
    AbstractModel.Person:       "person",
    #AbstractModel.OU:           "ou", 
    AbstractModel.Quarantine:   "quarantine",
}

def object_url(object, method="view"):
    """Returns the full path to a page treating the object.
       Method could be "view" (the default), "edit" and 
       other things."""
    # You might catch special cases here before the for-loop   
    for (type, path) in _object_type_url_map.items():
        if isinstance(object, type):
            return url("%s/%s/?id=%s" % 
                       (path, method, object.id))
    raise "Unknown object %r" % object

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
    

