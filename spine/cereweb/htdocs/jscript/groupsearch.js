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

// Stores the gid_end while option is not range.
var GS_gid_end_value = "";

// Runs when the page is finished loading.
addLoadEvent(GS_init_listeners);

// Initialises the listener on the reset button.
function GS_init_listeners() {
    var gid_option = document.getElementById('gid_option');
    
    addEvent(gid_option, 'change', GS_option_changed);

    GS_option_changed();
}

// Disables gid_end unless option is range.
function GS_option_changed() {
    var gid_end = document.getElementById('gid_end');
    var gid_option = document.getElementById('gid_option');
    var selected = gid_option.options[gid_option.selectedIndex];

    if (selected.value == "range") {
        if (gid_end.value == "") {
            gid_end.value = GS_gid_end_value;
        }
        gid_end.disabled = false;
    } else {
        if (gid_end.disabled != true) {
            GS_gid_end_value = gid_end.value;
        }
        gid_end.value = "";
        gid_end.disabled = true;
    }
}

