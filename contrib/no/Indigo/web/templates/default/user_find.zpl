<span tal:define="title string:User find;title_id string:user_find" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>Vis <a tal:attributes="href string:?action=do_user_find&search_type=owner&search_value=${state/tgt_person_id}">valgt persons brukere</a></p>


<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_user_find">
<dl>
  <dt>Search <a tal:replace="structure python:help_link('user_find_filter', 'filter')">filter</a>
  <dd><input type="TEXT" name="search_value" size="20">
  <dt>Search type
  <dd>
    <input type="RADIO" name="search_type" value="uname" CHECKED>uname<br>
    <input type="RADIO" name="search_type" value="stedkode">stedkode<br>
    <input type="RADIO" name="search_type" value="disk">disk<br>
    <input type="RADIO" name="search_type" value="host">host<br>
</dl>

<input type="SUBMIT" value="search">

</form>

</span></span></span>
