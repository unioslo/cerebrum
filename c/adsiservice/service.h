/*

This portion is heavily based on the sample service distributed with VC++4.2
*/

//#define TEST_DEMANDRED

#include <windows.h>
#include <winsock.h>
#include <stdio.h>
#include <stdlib.h>
#include <process.h>
#include <tchar.h>
#include <lmaccess.h>
#include <winnls.h>
#include <comutil.h>
#include <io.h>

#include "activeds.h"
#include "Iads.h"


#ifndef _SERVICE_H
#define _SERVICE_H

#ifdef __cplusplus
extern "C" {
#endif

// name of the executable
#define SZAPPNAME            "cerebrumS"
// internal name of the service
#define SZSERVICENAME        "cerebrumSync"
// displayed name of the service
#define SZSERVICEDISPLAYNAME "cerebrum Sync"
// list of service dependencies - "dep1\0dep2\0\0"
#define SZDEPENDENCIES       "RPCSS\0\0"

VOID ServiceStart(DWORD dwArgc, LPTSTR *lpszArgv);
VOID ServiceStop();
VOID AddToMessageLog(LPTSTR lpszMsg);

BOOL ReportStatusToSCMgr(DWORD dwCurrentState, DWORD dwWin32ExitCode, DWORD dwWaitHint);

#ifdef __cplusplus
}
#endif

#endif

extern LPTSTR GetLastErrorText( LPTSTR lpszBuf, DWORD dwSize );
extern TCHAR                   szErr[];

// Spesific to this service (GetLastErrorText + AddToMessageLog i service.cpp kan brukes...)

#define GLOB_GROUP L"GlobalGroup"
#define GLOB_USER L"User"

extern int show_debug;
extern BOOL debuging_service;

#define BAIL_ON_NULL(p)       if (!(p)) goto error; 
#define BAIL_ON_FAILURE(hr)   if (FAILED(hr)){ sprintf(ret, "Failed: 0x%x on line %d", hr, __LINE__); goto error; }
#define FREE_INTERFACE(pInterface) if (pInterface) { pInterface->Release(); pInterface=NULL; }

#define DBG_ERR printf("Error in %s, line %d\n", __FILE__, __LINE__);

#define MAXARGS 20
#define FETCH_NUM 100
#define RET_SIZE  512

#define NO_FLAGS_SET         0
#define MAX_PENDING_CONNECTS 4

#define PORT 1681
#define INI_FILE "c:/cerebrum_sync.ini"
#define TIMEOUT_VALUE 1140
#define DOPRINTF(x) if (debuging_service) printf x

typedef struct buff_struct BUFF;

struct buff_struct{
	int fd;
	char *inptr;
	char *inbase;
	int bufsiz;
	int incnt;
};



extern BOOLEAN send_data(int s, LPTSTR c);
int Decode(LPTSTR str, TCHAR *params[], int maxpars);
extern int rf_gets(LPTSTR buff, int n, BUFF *fb);


extern HRESULT ShowGroup(int sock2, LPWSTR pszPath, BOOL UsersGroups, char *ret);
extern HRESULT ProcessUser(LPTSTR pszPath, IADsUser *pUser, LPTSTR line, char *ret);
extern HRESULT CreateGroupOrUserWrap(LPWSTR pwParentName, LPWSTR pwGroupName, LPWSTR pwSamAcctName, char *type, char *ret);
extern HRESULT myDeleteObject(LPOLESTR pwszAdsPath, char *ret);
extern HRESULT ListObjectsWrap(int sock2, WCHAR *szPath, char *type, BOOL expand, char *ret);
extern HRESULT MoveObject(LPWSTR pszSrc, LPWSTR pszDest, char *ret);
extern HRESULT AddRemoveMemberToGroup(LPWSTR member, LPWSTR grp, BOOL remove, char *ret);
extern HRESULT AlterUser(WCHAR *p[], int n, char *ret);
extern HRESULT ConvNameWrap(WCHAR *cvPath, LPTSTR line, char *ret);