#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""A hierarchical menu generator for HTMLs. 
   Supports setting focus on a part of the menu and thereby
   expanding that branch. Does not use ECMAscript, relies on
   server-side.

   Example:

   >>> menu = Menu()
   >>> person = menu.addItem("person", "Person", "/person")
   >>> person.addItem("search", "Search", "/searc-person-from-hell")
   <Menu.MenuItem search>
   >>> group = menu.addItem("group", "Group", "/group")
   >>> menu.setFocus("person/search")
   >>> print menu
   <div class="menu menulevel0">
     <div class="menu menulevel1">
       <a href="/person">
         Person
       </a>
       <div class="menu menulevel2 active">
         <a href="/searc-person-from-hell">
           Search
         </a>
       </div>
     </div>
     <div class="menu menulevel1">
       <a href="/group">
         Group
       </a>
     </div>
   </div>
   
   You can add menu items that should only be displayed when a 
   specific object is focused by including %s in it's URL. To
   specify such an object, supply 'object' to setFocus().

"""

import forgetHTML as html
import sys

try:
    import unittest
except ImportError:
    unittest = None

class Menu:
    def __init__(self):
         self.name = ""
         self.children = []
         self.focus = None
         self.inFocus = False
         self.open = True
         self.highlight = False
        
    def setFocus(self,path,object=None):
        """Expands and highlights relevant menu items. 

           path -- a string denoting which part of the menu
             is focused, "person/search" will open the branch
             "person" and highlight the item named "search". The 
             names used are the ones supplied as "name" to 
             menu items.
          
           object -- optional focused object, URLs containing
             %s will call object.urlReference() to replace the
             %s. If object is not given, such items will not
             be included. If object is of type str, it will be
             inserted directly.
        """
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
        """Generates the HTML objects from the given focus.
           Could return None if nothing to show."""
        div = html.Division()
        div['class'] = "menu menulevel%s" % level
        if self.highlight:
            div['class'] += " active"
        if self.open or self.inFocus:
            for child in self.children:
                result = child.output(level+1)
                if result:
                    div.append(result)
        return div

    def __str__(self):
        return str(self.output())    
    
    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.name)
    
    def __call__(self):
        return str(self)    

class MenuItem(Menu):                
    def __init__(self,name,label,url):
         Menu.__init__(self)
         self.name = name
         self.label = label
         self.url = url
         self.open = False
         
    def getUrl(self):     
        """Expands any %s and returns the url. 
           Returns None if the URL can't be expanded."""
        url = self.url
        focus = self.focus
        if url.count("%s") <> 1:
            return url
        if focus is None:
            # We can't expand %s without focus object
            return None
        if type(focus) != str:
            focus = focus.urlReference()    
        url = url % focus    
        return url          

    def output(self,level=0):
        div = Menu.output(self, level)
        url = self.getUrl()
        if url is None:
            # we can't use this item without a link
            return None
        link = html.Anchor(self.label, href=url)
        # Dirty trick to insert at the beginning
        # of the div.
        div._content.insert(0, link)
        return div

