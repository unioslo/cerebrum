import forgetHTML as html

class Menu:
    def __init__(self):
         self.name = ""
         self.children = []
         self.focus = None
         self.open = True
         self.highlight = False

    def setFocus(self,path,object=None):
        """expands relevant menu items
           focus is either a class (ie Person or Group) or an instance of such a class
           if focus is None nothing is expanded"""
        self.focus = object
        if self.name == "":
            # Avoid splitting for the root element
            root = ""
            subpath = path
        elif path.count("/"):
            (root, subpath) = path.split("/", 1)
        else:
            root = path
            subpath = ""    
        self.highlight = False # No one is highlighted per default
        if root == self.name:
            self.inFocus = True
            if not subpath:
                self.highlight = True
        else:
            self.inFocus = False
            subpath = "" # Make sure no children are focused
            
        for child in self.children:
            child.setFocus(subpath, object)    
            
    def addMenuItem(self, menuitem):
        """Adds a menu item"""
        self.children.append(menuitem)        
    
    def addItem(self, *args):
        """Creates a menu item, adds it, and returns it"""
        item = MenuItem(*args)
        self.addMenuItem(item)
        return item

    def output(self,level=0):
        """return html menu"""
        div = html.Division()
        div['class'] = "menu menulevel%s" % level
        if self.highlight:
            div['class'] += " active"
        if self.open or self.inFocus:
            for child in self.children:
                div.append(child.output(level+1)) 
        return div

    def __str__(self):
        return str(self.output())    

class MenuItem(Menu):                
    def __init__(self,name,label,url):
         Menu.__init__(self)
         self.name = name
         self.label = label
         self.url = url
         self.open = False
    def output(self,level=0):
        div = Menu.output(self, level)
        link = html.Anchor(self.label, href=self.url)
        # Dirty trick to insert at the beginning
        # of the div.
        div._content.insert(0, link)
        return div
        
     
# >>> menu = Menu()
# >>> person = menu.addItem("person", "Person", "/person")
# >>> person.addItem("search", "Søk", "/searc-person-from-hell")
# >>> group = menu.addItem("group", "Group", "/group")
# >>> menu.setFocus("person/search")
# >>> print menu
# <div class="menu menulevel0">
#   <div class="menu menulevel1">
#     <a href="/person">
#       Person
#     </a>
#     <div class="menu menulevel2 active">
#       <a href="/searc-person-from-hell">
#         Søk
#       </a>
#     </div>
#   </div>
#   <div class="menu menulevel1">
#     <a href="/group">
#       Group
#     </a>
#   </div>
# </div>
# 
