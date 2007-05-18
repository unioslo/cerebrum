====================
Development tutorial
====================

Tutorial
========
* This tutorial will show how to extend cereweb.

Main
----
We wish to create a page for the url "cereweb/dummy/dummy_page".

First we need to create a new module named "dummy" in the directory
<cereweb\htdocs\>. To expose methods in the new module import it in the
index module <cereweb\htdocs\index.py> with "import dummy".

Inside the new module we need the following imports::

    import cherrypy
    from lib.Main import Main
    from lib.utils import transaction_decorator, commit_url

We create the method "dummy_page" with adding the following method and
code::

    def dummy_page():
        pass
    dummy_page.exposed = True

If the page interacts with our spine-server we need some extra code::

    def dummy_page(transaction):
        pass
    dummy_page = transaction_decorator(dummy_page)
    dummy_page.exposed = True

This automatically creates a new transaction for this method-call, which
will be rolled back if not committed when finished. To commit changes
done in the transaction use the commit_url()-method we imported earlier::

    commit_url(transaction, "dummy/dummy_page", msg="commit message")

If you need to access the page-request, the server-response or the session
its exposed in the cherrypy-module as cherrypy.request, cherrypy.response
or cherrypy.session::

    cherrypy.session['user_host'] = cherrypy.request.remote_host

Whatever our new method returns will be presented to our user::

    def dummy_page():
        return "Your host is %s" % cherrypy.request.remote_host
    dummy_page.exposed = True

To return a page with the standard cereweb-ui (with menus and more) return
an instance of the Main-class we imported earlier::

    def dummy_page():
        page = Main()
	page.title = "Dummy page"
	page.setFocus("dummy/dummy_page")
	page.content = lambda: "this is the content of the page we return"
	return page
    dummy_page.exposed = True


Html template
-------------
If the page you wish to present to the user contains lot of html, 
cheetah-templates let you mix python code inside html-files easily.

Create the file DummyPageTemplate.tmpl in <cereweb\lib\templates\>.
Use the template inside your dummy-module with the following code::

    def dummy_page():
        page = Main()
	......
	template = DummyPageTemplate()
        page.content = lambda: template.method(args)
        return page
    dummy_page.exposed = True


Javascript
----------
If your page needs javascript place your javascript-file in 
<cereweb\htdocs\jscript\>, and use the following code in your module::

    def dummy_page():
        page = Main()
	page.add_jscript("filename.js")
	....
    dummy_page.exposed = True

Cascade style sheets
--------------------
Css-files are placed in <cereweb\htdocs\css\>, and uses cheetah-templates
too. Add your css code to the styles.tmpl file or create your own css-file.

..
   arch-tag: 543d2da8-ce52-11da-8653-3805d70f470b
