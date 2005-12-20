<span tal:define="title string:Endringer;title_id string:endringer" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
<form action="#" method="get">
Vis endringer siste
<input type="HIDDEN" name="action" value="do_list_new_entities">

<select name="dager">
  <option value="1">1 
  <option value="3">3
  <option value="7">7
  <option value="14">14
  <option value="30">30
</select> dager.  <input type="SUBMIT" value="Oppdater">
</form>
</p>

<span tal:condition="not:changes" tal:omit-tag="">
  No data
</span>

<span tal:condition="changes" tal:omit-tag="">

Endringer siste <span tal:content="days" tal:omit-tag=""/> dager.

<table border=1>
  <tr><th>Dato</th> <TH>Type</TH> <TH>Navn</TH> <th>misc</th></tr>
  <tr valign="top" tal:repeat="c changes"
    tal:attributes="class python:test(path('repeat/c/odd'), 'white', 'grey')">
    <td tal:content="c/tstamp"/>
    <td tal:content="c/change_type"/>

    <span tal:condition="exists:c/person_id" tal:omit-tag="">
      <td><a tal:attributes="href string:?action=show_person_info&entity_id=${c/person_id}" tal:content="c/name">Mr. Test</a></td>
    </span>
    <span tal:condition="not:exists:c/person_id" tal:omit-tag="">
      <td tal:content="c/name"/>
    </span>
    <td tal:content="c/misc"/>
  </tr>
</table>
</span>

</span></span></span>
