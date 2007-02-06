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

YAHOO.util.Event.addListener('search_clear', 'click', SR_clear);
YAHOO.util.Event.addListener('search_submit', 'click', SR_submit);

YE.onAvailable('add_member_name', initAutoComplete);
function initAutoComplete(event) {
    var myName = YD.get('add_member_name');
    var myDiv = document.createElement('div');
    myDiv.setAttribute('id', 'search_autoComplete');
    myName.parentNode.appendChild(myDiv);
    myName.parentNode.setAttribute('id', 'autocomplete');
    var myDataSource = new YAHOO.widget.DS_XHR(
        '/ajax/search', ["ResultSet", "name", "type", "owner"]);
    myDataSource.connTimeout = 3000;
    myDataSource.queryMatchCase = true;
    var myAutoComp = new YAHOO.widget.AutoComplete
        (myName, myDiv, myDataSource);
    myAutoComp.minQueryLength = 3;
    myAutoComp.dataReturnEvent.subscribe(dataReturn, myName);

    myAutoComp.formatResult = function(aResultItem, sQuery) {
        var name = aResultItem[0];
        var type = aResultItem[1];
        var owner = aResultItem[2];
        var aMarkup = ["<div id='ysearchresult'>",
            '<div style="float:left;width:6em;">',
            name,
            '</div>',
            owner.name,
            "</div>"]
        
        return (aMarkup.join(""));
    }
}

function dataReturn(event, args, myName) {
    if (args[2].length === 0)
        myName.style.backgroundColor = "red";
    else
        myName.style.backgroundColor = "";
}

// Clears the searchform.
function SR_clear(e) {
    YAHOO.util.Event.preventDefault(e);

    var form = document.getElementById('search_form');
    var base_uri = 'http://' + location.host;
    var uri = base_uri + "/entity/clear_search?url=" + form.action;
    
    //Resets all elements in the form.
    for(var i = 0; i < form.length; i++) {
        if (form.elements[i].type == "text") {
            form.elements[i].value = "";
        }
    }

    var callback = {
        success: remove_searchresult,
        failure: remove_searchresult,
        timeout: 5000
    }

    var cObj = YAHOO.util.Connect.asyncRequest('GET', uri, callback);
}

function remove_searchresult() {
    YAHOO.log('removing...');
    var maindiv = document.getElementById('content');
    if (YAHOO.util.Dom.inDocument('searchresult')) {
        var searchresult = document.getElementById('searchresult');
        var removed = maindiv.removeChild(searchresult);
    }
}

function SR_submit(e) {
    return; // Disabled until pages are ready for DOM manipulation.
    YAHOO.util.Event.stopEvent(e); // AJAX takes over.
    var uri = 'http://' + location.host + '/ajax/search';
    
    var callback = {
        success: function(o) {
            var result = o.responseText;
            var maindiv = document.getElementById('content');
            remove_searchresult();

            maindiv.innerHTML = result + maindiv.innerHTML;
        },
        failure: function(o) {
            YAHOO.log('failure');
        },
        timeout: 5000
    }
    YAHOO.util.Connect.setForm('search_form');
    var cObj = YAHOO.util.Connect.asyncRequest('POST', uri, callback);
}
