import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.AccountSearchTemplate import AccountSearchTemplate
from Cerebrum.web.templates.AccountViewTemplate import AccountViewTemplate
from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url

def index(req):
    page = Main(req)
    page.menu.setFocus("account/search")
    accountsearch = AccountSearchTemplate()
    page.content = accountsearch.form
    return page

def search(req, name, owner, expire_date, create_date):
    page = Main(req)
    page.title = "Account search"
    page.setFocus("account/list")
    server = req.session['server']
    # Store given search parameters in search form
    formvalues = {}
    formvalues['name'] = name
    formvalues['owner'] = owner
    formvalues['expire_date'] = expire_date
    formvalues['create_date'] = create_date
    accountsearch = AccountSearchTemplate(
                       searchList=[{'formvalues': formvalues}])
    result = html.Division()
    result.append(html.Header(_("Account search results"), level=2))
    accounts = ClientAPI.Account.search(server, name or None,
                                        owner or None,
                                        expire_date or None,
                                        create_date or None)
    table = html.SimpleTable(header="row")
    table.add(_("Name"), _("Owner"))
    for (id, name, owner) in accounts:
        owner = owner or ""
        link = url("account/view?id=%s" % id)
        link = html.Anchor(name, href=link)
        table.add(link, desc)
    if accounts:    
        result.append(table)
    else:
        result.append(html.Emphasis(_("Sorry, no account(s) found matching the given criteria.")))
    result.append(html.Header(_("Search for other accounts"), level=2))
    result.append(accountsearch.form())
    page.content = result.output().encode("utf8")
    return page    


def _create_view(req, id):
    """Creates a page with a view of the account given by id, returns
       a tuple of a Main-template and an account instance"""
    server = req.session['server']
    page = Main(req)
    try:
        account = ClientAPI.Account.fetch_by_id(server, id)
    except:
        page.add_message(_("Could not load account with id %s") % id)
        return (page, None)

    page.menu.setFocus("account/view", id)
    view = AccountViewTemplate()
    page.content = lambda: view.viewAccount(account)
    return (page, account)

def view(req, id):
    (page, account) = _create_view(req, id)
    return page
