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

/* Globale variabler ved multithreading:
  __declspec( thread ) int tls_i = 1;
  (Thread Local Storage (TLS))
*/

int recvwithtimeout(int sock, char *buf, int len, int flags){  // From apache...
    u_long FAR iostate = 1;
    fd_set fdset;
    struct timeval tv;
    int err = WSAEWOULDBLOCK;
    int rv;

//    if (!(tv.tv_sec = ap_check_alarm())) return (recv(sock, buf, len, flags));

    rv = ioctlsocket(sock, FIONBIO, &iostate);
    iostate = 0;
//    ap_assert(!rv);
    rv = recv(sock, buf, len, flags);
    if (rv == SOCKET_ERROR) {
        err = WSAGetLastError();
        if (err == WSAEWOULDBLOCK) {
            FD_ZERO(&fdset);
            FD_SET(sock, &fdset);
            tv.tv_usec = 0; tv.tv_sec = TIMEOUT_VALUE;   // TODO: as #define
            rv = select(FD_SETSIZE, &fdset, NULL, NULL, &tv);
            if (rv == SOCKET_ERROR)
                err = WSAGetLastError();
            else if (rv == 0) {
                ioctlsocket(sock, FIONBIO, &iostate);
//                ap_check_alarm();
                WSASetLastError(WSAEWOULDBLOCK);
                return (SOCKET_ERROR);
            }
            else {
                rv = recv(sock, buf, len, flags);
                if (rv == SOCKET_ERROR)
                    err = WSAGetLastError();
            }
        }
    }
    ioctlsocket(sock, FIONBIO, &iostate);
    if (rv == SOCKET_ERROR)
        WSASetLastError(err);
	return (rv);
}

int rf_gets(LPTSTR rbuff, int n, BUFF *fb){
	int i, ch, ct;
	char buff[RET_SIZE];

	i = 0; ct = 0;
	for(;;){
		if (i == fb->incnt){  // no characters left
			fb->inptr = fb->inbase; fb->incnt = 0;
			i = recvwithtimeout(fb->fd, fb->inbase, fb->bufsiz, NO_FLAGS_SET);
			if (i == -1){
				buff[ct] = '\0';
				return ct ? ct : -1;
			}
			fb->incnt = i;
			if(i == 0) break;  // EOF
			i = 0;
			continue;  // restart
		}
		ch = fb->inptr[i++];

        if (ch == '\012') {     /* got LF */
            if (ct == 0)
                buff[ct++] = '\n';
/* if just preceeded by CR, replace CR with LF */
            else if (buff[ct - 1] == '\015')
                buff[ct - 1] = '\n';
            else if (ct < n - 1)
                buff[ct++] = '\n';
            else
                i--;            /* no room for LF */
            break;
        }
        if (ct == n - 1) {
            i--;                /* push back ch */
            break;
        }

        buff[ct++] = ch;
    }
    fb->incnt -= i;
    fb->inptr += i;

    buff[ct] = '\0';
    MultiByteToWideChar(CP_ACP, 0, buff, strlen(buff)+1, rbuff, strlen(buff)*2+1);

    DOPRINTF(("<%S", rbuff));
    return ct;
}

int Decode(LPTSTR str, TCHAR *params[], int maxpars){ // Malloc's the params[] 
	int n = 0, b = 0, t;
	TCHAR s;
	TCHAR *pstr;
	TCHAR buff[255];
// wprintf(L"DECODE: '%s'\n", str);
	pstr = buff;
	while(*str != 0){
		if(*str == '&'){
			*pstr = 0;
			params[n] = (TCHAR *) malloc(b*sizeof(TCHAR)+1);
			wcscpy(params[n], buff);
			b = 0;
			pstr = buff;
			n++;
		} else if(*str == '%'){
			str++; s = 0;
			for(t = 4; t>-1; t-= 4){
				if(*str >= '0' && *str <= '9'){
					s += (*str - '0') << t;
				} else if(*str >= 'a' && *str <= 'f'){
					s += (*str - 'a'+10) << t;
				} else if(*str >= 'A' && *str <= 'F'){
					s += (*str - 'A'+10) << t;
				} else {
					DOPRINTF(("Illegal decode! (%c)\n", str)); return -1;
				}
				str++;
			}
			str--;
			*pstr++ = s; 
		} else {
			*pstr++ = *str;
		}
		b++;
		str++;
		if(b > 255){
			DOPRINTF(("Oops, line very long!\n")); return -1;
		}
	}
	*pstr = 0;
	params[n] = (TCHAR *) malloc(b*sizeof(TCHAR)+1);
	wcscpy(params[n], buff);
//	printf("Arg %i: '%S'\n", n, buff);
//	for(b = 0; b <= n; b++){ printf("x-Arg %i: '%S'\n", b, params[b]);	}
	return n;
}

char *Encode(char *c){
  char *pstr;
  static char buff[255];
  int b = 0;

  pstr = buff;
  while(*c != 0){
    if(*c == '%' || *c == '&'){
      *pstr++ = '%';
      sprintf(pstr, "%02x", *c);
      pstr+=2;
      b+=2;
    } else {
      *pstr++ = *c;
    }
    c++;
    b++;
    if(b > 255){
      DOPRINTF(("Oops, line very long!\n")); return NULL;
    }
  }
  return buff;
}

BOOLEAN send_data(int s, LPTSTR str){
  int n, rest;
  char buff[255], *c;

  DOPRINTF((">%S", str));
  WideCharToMultiByte(CP_ACP, 0, str, wcslen(str)+1, buff, 255, FALSE, NULL);
  c = buff;
  rest = strlen(c);
  while(rest > 0){
	n = send(s, c, rest, NO_FLAGS_SET);
	if(n == SOCKET_ERROR) return FALSE;
	c += n; rest -= n;
  }

  return TRUE;
}

