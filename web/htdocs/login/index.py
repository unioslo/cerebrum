
from mod_python.Session import Session
from mod_python import apache
from mod_python import util
import forgetHTML as html

from Cerebrum.client.ServerConnection import ServerConnection

def index(req, user="", password=""):
    # Do this ourself since we are invoked by 
    # mod_python.publisher instead of Cerebrum.web.publisher
    req.session = Session(req)
    error = user
    if user:
        error = "Login"
        try:
            server = ServerConnection(user, password)
        except Exception, e:
            error = str(e)
            error = error.replace("<", "")
            error = error.replace(">", "")
        else:
            req.session['server'] = server     
            req.session.save()
            util.redirect(req, "http://garbageman.itea.ntnu.no/~stain/")
        
    doc = html.SimpleDocument("Log in to Cerebrum")
    body = doc.body
    body.append(html.Paragraph("Cerebrum is powered by 230V"))
    if error:
        body.append(html.Paragraph(error, style="color: red;"))
    form = html.SimpleForm(method="POST")
    body.append(form)
    form.addText("user", "Username", user)
    form.addText("password", "Password", password)
    form.append(html.Submit("Login"))
    return doc
    

