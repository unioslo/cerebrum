<span tal:define="title string:Finn gruppe;title_id string:group_search" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_group_find">
<input type="hidden" name="search_type" value="name">

Gruppenavn: <input type="TEXT" name="search_value" size="20">

<p>

<input type="SUBMIT" value="Finn">

</form>

</span></span></span>
