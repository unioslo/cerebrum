import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.PersonSearchTemplate import PersonSearchTemplate
from Cerebrum.web.templates.PersonCreateTemplate import PersonCreateTemplate
from Cerebrum.web.templates.PersonViewTemplate import PersonViewTemplate
from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url
from Cerebrum.web import profile
import xmlrpclib

def index(req):
    page = Main(req)
    page.menu.setFocus("person/search")
    personsearch = PersonSearchTemplate()
    page.content = personsearch.form
    return page


def create(req, name="", birthno="", birthdate="", ou="", affiliation="", aff_status=""):
    page = Main(req)
    page.title = "Person create"
    page.setFocus("person/create")
    server = req.session['server']
    # Store given create parameters in create-form
    formvalues = {}
    formvalues['name'] = name
    formvalues['birthno'] = birthno
    formvalues['birthdate'] = birthdate
    formvalues['ou'] = ou
    formvalues['affiliation'] = affiliation
    formvalues['aff_status'] = aff_status
    personcreate = PersonCreateTemplate(
                        searchList=[{'formvalues': formvalues}])

    result = html.Division()

    if name and birthno and birthdate and  \
        ou and affiliation and aff_status:
        person = ClientAPI.Person.create(server, name, birthno, 
                                        birthdate, ou, 
                                        affiliation, aff_status)
 
        if person:
            #Display some text about "Person created...", maybe jump to viewing that user?
            table = html.SimpleTable(header="row")
            table.add(_("Name"), _("Date of birth"))
            link = url("person/view?id=%s" % person.id)
            link = html.Anchor(person.name, href=link)
            table.add(link, person.birthdate.Format("%Y-%m-%d"))
            result.append(table)
        elif person==None:
            page.add_message(_("Sorry, person not created because of an error"), True)
        
    result.append(personcreate.form())
    page.content = lambda: result.output().encode("utf8")
    return page

def list(req):
    (name, accountid, birthno, birthdate) = \
        req.session.get('person_lastsearch', ("", "", "", ""))
    return search(req, name, accountid, birthno, birthdate)


def search(req, name="", accountid="", birthno="", birthdate=""):
    req.session['person_lastsearch'] = (name, accountid, 
                                         birthno, birthdate)
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

    try:
        persons = ClientAPI.Person.search(server, name or None,
                                          accountid or None,
                                          birthno or None,
                                          birthdate or None)
        
        if persons:
            table = html.SimpleTable(header="row")
            table.add(_("Name"), _("Date of birth"))
            for person in persons:
                link = url("person/view?id=%s" % person.id)
                link = html.Anchor(person.name, href=link)
                table.add(link, person.birthdate.Format("%Y-%m-%d"))
            result.append(table)
        else:
            page.add_message(_("Sorry, no person(s) found matching the given criteria."))

    except xmlrpclib.Fault, e:
        page.add_message(e.faultString.split("CerebrumError: ")[-1], True)
        
    result.append(html.Header(_("Search for other persons"), level=2))
    result.append(personsearch.form())
    page.content = lambda: result.output().encode("utf8")
    return page    


def _create_view(req, id):
    """Creates a page with a view of the person given by id, returns
       a tuple of a Main-template and a person instance"""
    server = req.session['server']
    page = Main(req)
    try:
        person = ClientAPI.Person.fetch_by_id(server, id)
    except:
        page.add_message(_("Could not load person with id %s") % id)
        return (page, None)

    page.menu.setFocus("person/view", id)
    view = PersonViewTemplate()
    page.content = lambda: view.viewPerson(person, req.session['profile'])
    return (page, person)

def view(req, id):
    (page, person) = _create_view(req, id)
    return page
