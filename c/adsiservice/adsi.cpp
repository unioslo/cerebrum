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

HRESULT ConvName(WCHAR *from, WCHAR *to, char *ret){
	IADsNameTranslate *pNto;
	HRESULT hr = S_OK;
	WCHAR *fp;
	BSTR bstr;
	TCHAR *ch;

	hr = CoCreateInstance(CLSID_NameTranslate, NULL, CLSCTX_INPROC_SERVER, IID_IADsNameTranslate, (void**)&pNto);
	BAIL_ON_FAILURE(hr);
	hr = pNto->Init(ADS_NAME_INITTYPE_GC, L"");
	BAIL_ON_FAILURE(hr);
	if(!wcsncmp(L"LDAP://", from, 7)){
		fp = &from[7];
		hr =pNto->Set(ADS_NAME_TYPE_1779, fp);
		BAIL_ON_FAILURE(hr);
		hr = pNto->Get(ADS_NAME_TYPE_NT4, &bstr);
		BAIL_ON_FAILURE(hr); 
		while((ch = wcschr(bstr, L'\\')) != NULL){
			*ch = L'/';
		}
		wcscpy(to, L"WinNT://");
		wcscat(to, bstr);
		SysFreeString(bstr);
	} else if(!wcsncmp(L"WinNT://", from, 8)) {		
		fp = &from[8]; 
		while((ch = wcschr(fp, L'/')) != NULL){
			*ch = L'\\';
		}
		hr =pNto->Set(ADS_NAME_TYPE_NT4, fp);
		BAIL_ON_FAILURE(hr); 
		hr = pNto->Get(ADS_NAME_TYPE_1779, &bstr);
		wcscpy(to, L"LDAP://");
		wcscat(to, bstr);
		SysFreeString(bstr);
	}
error:
	FREE_INTERFACE(pNto);
	return hr;
}



HRESULT ConvNameWrap(WCHAR *cvPath, LPTSTR line, char *ret){

	HRESULT hr = S_OK;
	WCHAR base[255];

	printf("E: '%S'\n", cvPath);
	hr = ConvName(cvPath, base, ret);
	BAIL_ON_FAILURE(hr);
	wcscat(line, base);
error:
	return hr;

}


void appres(LPTSTR str, LPTSTR key, LPTSTR val, int maxlen){
	wcscat(str, key); wcscat(str, L"&");
	wcscat(str, val); wcscat(str, L"&");
}

HRESULT ProcessUser(LPTSTR pszPath, IADsUser *pUser, LPTSTR line, char *ret){
	HRESULT hr;
	BSTR bt;
	VARIANT var;
	WCHAR pszNewPath[255];

	if(pUser == NULL){
		if(!wcsncmp(L"LDAP://", pszPath, 7)){
		    ConvName(pszPath, pszNewPath, ret);
		} else {
			wcscpy(pszNewPath, pszPath); 		
		}
		hr = ADsGetObject(pszNewPath, IID_IADsUser, (void **) &pUser);	
		BAIL_ON_FAILURE(hr);
	}

	hr = pUser->get_Name(&bt);
	BAIL_ON_FAILURE(hr);
	appres(line, L"name", bt, RET_SIZE);
	SysFreeString(bt);

	hr = pUser->get_ADsPath(&bt);
	BAIL_ON_FAILURE(hr);		
	appres(line, L"up", bt, RET_SIZE);
	SysFreeString(bt);
	
	hr = pUser->get_HomeDirectory(&bt);
	BAIL_ON_FAILURE(hr);
	appres(line, L"hdir", bt, RET_SIZE);
	SysFreeString(bt);

	hr = pUser->get_FullName(&bt);
	BAIL_ON_FAILURE(hr);
	appres(line, L"fn", bt, RET_SIZE);
	SysFreeString(bt);

	hr = pUser->get_Profile(&bt);
	BAIL_ON_FAILURE(hr);
	appres(line, L"pf", bt, RET_SIZE);
	SysFreeString(bt);

	hr = pUser->get_LoginScript(&bt);
	BAIL_ON_FAILURE(hr);
	appres(line, L"ls", bt, RET_SIZE);
	SysFreeString(bt);

	hr = pUser->Get(L"HomeDirDrive", &var);
	BAIL_ON_FAILURE(hr);
	appres(line, L"hdr", var.bstrVal, RET_SIZE);
	VariantClear(&var);

	hr = pUser->get_AccountDisabled(&(var.boolVal));
	BAIL_ON_FAILURE(hr);
	appres(line, L"dis", var.boolVal ? L"1" : L"0", RET_SIZE);
	VariantClear(&var);

	hr = pUser->Get(L"UserFlags", &var);
	BAIL_ON_FAILURE(hr);
	appres(line, L"ccp", var.intVal & UF_PASSWD_CANT_CHANGE ? L"0" : L"1", RET_SIZE);
	VariantClear(&var);

	hr = pUser->Get(L"PasswordExpired", &var);
	BAIL_ON_FAILURE(hr);
	appres(line, L"pexp", var.boolVal ? L"1" : L"0", RET_SIZE);
	VariantClear(&var);

	if(pszPath != NULL){
		FREE_INTERFACE(pUser);
	}
	return S_OK;
error:
	return hr;
}