if unittest:
    class TestMenuItem(unittest.TestCase):            
        def setUp(self):
            self.item = MenuItem("group", "Group", "/mygroup")

        def testAttributes(self):
            item = self.item
            self.assertEqual(item.name, "group")
            self.assertEqual(item.label, "Group")
            self.assertEqual(item.url, "/mygroup")
            # Should NOT be expanded
            self.assertEqual(item.getUrl(), item.url)

        def testOutput(self):
            output = str(self.item)
            self.assertEqual(output,
"""<div class="menu menulevel0">
  <a href="/mygroup">
    Group
  </a>
</div>
""")
    class TestMenuItemExpansion(unittest.TestCase):
        def setUp(self):
            self.item = MenuItem("group", "Group", 
                            "/mygroup?id=%s")

        def testExpandedUrlIgnore(self):
            # Should ignore this item
            self.assertEqual(self.item.getUrl(), None)

        def testExpandedUrlString(self):
            # Should expand string
            self.item.setFocus("group", "76")
            self.assertEqual(self.item.getUrl(), "/mygroup?id=76")

        def testExpandedUrlObject(self):
            class MyObject:
                def urlReference(self):
                    """Returns an integer that should be expanded"""
                    return 745
            myObject = MyObject()
            # Remember to test the test! =)
            self.assertEqual(myObject.urlReference(), 745)
            self.item.setFocus("group", myObject)
            self.assertEqual(self.item.getUrl(), "/mygroup?id=745")
            

    class TestMenu(unittest.TestCase):
        def setUp(self):
            self.menu = Menu()
        def testOutput(self):
            output = str(self.menu)
            # Notice that forgetHTML closes the 
            # <div /> tag when lacking content
            self.assertEqual(output, 
                '<div class="menu menulevel0" />\n')
        def testOutputLevel(self):
            """Makes sure that leveling is intact"""
            output = str(self.menu.output(2))
            self.assertEqual(output, 
                '<div class="menu menulevel2" />\n')
        def testAddItem(self):
            item = self.menu.addItem("person", "Person", "/myperson")
            self.assertEqual(item.__class__, MenuItem)
            self.assertEqual(item.name, "person")
            self.assertEqual(item.label, "Person")
            self.assertEqual(item.url, "/myperson")
        def testAddMenuItem(self):
            item = MenuItem("group", "Group", "/mygroup")
            self.menu.addMenuItem(item)
            self.assertEqual(self.menu.children, [item])

    class TestMenuChildren(unittest.TestCase):
        def setUp(self):
            self.menu = Menu()
            self.menu.addItem("person", "Person", "/myperson")
            self.menu.addItem("group", "Group", "/mygroup")
            self.menu.addItem("extra", "Extra", "/myextra")
        def testIsOpen(self):
            """The root menu should always be open"""
            output = str(self.menu)       
            self.assertEqual(output,
"""<div class="menu menulevel0">
  <div class="menu menulevel1">
    <a href="/myperson">
      Person
    </a>
  </div>
  <div class="menu menulevel1">
    <a href="/mygroup">
      Group
    </a>
  </div>
  <div class="menu menulevel1">
    <a href="/myextra">
      Extra
    </a>
  </div>
</div>
""")
        def testSelection(self):
            self.menu.setFocus("group")
            output = str(self.menu)
            self.assertEqual(output, 
"""<div class="menu menulevel0">
  <div class="menu menulevel1">
    <a href="/myperson">
      Person
    </a>
  </div>
  <div class="menu menulevel1 active">
    <a href="/mygroup">
      Group
    </a>
  </div>
  <div class="menu menulevel1">
    <a href="/myextra">
      Extra
    </a>
  </div>
</div>
""")

            
    class TestMenuBranches(unittest.TestCase):
        def setUp(self):
            self.menu = Menu()
            person = self.menu.addItem("person", "Person", "/myperson")
            group = self.menu.addItem("group", "Group", "/mygroup")
            extra = self.menu.addItem("extra", "Extra", "/myextra")
            person.addItem("search", "Search", "/myperson/search")
            person.addItem("list", "List", "/myperson/list")
            group.addItem("add", "Add", "/mygroup/add")
            group.addItem("delete", "Delete", "/mygroup/delete")
            extra.addItem("help", "Help", "/help")
        def testNotExpanded(self):
            output = str(self.menu)
            self.assertEqual(output, 
"""<div class="menu menulevel0">
  <div class="menu menulevel1">
    <a href="/myperson">
      Person
    </a>
  </div>
  <div class="menu menulevel1">
    <a href="/mygroup">
      Group
    </a>
  </div>
  <div class="menu menulevel1">
    <a href="/myextra">
      Extra
    </a>
  </div>
</div>
""")
        def testExpanded(self):
            """Group items and only group items should be shown"""
            self.menu.setFocus("group")
            output = str(self.menu)
            self.assertEqual(output, 
"""<div class="menu menulevel0">
  <div class="menu menulevel1">
    <a href="/myperson">
      Person
    </a>
  </div>
  <div class="menu menulevel1 active">
    <a href="/mygroup">
      Group
    </a>
    <div class="menu menulevel2">
      <a href="/mygroup/add">
        Add
      </a>
    </div>
    <div class="menu menulevel2">
      <a href="/mygroup/delete">
        Delete
      </a>
    </div>
  </div>
  <div class="menu menulevel1">
    <a href="/myextra">
      Extra
    </a>
  </div>
</div>
""")
        def testDeepFocus(self):
            """Expand, but only the deepest item should be active"""
            self.menu.setFocus("person/list")
            output = str(self.menu)
            self.assertEqual(output, 
"""<div class="menu menulevel0">
  <div class="menu menulevel1">
    <a href="/myperson">
      Person
    </a>
    <div class="menu menulevel2">
      <a href="/myperson/search">
        Search
      </a>
    </div>
    <div class="menu menulevel2 active">
      <a href="/myperson/list">
        List
      </a>
    </div>
  </div>
  <div class="menu menulevel1">
    <a href="/mygroup">
      Group
    </a>
  </div>
  <div class="menu menulevel1">
    <a href="/myextra">
      Extra
    </a>
  </div>
</div>
""")
        
if __name__ == "__main__":
    if unittest is None:
        print "unittest module must be installed to run tests"
        sys.exit(1)    
    unittest.main()        
                            

# arch-tag: 516a49d6-a4ad-4256-bcff-7de494d3e6dc
