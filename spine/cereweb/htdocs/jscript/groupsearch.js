/*
 * Copyright 2004, 2005 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

// Runs when the page is finished loading.
YE.addListener('gid_option', 'change', GS_option_changed);
YE.onAvailable('gid_option', GS_option_changed);

// Disables gid_end unless option is range.
function GS_option_changed() {
    var state = YD.get('gid_option').value !== "range";
    YD.get('gid_end').disabled = state;
}

if(cereweb.debug) {
    log('groupsearch is loaded');
}
