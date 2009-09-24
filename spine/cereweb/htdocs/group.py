# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import cherrypy
import string
import mx.DateTime

from gettext import gettext as _
from lib.utils import queue_message, redirect_entity, entity_link
from lib.utils import transaction_decorator, redirect, get_database
from lib.utils import web_to_spine, session_required_decorator
from lib.GroupSearcher import GroupSearcher
from lib.templates.GroupViewTemplate import GroupViewTemplate
from lib.templates.GroupCreateTemplate import GroupCreateTemplate
from Cerebrum.Errors import NotFoundError

from lib.data.EntityFactory import EntityFactory
from lib.data.GroupDAO import GroupDAO
from lib.data.EntityDAO import EntityDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.HostDAO import HostDAO
from lib.data.GroupDTO import GroupDTO

from lib.GroupSearchForm import GroupSearchForm

@session_required_decorator
def search(**vargs):
    """Search for groups and displays results and/or searchform."""
    searcher = GroupSearcher(**vargs)
    return searcher.respond()
search.exposed = True
index = search

@session_required_decorator
def view(id, **vargs):
    """Creates a page with the view of the group with the given id."""
    db = get_database()
    page = GroupViewTemplate()
    page.group = GroupDAO(db).get(id, include_extra=True)
    page.group.traits = []
    page.group.history = HistoryDAO(db).get_entity_history_tail(id)
    page.visibilities = ConstantsDAO(db).get_group_visibilities()
    page.spreads = ConstantsDAO(db).get_group_spreads()
    page.email_target_types = ConstantsDAO(db).get_email_target_types()
    page.email_servers = HostDAO(db).get_email_servers()
    page.targets = HostDAO(db).get_email_targets(id)
    
    return page.respond()
view.exposed = True
    
@session_required_decorator
def join_group(entity_id, group_name, selected_id=None, **kwargs):
    db = get_database()
    dao = GroupDAO(db)

    if selected_id is None:
        selected_id = get_selected_id(group_name, 'group')

    if selected_id is None:
        msg = _("Group '%s' not found") % group_name
        queue_message(msg, True, entity_link(entity_id), title="Not Found")
        redirect_entity(entity_id)

    dao.add_member(entity_id, selected_id)
    db.commit()

    msg = _('Joined group %s successfully') % group_name
    queue_message(msg, True, entity_link(entity_id), title="Joined group")
    redirect_entity(entity_id)
join_group.exposed = True

@session_required_decorator
def add_member(group_id, member_name, member_type, selected_id=None, **kwargs):
    """Add a member to a group."""
    db = get_database()
    
    if not selected_id:
        selected_id = get_selected_id(member_name, member_type)

    if not selected_id:
        msg = _("Member '%s' not found") % member_name
        queue_message(msg, True, entity_link(group_id), title="Not Found")
        redirect_entity(group_id)

    GroupDAO(db).add_member(selected_id, group_id)
    db.commit()

    msg = _("%s added as a member to group.") % member_name
    queue_message(msg, True, entity_link(group_id), title="Joined group")
    redirect_entity(group_id)
add_member.exposed = True
    
@session_required_decorator
def remove_member(group_id, member_id):
    db = get_database()
    member = EntityDAO(db).get(member_id)
    GroupDAO(db).remove_member(group_id, member_id)
    db.commit()

    msg = _("%s removed from group.") % member.name
    queue_message(msg, True, entity_link(member_id), title="Removed member")
    redirect_entity(group_id)
remove_member.exposed = True

@session_required_decorator
def create(name="", expire="", description=""):
    """Creates a page with the form for creating a group."""
    page = GroupCreateTemplate()
    page.title = _("Group")
    page.set_focus('group/create')

    page.data = {
        'name': name,
        'expire': expire,
        'description': description,
    }
    
    return page.respond()
create.exposed = True

@session_required_decorator
def save(id, name, expire, description, visi, gid=None):
    valid, error_msg = validate(name, description, expire)

    if not valid:
        queue_message(error_msg, error=True, title=_("Save failed"))
        return redirect_entity(group.id)

    db = get_database()
    dao = GroupDAO(db)
    group = dao.get_shallow(id)
    populate(group, name, description, expire, visibility=visi)
    populate_posix(group, gid)
    dao.save(group)
    db.commit()

    queue_message(
        _("Group successfully updated."),
        link=entity_link(group.id),
        title=_("Changed group"))

    redirect_entity(group.id)
save.exposed = True

@session_required_decorator
def make(name, description, expire):
    """Performs the creation towards the server."""
    valid, error_msg = validate(name, description, expire)
    if not valid:
        queue_message(error_msg, error=True, title=_("Creation failed"))
        return redirect('/group/create')

    group = GroupDTO()
    populate(group, name, description, expire)

    db = get_database()
    GroupDAO(db).add(group)
    db.commit()
    
    if not valid:
        queue_message(error_msg, error=True, title=_("Creation failed"))
        return redirect('/group/create')
        
    msg = _("Group successfully created.")
    queue_message(msg, title=_("Group created"))
    redirect_entity(group.id)
make.exposed = True

@session_required_decorator
def posix_promote(id):
    db = get_database()
    GroupDAO(db).promote_posix(id)
    db.commit()
    
    msg = _("Group successfully promoted to posix.")
    queue_message(msg, title=_("Group promoted"))
    redirect_entity(id)
posix_promote.exposed = True

@session_required_decorator
def posix_demote(id):
    db = get_database()
    GroupDAO(db).demote_posix(id)
    db.commit()

    msg = _("Group successfully demoted from posix.")
    queue_message(msg, title=_("Group demoted"))
    redirect_entity(id)
posix_demote.exposed = True

@session_required_decorator
def delete(id):
    """Delete the group from the server."""
    db = get_database()
    dao = GroupDAO(db)
    group = dao.get_entity(id)
    dao.delete(id)
    db.commit()

    msg = _("Group '%s' successfully deleted.") % group.name
    queue_message(msg, title=_("Changed group"))
    redirect('index')
delete.exposed = True

def populate(group, name, description, expire, visibility=None):
    group.name = web_to_spine(name.strip())
    group.description = web_to_spine(description.strip())
    
    if expire:
        expire = mx.DateTime.strptime(expire, "%Y-%m-%d")
            
    group.expire_date = expire

    if visibility:
        group.visibility_value = visibility

def populate_posix(group, gid):
    if gid is not None and group.is_posix:
        group.posix_gid = gid 

def validate(name, description, expire):
    if not name:
        return False, _("Group-name is empty.")

    if len(name) < 3:
        return False, _("Group-name is too short( min. 3 characters).")
    
    if len(name) > 16:
        return False, _("Group-name is too long(max. 16 characters).")

    if expire:
        try:
            expire = mx.DateTime.strptime(expire, "%Y-%m-%d")
        except mx.DateTime.Error, e:
            return False, _("Expire-date is not a legal date.")

    return True, ""

def get_selected_id(entity_name, entity_type_name):
    try:
        entity = EntityFactory().create_by_name(entity_type_name, entity_name)
        return entity.id
    except NotFoundError, e:
        return None

