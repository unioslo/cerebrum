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

int sock;
// int show_debug = 1;
HANDLE mainThread, acceptThread;
boolean told2stop = FALSE;
DWORD cErr=0;
LPTSTR password;


void rf_resume(int s, LPTSTR c){
  if(c != NULL){   
    AddToMessageLog(c); 
  }
  closesocket(s);
  ResumeThread(mainThread);
  ExitThread(0);
}

#define BAD_NUMBER_OF_ARGS  0
DWORD AcceptThreadProc( LPDWORD lpdwParam ){
  SOCKADDR_IN rsin;
  int rsin_len;
  int sock2;
  TCHAR szBuff[255];
  TCHAR respBuff[255];
  TCHAR lnBuff[255];
  HRESULT hr;
  TCHAR *par[MAXARGS];
  char errmsg[255];
  char retb[RET_SIZE];
//  WCHAR *lpar[MAXARGS];
  BOOLEAN done, give_ack;
  rsin_len = sizeof(rsin);
  int nargs, n;
  BUFF fb;
  BOOL authenticated = FALSE;
  char *errmsgs[] = {"Bad number of arguments", "Some error"};

  if((sock2 = accept( sock,(struct sockaddr FAR *) &rsin, (int FAR *) &rsin_len )) < 0) {
    wsprintf(szBuff, L"accept %d is the error", WSAGetLastError());
    rf_resume(sock2, szBuff); 
  }
  done = FALSE;

#ifdef TEST_DEMANDRED
  DOPRINTF(("Warning: ALLOWING CONNECTION FROM ANY HOST (%s connected)!!!!!!\n", inet_ntoa(rsin.sin_addr)));
#else
  if(strcmp(inet_ntoa(rsin.sin_addr), ALLOWED_HOST)){
	  sprintf(szBuff, "320 Connection not allowed from '%s'\r\n", inet_ntoa(rsin.sin_addr));
	  send_data(sock2, szBuff);
	  rf_resume(sock2, szBuff); 
	  return FALSE;  // never reached
  }
#endif
  send_data(sock2, L"200 Ready æøå\r\n");
  fb.inbase = (char *)malloc(255); fb.bufsiz = 255; fb.incnt = 0; fb.fd = sock2;

  CoInitialize(NULL);	// should check return code
  while(!done){
	if((n = rf_gets(lnBuff, sizeof(lnBuff), &fb)) <= 0){
		wsprintf(respBuff, L"read_line: %d is the error", WSAGetLastError());
		rf_resume(sock2, respBuff);
	}
	if(!authenticated){
		if(wcscmp(password, lnBuff)){
			send_data(sock2, L"300 Hey! That wasn't nice! Go away!\n");
			rf_resume(sock2, respBuff);
			return FALSE; // never reached
		} else {
			send_data(sock2, L"200 Howdy, long time no see!\n");
			authenticated = TRUE;
			continue;
		}
	}
	lnBuff[n-1] = '\0';  // Vil ikke ha siste \n
	nargs = Decode(lnBuff, par, MAXARGS);
//    printf("COMMAND (%i): '%S'\n", nargs, par[0]);
	hr = 0; errmsg[0] = '\0'; give_ack = FALSE; retb[0] = '\0';
    if(!wcscmp(par[0], L"LUSERS")){
		if(nargs != 2) strcpy(errmsg, errmsgs[BAD_NUMBER_OF_ARGS]);
		else hr = ListObjectsWrap(sock2, par[1], "users", wcscmp(par[2], L"1") == 0, (char *)&retb);
    }else if(!wcscmp(par[0], L"LGROUPS")){
		if(nargs != 1) strcpy(errmsg, errmsgs[BAD_NUMBER_OF_ARGS]);
		else hr = ListObjectsWrap(sock2, par[1], "group", FALSE, (char *)&retb);		
	}else if(!wcscmp(par[0], L"LORGS")){
		if(nargs != 1) strcpy(errmsg, errmsgs[BAD_NUMBER_OF_ARGS]);
		else hr = ListObjectsWrap(sock2, par[1], "org", FALSE, (char *)&retb);
    }else if(!wcscmp(par[0], L"LUSER")){
		TCHAR line[255];
		wcscpy(line, L"210 ");
		hr = ProcessUser(par[1], NULL, line, retb);
		if(SUCCEEDED(hr)){
			wcscat(line, L"\n");
			send_data(sock2, line);
		}
	}else if(!wcscmp(par[0], L"TRANS")){
		TCHAR line[255];
		wcscpy(line, L"210 ");
		hr = ConvNameWrap(par[1], line, retb);
		if(SUCCEEDED(hr)){
			wcscat(line, L"\n");
			send_data(sock2, line);
		}
	}else if(!wcscmp(par[0], L"LGROUP")){
		give_ack = TRUE;		
		hr = ShowGroup(sock2, par[1], FALSE, retb); 
    }else if(!wcscmp(par[0], L"LUSERMEMB")){
		give_ack = TRUE;		
		hr = ShowGroup(sock2, par[1], TRUE, retb); 
    }else if(!wcscmp(par[0], L"NEWGR")){
		give_ack = TRUE;		
		hr = CreateGroupOrUserWrap(par[1], par[2], par[3], "group", retb);
    }else if(!wcscmp(par[0], L"NEWUSR")){
		give_ack = TRUE;
		hr = CreateGroupOrUserWrap(par[1], par[2], par[3], "user", retb);
    }else if(!wcscmp(par[0], L"NEWORG")){
		give_ack = TRUE;
		hr = CreateGroupOrUserWrap(par[1], par[2], par[3], "org", retb);
    }else if(!wcscmp(par[0], L"DELGR") || !wcscmp(par[0], L"DELUSR") || !wcscmp(par[0], L"DELORG")){
		give_ack = TRUE;
		hr = myDeleteObject(par[1], retb);
	}else if(!wcscmp(par[0], L"MOVEOBJ")){
		give_ack = TRUE;
		hr = MoveObject(par[1], par[2], retb);
    }else if(!wcscmp(par[0], L"ADDUSRGR")){
		give_ack = TRUE;
		hr = AddRemoveMemberToGroup(par[1], par[2], FALSE, retb);
    }else if(!wcscmp(par[0], L"DELUSRGR")){
		give_ack = TRUE;
		hr = AddRemoveMemberToGroup(par[1], par[2], TRUE, retb);
    }else if(!wcscmp(par[0], L"ALTRUSR")){
		give_ack = TRUE;
		hr = AlterUser(par, nargs, retb);
	}else if(!wcscmp(par[0], L"QUIT")){
		done = TRUE;
	}else{
		wsprintf(respBuff, L"310 Ka fasken prater du om (%s)?\r\n", par[0]);
		send_data(sock2, respBuff);
    }
    SetLastError(hr);
	if(SUCCEEDED(hr) && errmsg[0] == '\0'){
		if(give_ack){
			send_data(sock2, L"210 OK\n");
		}
	} else {
		if(errmsg[0] == '\0') wsprintf(respBuff, L"300 Failed 0x%x (%s) (%S)\n", hr, GetLastErrorText(szErr,256), retb);
		else  wsprintf(respBuff, L"300 Failed (%s)\n", errmsg);
		send_data(sock2, respBuff);
	}
//	printf("Error (0x%x): %s\n", hr, GetLastErrorText(szErr,256));
  }
  CoUninitialize();
  send_data(sock2, L"210 Haba baba\r\n");
  rf_resume(sock2, NULL);
  return 1;
}

