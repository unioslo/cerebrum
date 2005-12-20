<span tal:define="title string:Søkeresultat;title_id string:person_find_res" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<span tal:condition="not:personlist" tal:omit-tag="">
  Ingen treff
</span>

<span tal:condition="personlist" tal:omit-tag="">
  <table border="1">
    <tr><th>Fødselsdato</th>  <th>Navn</th></tr>
    <tr valign="top" tal:repeat="person personlist"
        tal:attributes="class python:test(path('repeat/person/odd'), 'white', 'grey')">
      <td tal:content="person/birth">1999-99-99</td>
      <td><a tal:attributes="href string:?action=show_person_info&entity_id=${person/entity_id}" tal:content="person/name">Mr. Test</a></td>
    </tr>
  </table>
</span>
</span></span></span>
