import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.GroupSearchTemplate import GroupSearchTemplate
from Cerebrum.web.templates.GroupViewTemplate import GroupViewTemplate
from Cerebrum.web.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
from Cerebrum.web.templates.EditGroupTemplate import EditGroupTemplate
from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url

def index(req):
    page = Main(req)
    page.menu.setFocus("group/search")
    groupsearch = GroupSearchTemplate()
    page.content = groupsearch.form
    return page

def search(req, name, desc, spread):
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
    table = html.SimpleTable(header="row")
    table.add(_("Name"), _("Description"))
    for (id, name,desc) in groups:
        desc = desc or ""
        link = url("group/view?id=%s" % id)
        link = html.Anchor(name, href=link)
        table.add(link, desc)
    if groups:    
        result.append(table)
    else:
        result.append(html.Emphasis(_("Sorry, no groups found matching the given criteria.")))
    result.append(html.Header(_("Search for other groups"), level=2))
    result.append(groupsearch.form())
    page.content = result.output().encode("utf8")
    return page    

def list(req):
    (name, desc, spread) = req.session.get('group_lastsearch',
                                           ("", "", ""))
    return search(req, name, desc, spread)

def _create_view(req, id):
    """Creates a page with a view of the group given by id, returns
       a tuple of a Main-template and a group instance"""
    server = req.session['server']
    page = Main(req)
    try:
        group = ClientAPI.Group.fetch_by_id(server, id)
        group.quarantines = group.get_quarantines()
        group.uri = req.unparsed_uri
    except:
        page.add_message(_("Could not load group with id %s") % id)
        return (page, None)

    page.menu.setFocus("group/view", id)
    view = GroupViewTemplate()
    view.add_member = lambda group:_add_box(group)
    page.content = lambda: view.viewGroup(group)
    return (page, group)

def view(req, id):
    (page, group) = _create_view(req, id)
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
    (page, group) = _create_view(req, id)
    if not group:
        return page
    if operation not in (ClientAPI.Constants.UNION, 
                         ClientAPI.Constants.INTERSECTION, 
                         ClientAPI.Constants.DIFFERENCE):
        # Display an error-message on top of page.
        page.add_message(_("%s is not a valid operation.") % operation, True)
        return page
    
    try:
        if (type == "account"):
            entity = ClientAPI.Account.fetch_by_name(server, name)
        elif (type == "group"):
            entity = ClientAPI.Group.fetch_by_name(server, name)
    except:
        page.add_message(_("Could not add non-existing member %s %s") %
                         (type, name), True)       
        return page 

    #FIXME: Operation should be constants somewhere
    try:
        group.add_member(entity, operation)
    except:    
        page.add_message(_("Could not add member %s %s to group, "
                           "already member?") % (type, name), True) 
    # Display a message stating that entity is added as group-member
    page.add_message(_("%s %s added as a member to group.") % 
                        (type, name), False)
    return page

def remove_member(req, groupid, memberid, operation):
    (page, group) = _create_view(req, groupid)
    if not group:
        return page
    group.remove_member(member_id=memberid, operation=operation)
    page.add_message(_("%s removed") % memberid)
    return page

def edit(req, id):
    server = req.session['server']
    page = Main(req)
    edit = EditGroupTemplate()
    group = ClientAPI.Group.fetch_by_id(server, id)
    edit.formvalues['name'] = group.name
    edit.formvalues['desc'] = group.description
    edit.formvalues['expire'] = str(group.expire)
    page.content = lambda: edit.form(id)
    return page

def save(req, id, name, desc, expire):
    return "eh.. %s" % name    