HRESULT ListObjectsWin(int sock2, WCHAR *pszPath, char *type, BOOL expand, char *ret){
	ULONG cElementFetched = 0L;
	IEnumVARIANT *pEnumVariant = NULL;
	VARIANT VarFilter, VariantArray[FETCH_NUM];
	HRESULT hr;
	IADsContainer *pADsContainer =  NULL;
	DWORD dwObjects = 0, dwEnumCount = 0, i = 0;
	BOOL  fContinue = TRUE;
	LPWSTR grpArr[] = { GLOB_GROUP, NULL };
	LPWSTR usrArr[] = { L"User", NULL };
	TCHAR line[255];

	VariantInit(&VarFilter);
 	hr = ADsGetObject(pszPath, IID_IADsContainer, (void **)&pADsContainer);
	BAIL_ON_FAILURE(hr);
	if(! strcmp("users", type)){
		hr = ADsBuildVarArrayStr(usrArr, sizeof(usrArr)/sizeof(LPWSTR), &VarFilter);
	} else if(! strcmp("groups", type)){
		hr = ADsBuildVarArrayStr(grpArr, sizeof(grpArr)/sizeof(LPWSTR), &VarFilter);
	} else {
		sprintf(ret, "Bad args");
		return S_FALSE;
	}
	BAIL_ON_FAILURE(hr);
	hr = pADsContainer->put_Filter(VarFilter);
	BAIL_ON_FAILURE(hr);
	hr = ADsBuildEnumerator(pADsContainer, &pEnumVariant);
	BAIL_ON_FAILURE(hr);

	while (fContinue) {
		IADs *pObject = NULL;
		hr = ADsEnumerateNext(pEnumVariant, FETCH_NUM, VariantArray, &cElementFetched);

		if (hr == S_FALSE) fContinue = FALSE;
		dwEnumCount++;

		for (i = 0; i < cElementFetched; i++ ) {
			IDispatch *pDispatch = NULL;

			pDispatch = VariantArray[i].pdispVal;
			if(expand){
				IADsUser *pUser = NULL;
				hr = pDispatch->QueryInterface(IID_IADsUser, (VOID **) &pUser);
				BAIL_ON_FAILURE(hr);
				wcscpy(line, L"210-");
				hr = ProcessUser(NULL, pUser, line, ret);
				FREE_INTERFACE(pUser);
				if(FAILED(hr)){ goto error; }
				wcscat(line, L"\n");
				send_data(sock2, line);
			} else {
				BSTR bt;
				int cp = 4;
				wcscpy(line, L"210-");
				hr = pDispatch->QueryInterface(IID_IADs, (VOID **) &pObject) ;
				BAIL_ON_FAILURE(hr);
				hr = pObject->get_ADsPath(&bt);
				BAIL_ON_FAILURE(hr);
				wcscat(line, L"up&"); wcscat(line, bt);
				SysFreeString(bt);
				hr = pObject->get_Name(&bt);
				BAIL_ON_FAILURE(hr);
				wcscat(line, L"&name&"); wcscat(line, bt); wcscat(line, L"\n");
				SysFreeString(bt);
				FREE_INTERFACE(pObject);
				send_data(sock2, line);
			}
			FREE_INTERFACE(pDispatch); 
		}
		memset(VariantArray, 0, sizeof(VARIANT)*FETCH_NUM);
		dwObjects += cElementFetched;
	}
	wsprintf(line, L"210 OK That's all folks, all %d of them!\n", dwObjects);
	send_data(sock2, line);
error:
	FREE_INTERFACE(pEnumVariant);
	VariantClear(&VarFilter);
	FREE_INTERFACE(pADsContainer);
	return(hr);
}




