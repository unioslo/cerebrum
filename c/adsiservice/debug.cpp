/*

Copyright 2002 University of Oslo, Norway

This file is part of Cerebrum.

Cerebrum is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

Cerebrum is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with Cerebrum; if not, write to the Free Software Foundation,
Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

*/

#include "service.h"

HRESULT PrintVariantArray(VARIANT var){
  LONG dwSLBound = 0;
  LONG dwSUBound = 0;
  VARIANT v;
  LONG i;
  HRESULT hr = S_OK;
  char ret[255];

  if(!((V_VT(&var) &  VT_VARIANT) &&  V_ISARRAY(&var))) return(E_FAIL);
  //
  // Check that there is only one dimension in this array
  //

  if ((V_ARRAY(&var))->cDims != 1) {
    hr = E_FAIL;
    BAIL_ON_FAILURE(hr);
  }
  //
  // Check that there is atleast one element in this array
  //

  if ((V_ARRAY(&var))->rgsabound[0].cElements == 0){
    hr = E_FAIL;
    BAIL_ON_FAILURE(hr);
  }

  //
  // We know that this is a valid single dimension array
  //

  hr = SafeArrayGetLBound(V_ARRAY(&var), 1, (long FAR *)&dwSLBound);
  BAIL_ON_FAILURE(hr);

  hr = SafeArrayGetUBound(V_ARRAY(&var), 1, (long FAR *)&dwSUBound);
  BAIL_ON_FAILURE(hr);

  for (i = dwSLBound; i <= dwSUBound; i++) {
    VariantInit(&v);
    hr = SafeArrayGetElement(V_ARRAY(&var), (long FAR *)&i, &v);
    if (FAILED(hr)) continue;
    if (i < dwSUBound) DOPRINTF(("%S, ", v.bstrVal));
    else DOPRINTF(("%S", v.bstrVal));
  }
  return(S_OK);

 error:
  return(hr);
}

HRESULT PrintVariant(VARIANT varPropData){
  HRESULT hr;
  BSTR bstrValue;

  switch (varPropData.vt) {
  case VT_I4:
    DOPRINTF(("%d", varPropData.lVal));
    break;
  case VT_BSTR:
    DOPRINTF(("%S", varPropData.bstrVal));
    break;

  case VT_BOOL:
    DOPRINTF(("%d", V_BOOL(&varPropData)));
    break;

  case (VT_ARRAY | VT_VARIANT):
    PrintVariantArray(varPropData);
    break;

  case VT_DATE:
    hr = VarBstrFromDate(varPropData.date, LOCALE_SYSTEM_DEFAULT, LOCALE_NOUSEROVERRIDE, &bstrValue);
    DOPRINTF(("%S", bstrValue));
    break;

  default:
    DOPRINTF(("Data type is %d\n", varPropData.vt));
    break;

  }
  DOPRINTF(("\n"));
  return(S_OK);
}

HRESULT PrintProperty(BSTR bstrPropName, HRESULT hRetVal, VARIANT varPropData){
  HRESULT hr = S_OK;

  switch (hRetVal) {

  case 0:
    DOPRINTF(("%-32S: ", bstrPropName));
    PrintVariant(varPropData);
    break;

  case E_ADS_CANT_CONVERT_DATATYPE:
    DOPRINTF(("%-32S: ", bstrPropName));
    DOPRINTF(("<Data could not be converted for display>\n"));
    break;

  default:
    DOPRINTF(("%-32S: ", bstrPropName));
    DOPRINTF(("<Data not available>\n"));
    break;

  }
  return(hr);
}

HRESULT ListObjectProperties(LPWSTR sObj, char *ret){  // List properties of a given object
  IADs *pADs;
  HRESULT hr;
  VARIANT var;
  BSTR bstrSchemaPath;
  IADsClass * pADsClass;
  VARIANT *   pvarPropName;
  DWORD i;
  VARIANT varProperty;

  hr = ADsGetObject(sObj, IID_IADs, (void**)&pADs);
  BAIL_ON_FAILURE(hr);
  hr = pADs->get_Schema(&bstrSchemaPath);
  DOPRINTF(("Schemapath: %S\n", bstrSchemaPath));
  hr = ADsGetObject(bstrSchemaPath, IID_IADsClass, (void **)&pADsClass);
  DOPRINTF(("1: %s\n", FAILED(hr) ? "FAILED" : "OK"));
  hr = pADsClass->get_OptionalProperties(&var);
  DOPRINTF(("2: %s\n", FAILED(hr) ? "FAILED" : "OK"));
  pADsClass->Release();
  DOPRINTF(("3: %s\n", FAILED(hr) ? "FAILED" : "OK"));

  hr = SafeArrayAccessData(var.parray, (void **) &pvarPropName);
  DOPRINTF(("4: %s\n", FAILED(hr) ? "FAILED" : "OK"));
  DOPRINTF(("TEST: %S\n", pvarPropName[0].bstrVal));
  for (i = 0; i < var.parray->rgsabound[0].cElements; i++){      //
    hr = pADs->Get(pvarPropName[i].bstrVal, &varProperty);
    PrintProperty(pvarPropName[i].bstrVal, hr, varProperty );
  }
 error:
  return SafeArrayUnaccessData(var.parray);
}

HRESULT
PrintLongFormat(IADs * pObject)
{

  HRESULT hr = S_OK;
  BSTR bstrName = NULL;
  BSTR bstrClass = NULL;
  BSTR bstrSchema = NULL;
  char ret[RET_SIZE];

  hr = pObject->get_Name(&bstrName) ;
  BAIL_ON_FAILURE(hr);

  hr = pObject->get_Class(&bstrClass);
  BAIL_ON_FAILURE(hr);

  // hr = pObject->get_Schema(&bstrSchema);

  DOPRINTF(("  %S(%S)\n", bstrName, bstrClass));

 error:
  if (bstrClass) SysFreeString(bstrClass);
  if (bstrName) SysFreeString(bstrName);
  if (bstrSchema) SysFreeString(bstrSchema);
  return(hr);
}
