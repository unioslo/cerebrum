<span tal:define="title string:Bygge gruppe;title_id string:group_create" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="get">
<input type="HIDDEN" name="action" value="do_group_create">

Gruppenavn: <input type="TEXT" name="name" size="20"><br>
Beskrivelse: <input type="TEXT" name="description" size="20"><br>

<dl>
  <dt>Spreads:
  <dd>
    <span tal:repeat="s spreads" tal:omit-tag="">
    <input type="CHECKBOX" name="spreads" tal:attributes="value string:${s/code_str}"><a tal:content="s/desc" tal:omit-tag="">spread-desc</a><br>
    </span>
  </dd>
</dl>

<p>

<input type="SUBMIT" value="Bygg">

</form>

</span></span></span>