HRESULT ListObjectsLdap(int sock2, WCHAR *szPath, char *type, BOOL expand, char *ret){  /* users, groups and organizational units */
	IDirectorySearch *pContainerToSearch = NULL;
	IADs *pObject = NULL;
	HRESULT hr = S_OK;
	BSTR bt;
	WCHAR base_winnt[255];
	TCHAR line[RET_SIZE], *ch;
	DWORD dwObjects = 0;
	
	IADs* piIADs = NULL;
	VARIANT var;
	VariantInit(&var);
	WCHAR rootdse[255];

	//Specify paged search.
	ADS_SEARCHPREF_INFO SearchPrefs;
	SearchPrefs.dwSearchPref = ADS_SEARCHPREF_PAGESIZE;
	SearchPrefs.vValue.dwType = ADSTYPE_INTEGER;
	SearchPrefs.vValue.Integer = 1000;
	DWORD dwNumPrefs = 1;
	

	// Handle used for searching.
	ADS_SEARCH_HANDLE hSearch = NULL;

	LPWSTR pszAttrSam[] = { L"ADsPath", L"samaccountname"};  // Trenger samaccountname for å hente data som ikke finnes i LDAP
	LPWSTR pszAttrPath[] = { L"ADsPath"};
	LPWSTR *pszAttr;
	DWORD dwCount;
	LPOLESTR pszSearchFilter;
	WCHAR tmp[255];
	char dtype;		

	pszSearchFilter = (LPWSTR ) malloc(2048);

	hr = ADsOpenObject(szPath,
         NULL,
         NULL,
         ADS_SECURE_AUTHENTICATION, //Use Secure Authentication
         IID_IDirectorySearch,
         (void**)&pContainerToSearch);
	BAIL_ON_FAILURE(hr);

		
	// Specify the searchfilter
	if(! strcmp("users", type)){
		dtype = 1;
		dwCount = sizeof(pszAttrSam)/sizeof(LPWSTR);
		pszAttr = pszAttrSam;
		pszSearchFilter = L"(&(objectCategory=person)(objectClass=user))";
	} else if (! strcmp("group", type)){
		dtype = 2;
		dwCount = sizeof(pszAttrSam)/sizeof(LPWSTR);
		pszAttr = pszAttrSam;
		wcscpy(pszSearchFilter, L"(&(objectCategory=group)(objectClass=group)");

		wsprintf(tmp, L"(groupType:=%d)", ADS_GROUP_TYPE_GLOBAL_GROUP | ADS_GROUP_TYPE_SECURITY_ENABLED);
		wcscat(pszSearchFilter, tmp);
		wcscat(pszSearchFilter, L")");
	} else if (! strcmp("org", type)){
		dtype = 3;
		dwCount = sizeof(pszAttrPath)/sizeof(LPWSTR);
		pszAttr = pszAttrPath;
		wcscpy(pszSearchFilter, L"(objectClass=organizationalUnit)");
	} else {
		sprintf(ret, "Bad args");
		return S_FALSE;
	}
	//wprintf(L"Search filter: %s\n", pszSearchFilter);

	// Set the search preference.
	hr = pContainerToSearch->SetSearchPreference( &SearchPrefs, dwNumPrefs);
	hr = pContainerToSearch->ExecuteSearch(pszSearchFilter, pszAttr, dwCount, &hSearch);

	/* Now, convert search handle to WinNT provider */
	pContainerToSearch->QueryInterface(IID_IADs, (VOID **) &pObject);
	pObject->get_ADsPath(&bt);
	
	//Get rootDSE.
	hr = ADsGetObject(L"LDAP://rootDSE",IID_IADs,(void**)&piIADs);		
	BAIL_ON_FAILURE(hr);
	hr = piIADs->Get( L"defaultNamingContext", &var );
	BAIL_ON_FAILURE(hr);
	wcscpy(rootdse, L"LDAP://");
    wcscat(rootdse, var.bstrVal);
    VariantClear(&var);

	ConvName(rootdse, base_winnt, ret);
	while((ch = wcschr(base_winnt, L'\\')) != NULL){
		*ch = L'/';
	}
	//printf("RESS: %S\n", base_winnt);
	SysFreeString(bt);
	send_data(sock2, L"210-Data follows\n");
	
	hr = pContainerToSearch->GetFirstRow( hSearch);
	BAIL_ON_FAILURE(hr);
        
	while( hr != S_ADS_NOMORE_ROWS ) {
    
		ADS_SEARCH_COLUMN col;
		WCHAR path[255];

		dwObjects++;
        // loop through the array of passed column names,
        // print the data for each column
        for (DWORD x = 0; x < dwCount; x++) {
			hr = pContainerToSearch->GetColumn( hSearch, pszAttr[x], &col );
    		
			BAIL_ON_FAILURE(hr); 

			if(x == 0){
				wcscpy(path, col.pADsValues->CaseIgnoreString);
				if(dtype == 3){
					//printf("dtype3: %S\n", path);
					wcscpy(line, L"210-path&");
					//appres(line, L"name", col.pADsValues->CaseIgnoreString, RET_SIZE);										
					wcscat(line, col.pADsValues->CaseIgnoreString);	
					wcscat(line, L"\n");
					send_data(sock2, line);
				}
			} else {
				if(dtype == 1){
					if(expand){
						TCHAR winnt[255];
						wcscpy(line, L"210-");
						appres(line, L"path", path, RET_SIZE);
						printf("col:%S\n",col.pADsValues->CaseIgnoreString);
						wsprintf(winnt, L"%s%s", base_winnt, col.pADsValues->CaseIgnoreString);
						//wsprintf(winnt, L"%s%s", L"WinNT://WINTEST/", col.pADsValues->CaseIgnoreString);
						hr = ProcessUser(winnt, NULL, line, ret);

						if(FAILED(hr)){ 
							pContainerToSearch->FreeColumn( &col );
							goto error; 
						}
						wcscat(line, L"\n");
						send_data(sock2, line);
					} else {
//						BSTR bt;
						int cp = 4;
						wcscpy(line, L"210-");
						appres(line, L"up", path, RET_SIZE);
						wcscat(line, L"\n");
						send_data(sock2, line);
					}
				}
				if(dtype == 2){
					wcscpy(line, L"210-"); 
					appres(line, L"up", path, RET_SIZE);
					appres(line, L"name", col.pADsValues->CaseIgnoreString, RET_SIZE);
					wcscat(line, L"\n");
					send_data(sock2, line);
				}
			}
			pContainerToSearch->FreeColumn( &col );
        }
		FreeADsMem( pszAttr );
		hr = pContainerToSearch->GetNextRow( hSearch );
	}
	wsprintf(line, L"210 OK That's all folks, all %d of them!\n", dwObjects);
	send_data(sock2, line);
error:
	if(pContainerToSearch){
		pContainerToSearch->CloseSearchHandle(hSearch);
		FREE_INTERFACE(pContainerToSearch);
	}
	return hr;
}

