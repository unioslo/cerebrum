
// wrkElements : ((id, class, name), ...)
var maxElements = 20;
var wrkElements = new Array(maxElements);
for (var i = 0; i < maxElements; i++) {
    wrkElements[i] = new Array(null, "", "");
}

// fill wrkElements with the info already in the select
// TODO

// change the text on links to forget for things already in the worklist

// method to add an entity to the worklist
function worklist_remember(id, class, name) {
    var worklist = document.getElementById('worklistSel');

    if (worklist.length >= maxElements) {
        alert("Cannot add any more objects to the worklist.");
        return;
    }

    //element already remebered, remove
    for (var i = 0; i < maxElements; i++) {
        if (wrkElements[i][0] == id) {
            worklist_forget_by_pos(i);
            return;
        }
    }

    //remove option -Remembered objects-
    if (worklist[0].text == "-Remembered objects-") {
        worklist.remove(0);
    }

    var new_elm = document.createElement('option');
    new_elm.text = name;
    new_elm.value = id;

    try {
        worklist.add(new_elm, null); // standards compliant; doesn't work in IE
    } catch(ex) {
        worklist.add(new_elm); // IE only
    }

    // add element to wrkElements
    wrkElements[worklist.length-1] = new Array(id, class, name);

    // change the text on the element by id
    var link = document.getElementById("wrkElement"+id)
    link.innerText = "forget";
}

// method for removing an element from the worklist by position
function worklist_forget_by_pos(pos) {
    var worklist = document.getElementById('worklistSel');
    if (pos >= 0) {
        // remove element from wrkElements and worklist
        var id = wrkElements[pos][0];
        wrkElements[pos] = new Array(null, "", "");
        worklist.remove(pos);

        if (worklist.length == 0) {
            var option = document.createElement('option');
            option.text = "-Remembered objects-";
            worklist.add(option, 0);
        }

        // change the text on the element by id
        var link = document.getElementById("wrkElement"+id)
        if (link != null) {
            link.innerText = "remember";
        }
    }
}

// method for removing selected items from worklist
function worklist_forget() {
    var worklist = document.getElementById("worklistSel")
    for (i = worklist.length-1; i >= 0; i--) {
        if (worklist[i].selected == 1) {
            worklist_forget_by_pos(i);
        }
    }
}

function worklist_select_all() {
    var worklist = document.getElementById("worklistSel")
    for (i = 0; i < worklist.length; i++) {
        worklist[i].selected = 1;
    }
}

function worklist_select_none() {
    var worklist = document.getElementById("worklistSel")
    for (i = 0; i < worklist.length; i++) {
        worklist[i].selected = 0;
    }
}

function worklist_invert_selected() {
    var worklist = document.getElementById("worklistSel")
    for (i = 0; i < worklist.length; i++) {
        if (worklist[i].selected == 1) {
            worklist[i].selected = 0;
        } else {
            worklist[i].selected = 1;
        }
    }
}

