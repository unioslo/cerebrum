from Menu import Menu

class SideMenu(Menu):
    def __init__(self):
        Menu.__init__(self)
        self.makePerson()
        self.makeGroup()
        self.makeSpread()
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

    def makeSpread(self):
        self.group = self.addItem("spread", "spread", "/spread")
        self.group.addItem("search", "Search", "/spread/search")
        self.group.addItem("list", "List", "/spread/list")
        self.group.addItem("view", "View", "/spread/view?id=%s")
        self.group.addItem("edit", "Edit", "/spread/edit?id=%s")