HRESULT ListObjectsWrap(int sock2, WCHAR *szPath, char *type, BOOL expand, char *ret){
	if(! wcsncmp(szPath, L"WinNT:", 6)){
		return ListObjectsWin(sock2, szPath, type, expand, ret);
	} else {
		return ListObjectsLdap(sock2, szPath, type, expand, ret);
	}
	return S_FALSE;
}

HRESULT ShowGroup(int sock2, LPWSTR pszPath, BOOL UsersGroups, char *ret){
	HRESULT hr=S_OK;
	IADsGroup *pGroup                 = NULL;
	IADsMembers *pADsMembers          = NULL;
	IUnknown *      pUnknown          = NULL;     // IUnknown for getting the ENUM initially
	IEnumVARIANT *  pEnumVariant      = NULL;     // Ptr to the Enum variant
	VARIANT         VariantArray[FETCH_NUM];      // Variant array for temp holding retuned data
	BOOL            fContinue         = TRUE;     // Looping Variable
	ULONG           ulElementsFetched = NULL;     // Number of elements fetched
	IDispatch * pDispatch         = NULL; 
	IADs      * pIADsGroupMember  = NULL; 
	BSTR        bstrPath          = NULL; 
	IADsUser *pUser               = NULL;
	TCHAR line[255];

	if(UsersGroups){
		hr = ADsGetObject(pszPath, IID_IADsUser, (void**)&pUser);
		BAIL_ON_FAILURE(hr);
		hr = pUser->Groups(&pADsMembers);
	} else {
		hr = ADsGetObject(pszPath, IID_IADsGroup, (void**)&pGroup);
		BAIL_ON_FAILURE(hr);
		hr = pGroup->Members(&pADsMembers);
		//	  printf("Enumerating '%S' with AIDsGroup::Members\n", pszPath);
	}
	BAIL_ON_FAILURE(hr);
	hr = pADsMembers->get__NewEnum(&pUnknown);
	BAIL_ON_FAILURE(hr);
	hr = pUnknown->QueryInterface(IID_IEnumVARIANT, (void **)&pEnumVariant);
	BAIL_ON_FAILURE(hr);
	while (fContinue){
		ulElementsFetched = 0;
		hr = ADsEnumerateNext(pEnumVariant, FETCH_NUM, VariantArray, &ulElementsFetched);
		// printf("UE: %li\n", ulElementsFetched);    
		if (1 && ulElementsFetched ){
			for (ULONG i = 0; i < ulElementsFetched; i++ ){
				pDispatch = VariantArray[i].pdispVal;

				hr = pDispatch->QueryInterface(IID_IADs, (VOID **) &pIADsGroupMember) ;

				if (SUCCEEDED(hr)){
					BSTR bt;
					hr = pIADsGroupMember->get_Name(&bt);
					BAIL_ON_FAILURE(hr);
					wcscpy(line, L"210-name&"); wcscat(line, bt);
					SysFreeString(bt);
					wcscat(line, L"&up&");
					hr = pIADsGroupMember->get_ADsPath(&bt);
					BAIL_ON_FAILURE(hr);
					wcscat(line, bt); wcscat(line, L"\n");
					SysFreeString(bt);
					send_data(sock2, line);
					FREE_INTERFACE(pIADsGroupMember);
				}
				FREE_INTERFACE(pDispatch);
			}
			memset(VariantArray, 0, sizeof(VARIANT)*FETCH_NUM);
		}
		else
			fContinue = FALSE;
	}
error:
	FREE_INTERFACE(pUser);
	FREE_INTERFACE(pIADsGroupMember);
	FREE_INTERFACE(pDispatch);
	FREE_INTERFACE(pEnumVariant);
	FREE_INTERFACE(pUnknown);
	FREE_INTERFACE(pADsMembers);
	FREE_INTERFACE(pGroup);
	return hr; 
}

