import cereconf
import os.path
from Cerebrum.client import AbstractModel
from Cerebrum.Errors import ProgrammingError
import forgetHTML

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

def object_link(object, text=None, method="view"):
    """Creates a HTML anchor (a href=..) for the object.
       The text of the anchor will be str(object) - unless
       the parameter text is given."""
    url = object_url(object, method)   
    if text is None:
        text = str(object)
    return forgetHTML.Anchor(text, href=url)        

def redirect(req, url, temporary=False, seeOther=False):
    """
    Immediately redirects the request to the given url. If the
    seeOther parameter is set, 303 See Other response is sent, if the
    temporary parameter is set, the server issues a 307 Temporary
    Redirect. Otherwise a 301 Moved Permanently response is issued.

    General use:
        After a POST request you want to revert to the normal viewing:
            seeOther=True
        Some general style url, like entity/view?id=29, really should
        mean somewhere else, ie. group/view?id=29:
            the defaults (permanent redirect)
        An error occured, and you want to go to some default page
            temporary=True    
    """
    from mod_python import apache

    if temporary and seeOther:
        raise ProgrammingError, \
              "cannot set both temporary and seeOther"
    elif seeOther:
        status = apache.HTTP_SEE_OTHER
    elif temporary:
        status = apache.HTTP_TEMPORARY_REDIRECT
    else:
        status = apache.HTTP_MOVED_PERMANENTLY

    req.headers_out['Location'] = url
    req.status = status
    raise apache.SERVER_RETURN, status
    
def redirect_object(req, object, method="view", 
                    temporary=False, seeOther=False):
    """Redirects to the given object. 
       This is shorthand for calling object_url and redirect 
       in succession. See the respecting methods for
       explanation of the parameters.
    """                 
    url = object_url(object, method)                   
    redirect(req, url, temporary, seeOther)

def queue_message(req, message, error=False):
    """Queues a message for display next time a Main-page is showed.
       If error is true, the message will be indicated as such."""
    session = req.session
    if not session.has_key("messages"):
        session['messages'] = []
    session['messages'].append((message, error))
               
def no_cache(req):
    """Makes the current request non-cachable"""
    req.headers_out.add("Cache-Control:","no-cache")
    req.headers_out.add("Pragma:","no-cache")
