<span tal:define="title string:Bygge bruker;title_id string:user_create" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
Bygge ny bruker eid av 

<span tal:condition="exists:person_name" tal:content="string: personen ${person_name}">
</span>

<span tal:condition="exists:group_name" tal:content="string: gruppen ${group_name}">
</span>

</p>

<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_user_create">
<input type="HIDDEN" name="owner_type" tal:attributes="value string:${owner_type}">
<input type="HIDDEN" name="owner_id" tal:attributes="value string:${owner_id}">

Brukernavn: <input type="TEXT" name="name" size="20" tal:attributes="value string:${uname}">
<span tal:condition="more_unames" tal:omit-tag=""> (andre forslag: <span tal:content="more_unames" tal:omit-tag=""/>)</span>

<p>

<input type="SUBMIT" value="Bygg">
</p>

</form>

</span></span></span>