HRESULT MoveObject(LPWSTR pszSrc, LPWSTR pszDest, char *ret) {
    IADsContainer * pIADsC = NULL;
    HRESULT         hr;
    IDispatch * pIDispatchNewObject = NULL;
 
	//printf("Moving '%S' to '%S'\n", pszSrc, pszDest);
	hr = ADsGetObject(pszDest, IID_IADsContainer, (void **)& pIADsC);
	BAIL_ON_FAILURE(hr);
	hr = pIADsC->MoveHere(pszSrc,NULL, &pIDispatchNewObject );
	BAIL_ON_FAILURE(hr);
error:
    FREE_INTERFACE(pIDispatchNewObject);
	FREE_INTERFACE(pIADsC);
//	PrintLastError(hr);
    return hr;
}

HRESULT myDeleteObject(LPOLESTR pwszAdsPath, char *ret){
	HRESULT hr;
	BSTR  bsParentPath = NULL, bsClass = NULL, bsRelN = NULL;
	IADs *pIADsToDelete = NULL;
	IADsContainer *pIADsC = NULL;
	WCHAR *pWC;

	hr = ADsGetObject(pwszAdsPath, IID_IADs,(void **)& pIADsToDelete);
	BAIL_ON_FAILURE(hr);
	hr = pIADsToDelete->get_Parent(&bsParentPath); 
	BAIL_ON_FAILURE(hr);
	hr = pIADsToDelete->get_Schema(&bsClass); 
	BAIL_ON_FAILURE(hr);
	hr = pIADsToDelete->get_Name(&bsRelN); 
	BAIL_ON_FAILURE(hr);

	//  printf("Parent: %S, %S, %S\n", bsParentPath, bsClass, bsRelN);

	hr = ADsGetObject(bsParentPath, IID_IADsContainer,(void **)& pIADsC);
	BAIL_ON_FAILURE(hr);
	if((pWC = wcsrchr(bsClass, L'/')) != NULL) pWC++;
	else pWC = bsClass;
	hr = pIADsC->Delete(pWC, bsRelN);
	BAIL_ON_FAILURE(hr);

error:
	FREE_INTERFACE(pIADsToDelete);
	FREE_INTERFACE(pIADsC);
	SysFreeString(bsParentPath);
	SysFreeString(bsClass);
	SysFreeString(bsRelN);
	//  PrintLastError(hr);
	return hr;
}

