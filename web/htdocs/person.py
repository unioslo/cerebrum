import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.PersonSearchTemplate import PersonSearchTemplate
#from Cerebrum.web.templates.GroupViewTemplate import GroupViewTemplate
#from Cerebrum.web.templates.GroupAddMemberTemplate import GroupAddMemberTemplate
#from Cerebrum.web.templates.EditGroupTemplate import EditGroupTemplate
from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url

def index(req):
    page = Main(req)
    page.menu.setFocus("person/search")
    personsearch = PersonSearchTemplate()
    page.content = personsearch.form
    return page

def search(req, name, accountid, birthno, birthdate):
    page = Main(req)
    page.title = "Person search"
    page.setFocus("person/list")
    server = req.session['server']
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['accountid'] = accountid
    formvalues['birthno'] = birthno
    formvalues['birthdate'] = birthdate
    personsearch = PersonSearchTemplate(
                       searchList=[{'formvalues': formvalues}])
    result = html.Division()
    result.append(html.Header(_("Person search results"), level=2))
    persons = ClientAPI.Person.search(server, name or None,
                                    accountid or None,
                                    birthno or None,
                                    birthdate or None)
    table = html.SimpleTable(header="row")
    table.add(_("Name"), _("Description"))
    for (id, name, desc) in persons:
        desc = desc or ""
        link = url("person/view?id=%s" % id)
        link = html.Anchor(name, href=link)
        table.add(link, desc)
    if persons:    
        result.append(table)
    else:
        result.append(html.Emphasis(_("Sorry, no person(s) found matching the given criteria.")))
    result.append(html.Header(_("Search for other persons"), level=2))
    result.append(personsearch.form())
    page.content = result
    return page    