VOID ServiceStart (DWORD dwArgc, LPTSTR *lpszArgv)
{
  SOCKADDR_IN sin;
  PHOSTENT phe;
  char buff[500];
  TCHAR szBuff[200];
  DWORD lpd;
  FILE *f;
  
  if (!ReportStatusToSCMgr(SERVICE_START_PENDING, NO_ERROR, 3000)) return;
  					       
  AddToMessageLog(L"server\n");
  sock = socket( PF_INET, SOCK_STREAM, 0);
  
  if (sock == INVALID_SOCKET) {
    AddToMessageLog(L"Socket failed\n"); exit(0);
  }
  sin.sin_family = AF_INET;
  sin.sin_port = htons(PORT);
			   
  gethostname(buff, 50);
  phe = gethostbyname(buff);
  memcpy((char FAR *)&(sin.sin_addr), phe->h_addr, phe->h_length);
			   
			   
  if (bind( sock, (struct sockaddr FAR *) &sin, sizeof(sin)) == SOCKET_ERROR) {
    wsprintf(szBuff, L"bind %d is the error", WSAGetLastError());
    AddToMessageLog(szBuff);
    closesocket( sock );
  }
  if (listen( sock, MAX_PENDING_CONNECTS ) < 0) {
    wsprintf(szBuff, L"listen %d is the error", WSAGetLastError());
    AddToMessageLog(szBuff);
  }
			   			   
  if (!ReportStatusToSCMgr(SERVICE_RUNNING, NO_ERROR, 0)) return;

  if((f = fopen(PASSWORD_FILE, "r")) == NULL){
	  DOPRINTF(("Oops, failed to read passwordfile\n")); exit(1);
  }

  if(fgets(buff, sizeof(buff), f) == NULL){
	  DOPRINTF(("Oops, failed to read passwordfile\n")); exit(1);
  }
  fclose(f);

  password = (TCHAR *) malloc(strlen(buff)*sizeof(TCHAR)+1);

  MultiByteToWideChar(CP_ACP, 0, buff, strlen(buff)+1, password, strlen(buff)*2+1);

  while(!told2stop){
    mainThread = GetCurrentThread();
    DOPRINTF(("Starter trån\n"));
    acceptThread = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE) AcceptThreadProc, NULL, 0, (LPDWORD) &lpd);
    DOPRINTF(("Startet, Main thread suspended\n"));
    WaitForSingleObject(acceptThread, INFINITE);  // If changed, MUST change read_line!								       
    DOPRINTF(("Main thread resumed\n"));
  }
}

VOID ServiceStop(void){
  told2stop = 1;
  TerminateThread(acceptThread, 0);
}
