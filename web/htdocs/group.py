import cerebrum_path
import forgetHTML as html
from Cerebrum import Errors
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.GroupSearchTemplate import GroupSearchTemplate
from Cerebrum.web.templates.GroupViewTemplate import GroupViewTemplate
from Cerebrum.web.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
from Cerebrum.web.templates.GroupEditTemplate import GroupEditTemplate
from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url
from Cerebrum.web.utils import queue_message
from Cerebrum.web.utils import redirect_object
from Cerebrum.web.utils import redirect
from Cerebrum.web.utils import no_cache
from mx import DateTime

def index(req):
    page = Main(req)
    page.menu.setFocus("group/search")
    groupsearch = GroupSearchTemplate()
    page.content = groupsearch.form
    return page

def search(req, name="", desc="", spread=""):
    req.session['group_lastsearch'] = (name, desc, spread)
    page = Main(req)
    page.title = _("Group search")
    page.setFocus("group/list")
    server = req.session['server']
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['desc'] = desc
    formvalues['spread'] = spread
    groupsearch = GroupSearchTemplate(
                       searchList=[{'formvalues': formvalues}])
    result = html.Division()
    result.append(html.Header(_("Group search results"), level=2))
    groups = ClientAPI.Group.search(server, spread or None, 
                                    name or None, 
                                    desc or None)
    table = html.SimpleTable(header="row", _class="results")
    table.add(_("Name"), _("Description"))
    for (id, name,desc) in groups:
        desc = desc or ""
        link = url("group/view?id=%s" % id)
        link = html.Anchor(name, href=link)
        table.add(link, desc)
    
    if groups:    
        result.append(table)
    else:
        page.add_message(_("Sorry, no groups found matching " \
                           "the given criteria."), error=True)
        
    result.append(html.Header(_("Search for other groups"), level=2))
    result.append(groupsearch.form())
    page.content = lambda: result.output()
    return page    

def list(req):
    no_cache(req)
    (name, desc, spread) = req.session.get('group_lastsearch',
                                           ("", "", ""))
    return search(req, name, desc, spread)

def _get_group(req, id):
    server = req.session['server']
    try:
        return ClientAPI.Group.fetch_by_id(server, int(id))
    except Exception, e:
        queue_message(req, _("Could not load group with id=%s") % id, 
                      error=True)
        queue_message(req, str(e), error=True)
        # Go back to the root of groups, raise redirect-error.
        redirect(req, url("group"), temporary=True)
        raise Errors.UnreachableCodeError

def view(req, id):
    page = Main(req)
    group = _get_group(req, id)
    page.menu.setFocus("group/view", id)
    view = GroupViewTemplate()
    view.add_member = lambda group:_add_box(group)
    page.content = lambda: view.viewGroup(group)
    return page
    
def _add_box(group):
    operations = [(ClientAPI.Constants.UNION, _("Union")), 
                  (ClientAPI.Constants.INTERSECTION, _("Intersection")), 
                  (ClientAPI.Constants.DIFFERENCE, _("Difference"))]
    member_types = [("account", _("Account")),
                    ("group", _("Group"))]
    action = url("group/add_member?id=%s" % group.id)

    template = GroupAddMemberTemplate()
    return template.add_member_box(action, member_types, operations)

def add_member(req, id, name, type, operation):
    server = req.session['server']
    group = _get_group(req, id)
    if operation not in (ClientAPI.Constants.UNION, 
                         ClientAPI.Constants.INTERSECTION, 
                         ClientAPI.Constants.DIFFERENCE):
        # Display an error-message on top of page.
        queue_message(req, _("%s is not a valid operation.") % 
                           operation, error=True)
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError
    
    try:
        if (type == "account"):
            entity = ClientAPI.Account.fetch_by_name(server, name)
        elif (type == "group"):
            entity = ClientAPI.Group.fetch_by_name(server, name)
    except:
        queue_message(req, _("Could not add non-existing member %s %s") %
                         (type, name), error=True)       
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError

    #FIXME: Operation should be constants somewhere
    try:
        group.add_member(entity, operation)
    except:    
        queue_message(req, _("Could not add member %s %s to group, "
                      "already member?") % (type, name), error=True) 
    # Display a message stating that entity is added as group-member
    queue_message(req, (_("%s %s added as a member to group.") % 
                        (type, name)))
    redirect_object(req, group, seeOther=True)
    raise Errors.UnreachableCodeError

def remove_member(req, groupid, memberid, operation):
    group = _get_group(req, groupid)
    group.remove_member(member_id=memberid, operation=operation)
    queue_message(req, _("%s removed from group %s") % (memberid, group))
    redirect_object(req, group, seeOther=True)
    raise Errors.UnreachableCodeError

def edit(req, id):
    group = _get_group(req, id)
    page = Main(req)
    page.menu.setFocus("group/edit")
    edit = GroupEditTemplate()
    edit.formvalues['name'] = group.name
    edit.formvalues['desc'] = group.description
    if group.expire_date:
        edit.formvalues['expire_date'] = group.expire_date.Format("%Y-%m-%d")
    else:
        edit.formvalues['expire_date'] = ""    
    page.content = lambda: edit.form(id)
    return page

def create(req):
    page = Main(req)
    page.menu.setFocus("group/create")
    edit = GroupEditTemplate()
    page.content = edit.form
    return page

def save(req, id, name, desc, expire_date):
    if not(id):
        server = req.session['server']
        group = ClientAPI.Group.create(server, name, desc)
        redirect_object(req, group, seeOther=True)
        raise Errors.UnreachableCodeError
    
    group = _get_group(req, id)
    
    if name != group.name:
        #FIXME: Do something, maybe...
        queue_message(req, 
                      _("Sorry, cannot not change group name yet"), 
                      error=True)
    
    if expire_date:
        # Expire date is set, check if it's changed...
        expire_date = DateTime.DateFrom(expire_date)
        if group.expire_date != expire_date:
            group.set_expire_date(expire_date)
            queue_message(req, _("Set expiration date to %s") %
                            expire_date.Format("%Y-%m-%d"))
    else:
        # No expire_date date set, check if it's to be removed
        if group.expire_date:
            group.set_expire_date(None)
            queue_message(req, _("Removed expiration date"))

    if desc != group.description:
        #FIXME: Do something, maybe...
        queue_message(req, 
                      _("Sorry, cannot not change description yet"), 
                      error=True)

    redirect_object(req, group, seeOther=True)
    raise Errors.UnreachableCodeError