HRESULT CreateGroupOrUserLdap(LPWSTR pszPath, LPWSTR pwCommonName,LPWSTR pwSamAcctName, char *type, char *ret){
	IDirectoryObject *pDirObject = NULL;

	HRESULT    hr;
	ADSVALUE   sAMValue;
	ADSVALUE   classValue;
	LPDISPATCH pDisp = NULL;
	WCHAR       pwCommonNameFull[1024];
	ADSVALUE   groupType;
	ADS_ATTR_INFO *attrInfo;
	int iGroupType = 
	ADS_GROUP_TYPE_GLOBAL_GROUP |
	//        ADS_GROUP_TYPE_DOMAIN_LOCAL_GROUP, 
	//        ADS_GROUP_TYPE_UNIVERSAL_GROUP, 
	ADS_GROUP_TYPE_SECURITY_ENABLED 
	;
	ADS_ATTR_INFO  userAttrInfo[] = {  
		{L"objectClass", ADS_ATTR_UPDATE, ADSTYPE_CASE_IGNORE_STRING, &classValue, 1 },
		{L"sAMAccountName", ADS_ATTR_UPDATE, ADSTYPE_CASE_IGNORE_STRING, &sAMValue, 1},
	};
	ADS_ATTR_INFO  grpAttrInfo[] = {  
		{L"objectClass", ADS_ATTR_UPDATE, ADSTYPE_CASE_IGNORE_STRING, &classValue, 1 },
		{L"sAMAccountName", ADS_ATTR_UPDATE, ADSTYPE_CASE_IGNORE_STRING, &sAMValue, 1},
		{L"groupType", ADS_ATTR_UPDATE, ADSTYPE_CASE_IGNORE_STRING, &groupType, 1}
	};
	ADS_ATTR_INFO  ouAttrInfo[] = {  
		{L"objectClass", ADS_ATTR_UPDATE, ADSTYPE_CASE_IGNORE_STRING, &classValue, 1 }
	};

	DWORD dwAttrs;
	classValue.dwType = ADSTYPE_CASE_IGNORE_STRING;

	sAMValue.dwType=ADSTYPE_CASE_IGNORE_STRING;
	sAMValue.CaseIgnoreString = pwSamAcctName;

	hr = ADsGetObject(pszPath, IID_IDirectoryObject, (void **)&pDirObject); 
	BAIL_ON_FAILURE(hr);

	wsprintfW(pwCommonNameFull,L"CN=%s",pwCommonName);
	if(! strcmp("group", type)){
		attrInfo = grpAttrInfo;
		classValue.CaseIgnoreString = L"group";
		groupType.dwType=ADSTYPE_INTEGER;
		groupType.Integer =  iGroupType;
		dwAttrs = sizeof(grpAttrInfo)/sizeof(ADS_ATTR_INFO); 
	} else if(! strcmp("user", type)){
		attrInfo = userAttrInfo;
		classValue.CaseIgnoreString = L"user";
		dwAttrs = sizeof(userAttrInfo)/sizeof(ADS_ATTR_INFO); 
	} else if(! strcmp("org", type)){
		classValue.CaseIgnoreString = L"organizationalUnit";
		attrInfo = ouAttrInfo;
		dwAttrs = sizeof(ouAttrInfo)/sizeof(ADS_ATTR_INFO); 
		wsprintfW(pwCommonNameFull,L"OU=%s",pwCommonName);
	} else {
		sprintf(ret, "Illegal type '%S'", type);
		hr = E_FAIL; goto error;
	}

	hr = pDirObject->CreateDSObject( pwCommonNameFull,  attrInfo, dwAttrs, &pDisp );
	BAIL_ON_FAILURE(hr);
error:
	FREE_INTERFACE(pDisp);
	FREE_INTERFACE(pDirObject);
	return hr;
}

