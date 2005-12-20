<span metal:define-macro="page" tal:omit-tag="">
   <table> <tr><td><h1 tal:content="title">title</h1></td> <td><a tal:replace="structure python:help_link(title_id,'')"></a></td></tr> </table>
   <table>
  <tr><td><span metal:define-slot="body" tal:omit-tag=""></span></td>
  <td>  <iframe src="about:blank" name="helpframe" frameborder="0"> </iframe></td>
  </tr>
  </table>
</span>
