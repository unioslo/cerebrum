import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.GroupSearchTemplate import GroupSearchTemplate
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

def view(req, name="test74"):
    return name + " er fint .."

