<span tal:define="title string:Finn person;title_id string:person_find" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_person_find">

<dl>
  <dt>Søke <a tal:replace="structure python:help_link('person_find_filter', 'filter')"></a>
  <dd><input type="TEXT" name="search_value" size="20">
  <dt>Type søk
  <dd>
    <input type="RADIO" name="search_type" value="name" CHECKED>navn <br>
    <input type="RADIO" name="search_type" value="date">fødselsdato på formatet YYYY-MM-DD, f.eks 2004-12-30
</dl>

<input type="SUBMIT" value="Finn"/>

</form>
</span></span></span>