HRESULT CreateGroupOrUserWin(LPWSTR pwParentName, LPWSTR pwGroupName, char *type, char *ret){
  HRESULT    hr;
  LPDISPATCH pDisp = NULL;
  IADsContainer *pContainer = NULL;
  IADs *ado = NULL;

  if (wcslen(pwGroupName) >20) return E_FAIL;

  hr = ADsGetObject(pwParentName, IID_IADsContainer, (void **)&pContainer); 
  BAIL_ON_FAILURE(hr);

  if(! strcmp(type, "group")) hr = pContainer->Create(GLOB_GROUP, pwGroupName, &pDisp);
  else hr = pContainer->Create(GLOB_USER, pwGroupName, &pDisp);
  BAIL_ON_FAILURE(hr);

  hr = pDisp->QueryInterface(IID_IADs, (void **)&ado);
  BAIL_ON_FAILURE(hr);
  hr = ado->SetInfo();
  BAIL_ON_FAILURE(hr);
error:
//	PrintLastError(hr);
  FREE_INTERFACE(pContainer);
  FREE_INTERFACE(ado);
  FREE_INTERFACE(pDisp);
  return hr;
}

HRESULT CreateGroupOrUserWrap(LPWSTR pwParentName, LPWSTR pwGroupName, LPWSTR pwSamAcctName, char *type, char *ret){
	if(! wcsncmp(pwParentName, L"WinNT:", 6)){
		return CreateGroupOrUserWin(pwParentName, pwGroupName, type, ret);
	} else {
		return CreateGroupOrUserLdap(pwParentName, pwGroupName, pwSamAcctName, type, ret);
	}
	return S_FALSE;
}

