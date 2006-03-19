<span tal:define="title string:Opprett gruppe;title_id string:group_create" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_group_create">

<table border=0>
  <tr><td>Gruppenavn:</td><td><input type="TEXT" name="name" size="20"></td></tr>
  <tr><td>Beskrivelse:</td><td><input type="TEXT" name="description" size="20"></td></tr>
  <tr><td colspan=2></td></tr>   
</table>

<table border=0>
  <tr><td colspan=2><strong>Bruk i:</strong></td></tr>   
  <tr><td colspan=2></td></tr>
    <span tal:repeat="s spreads" tal:omit-tag="">
    <tr><td><input type="CHECKBOX" name="spreads" tal:attributes="value string:${s/code_str}"><a tal:content="s/desc" tal:omit-tag="">sprea\
d-desc</a></td></tr>
    </span>
    <tr><td colspan=2><input type="SUBMIT" value="Opprett gruppe"></td></tr>
</table>
</form>

</span></span></span>
