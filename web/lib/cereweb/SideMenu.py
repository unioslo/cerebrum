from Menu import Menu

class SideMenu(Menu):
    def __init__(self):
        Menu.__init__(self)
        self.makePerson()
        self.makeGroup()
        self.makeRoles()
        self.makeSpread()
        self.makeOptions()
    def makePerson(self):
        self.person = self.addItem("person", "Person", "/person")
        self.person.addItem("search", "Search", "/person/search")
        self.person.addItem("list", "List", "/person/list")
        self.person.addItem("view", "View", "/person/view?id=%s")
        self.person.addItem("edit", "Edit", "/person/edit?id=%s")
        
    def makeGroup(self):    
        self.group = self.addItem("group", "Group", "/group")
        self.group.addItem("search", "Search", "/group/search")
        self.group.addItem("list", "List", "/group/list")
        self.group.addItem("view", "View", "/group/view?id=%s")
        self.group.addItem("edit", "Edit", "/group/edit?id=%s")

    def makeRoles(self):
        self.group = self.addItem("roles", "Roles", "/roles")
        self.group.addItem("search", "Search", "/roles/search")
        self.group.addItem("list", "List", "/roles/list")
        self.group.addItem("view", "View", "/roles/view?id=%s")
        self.group.addItem("edit", "Edit", "/roles/edit?id=%s")

    def makeSpread(self):
        self.group = self.addItem("spread", "Spread", "/spread")
        self.group.addItem("search", "Search", "/spread/search")
        self.group.addItem("list", "List", "/spread/list")
        self.group.addItem("view", "View", "/spread/view?id=%s")
        self.group.addItem("edit", "Edit", "/spread/edit?id=%s")

    def makeOptions(self):
        self.group = self.addItem("options", "Options", "/options")
        self.group.addItem("search", "Search", "/options/search")
        self.group.addItem("list", "List", "/options/list")
        self.group.addItem("view", "View", "/options/view?id=%s")
        self.group.addItem("edit", "Edit", "/options/edit?id=%s")

