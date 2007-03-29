<span tal:define="title string:Søk etter brukere;title_id string:user_find" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_user_find">
<dl>
  <dt><a tal:replace="structure python:help_link('user_find_filter', 'Søkefilter')">filter</a>
  <dd><input type="TEXT" name="search_value" size="20">
  <br>
  <br>
  <dt>Søketype
  <dd>
    <input type="RADIO" name="search_type" value="uname" CHECKED>Brukernavn<br>
</dl>

<input type="SUBMIT" value="Søk">

</form>

</span></span></span>
