<span tal:define="title string:Søk etter grupper;title_id string:group_search" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_group_find">
<input type="hidden" name="search_type" value="name">

<table border=0>
  <tr><td><strong>Gruppenavn:</strong><td><input type="TEXT" name="search_value" size="20"></td></tr>
  <tr><td colspan=2></td></tr>
  <tr><td colspan=2></td></tr>
  <tr><td colspan=2><input type="SUBMIT" value="Søk"></td></tr>
</table>
</form>

</span></span></span>