HRESULT AddRemoveMemberToGroup(LPWSTR member, LPWSTR grp, BOOL remove, char *ret){
	HRESULT hr = E_INVALIDARG;
	IADsGroup * pGroup=NULL;
	IADs* pIADsNewMember=NULL;
	BSTR bsNewMemberPath;

	hr = ADsGetObject(member, IID_IADs, (void**)&pIADsNewMember);
	BAIL_ON_FAILURE(hr);
	
	hr = pIADsNewMember->get_ADsPath(&bsNewMemberPath); 
	BAIL_ON_FAILURE(hr);

	hr = ADsGetObject(grp, IID_IADsGroup, (void**)&pGroup);
	BAIL_ON_FAILURE(hr);

	if(remove) hr = pGroup->Remove(bsNewMemberPath);
	else hr = pGroup->Add(bsNewMemberPath);

error:
	FREE_INTERFACE(pGroup);
	FREE_INTERFACE(pIADsNewMember);
//	PrintLastError(hr);
	return hr;
}

HRESULT AlterUser(WCHAR *p[], int n, char *ret){
  int i;
  IADsUser * pUser = NULL;
  HRESULT hr = E_INVALIDARG;
  VARIANT var;

  hr = ADsGetObject(p[1], IID_IADsUser, (void**)&pUser);
  BAIL_ON_FAILURE(hr);

  for(i=2; i<=n; i+=2){
    if(!wcscmp(p[i],L"ADIS")){
    }else if(!wcscmp(p[i],L"fn")){
      hr = pUser->put_FullName(p[i+1]);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"pass")){ 
      hr = pUser->SetPassword(p[i+1]);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"hdr")){ 
      var.vt = VT_BSTR;
      var.bstrVal = p[i+1];
      hr = pUser->Put(L"HomeDirDrive", var);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"hdir")){ 
      hr = pUser->put_HomeDirectory(p[i+1]);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"ls")){
      hr = pUser->put_LoginScript(p[i+1]);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"pf")){
      hr = pUser->put_Profile(p[i+1]);
      BAIL_ON_FAILURE(hr);
	}else if(!wcscmp(p[i],L"pexp")){
	  hr = pUser->Get(L"UserFlags", &var);
      BAIL_ON_FAILURE(hr);
	  var.intVal |= ADS_UF_DONT_EXPIRE_PASSWD;
      if(!wcscmp(p[i+1], L"1")) var.intVal ^= ADS_UF_DONT_EXPIRE_PASSWD; 
	  hr = pUser->Put(L"UserFlags", var);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"ccp")){
      hr = pUser->Get(L"UserFlags", &var);
      BAIL_ON_FAILURE(hr);
      var.intVal |= UF_PASSWD_CANT_CHANGE;
      if(!wcscmp(p[i+1], L"1")) var.intVal ^= UF_PASSWD_CANT_CHANGE;
      hr = pUser->Put(L"UserFlags", var);
      BAIL_ON_FAILURE(hr);
    }else if(!wcscmp(p[i],L"dis")){
      /* 0 == FALSE, -1 == TRUE */
      hr = pUser->put_AccountDisabled(!wcscmp(p[i+1], L"1") ? -1 : 0);
      BAIL_ON_FAILURE(hr);
    }else{
      sprintf(ret, "What do you mean in arg '%i'?\n", i);
      hr = E_FAIL;
      BAIL_ON_FAILURE(hr);
    }
    //    wprintf(L"Arg %i : '%s'=%s (0x%x)\n", i, p[i], p[i+1], hr);
  }
  hr = pUser->SetInfo();
  BAIL_ON_FAILURE(hr);
 error:
  FREE_INTERFACE(pUser);
  return hr;
}
