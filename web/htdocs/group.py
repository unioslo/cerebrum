import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.GroupSearchTemplate import GroupSearchTemplate
from Cerebrum.web.templates.GroupViewTemplate import GroupViewTemplate
from Cerebrum.web.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
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
    page = Main(req)
    page.menu.setFocus("group/list")
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
        link = url("group/view?name=%s" % name)
        link = html.Anchor(name, href=link)
        table.add(link, desc)
    if groups:    
        result.append(table)
    else:
        result.append(html.Emphasis(_("Sorry, no groups found matching the given criteria.")))
    result.append(html.Header(_("Search for other groups"), level=2))
    result.append(groupsearch.form())
    page.content = result
    return page    

def view(req, name):
    page = Main(req)
    page.menu.setFocus("group/view", name)
    server = req.session['server']
    group = ClientAPI.Group.fetch_by_name(name, server)
    view = GroupViewTemplate()
    view.add_member = lambda group:_add_box(group)
    page.content = lambda: view.viewGroup(group)
    return page
    
def _add_box(group):
    operations = [(ClientAPI.Constants.JOIN, _("Union")), 
                  (ClientAPI.Constants.INTERSECTION, _("Intersection")), 
                  (ClientAPI.Constants.DIFFERENCE, _("Difference"))]
    member_types = [("account", _("Account")),
                    ("group", _("Group"))]
    action = url("group/add_member?id=%s" % group.id)

    template = GroupAddMemberTemplate()
    return template.add_member_box(action, member_types, operations)

def add_member(req, id, name, type, operation):
    server = req.session['server']
    
    page = view(req, name)
    if operation not in (ClientAPI.Constants.JOIN, 
                         ClientAPI.Constants.INTERSECTION, 
                         ClientAPI.Constants.DIFFERENCE):
        # Display an error-message on top of page.
        page.add_message(_("%s is not a valid operation." % operation), true)
        return page
    
    group = ClientAPI.Group.fetch_by_id(server, id)
    if (type == "account"):
        entity = ClientAPI.Account.fetch_by_name(server, name)
    elif (type == "group"):
        entity = ClientAPI.Group.fetch_by_name(server, name)

    #FIXME: Operation should be constants somewhere
    group.add_member(entity, operation)
   
    # Display a message stating that entity is added as group-member
    page.add_message(_("%s added as a member to group." % name), false)
    return page
