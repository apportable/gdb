/* Usage logging front end for gdb.

   Copyright (C) 2009 Free Software Foundation, Inc.

   This file is part of GDB.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.

   This is written with the possibility that several ways of logging
   may be chosen from.  For now we just use syslog.  */

#ifndef USAGE_LOGGING_H
#define USAGE_LOGGING_H

#include "ansidecl.h" /* for ATTRIBUTE_FPTR_PRINTF_1 */

extern int usage_log_enabled (void);

extern void usage_log_start (int argc, char **argv);

extern void usage_log_end (int exit_code);

extern void usage_log_printf (const char *, ...)
     ATTRIBUTE_FPTR_PRINTF_1;

extern void usage_log_flush (void);

#endif /* USAGE_LOGGING_H */
