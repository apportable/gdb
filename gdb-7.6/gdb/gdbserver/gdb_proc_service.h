/* <proc_service.h> replacement for systems that don't have it.
   Copyright (C) 2000-2013 Free Software Foundation, Inc.

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
   along with this program.  If not, see <http://www.gnu.org/licenses/>.  */

#ifndef GDB_PROC_SERVICE_H
#define GDB_PROC_SERVICE_H

#include <sys/types.h>

/* ANDROID: */
#ifdef UAPI_HEADERS
#if defined(__aarch64__) || defined(__arm__)
#include <sys/ptrace.h>
typedef unsigned long elf_greg_t;
typedef elf_greg_t elf_gregset_t[(sizeof (struct user_pt_regs) / sizeof(elf_greg_t))];
#else
#include <sys/user.h>
typedef unsigned long long elf_greg_t;
#define ELF_NGREG (sizeof (struct user_regs_struct) / sizeof(elf_greg_t))
typedef elf_greg_t elf_gregset_t[ELF_NGREG];
typedef struct user_fpregs_struct elf_fpregset_t;
#endif
#endif

#ifdef HAVE_PROC_SERVICE_H
#include <proc_service.h>
#else

#ifdef HAVE_SYS_PROCFS_H
#include <sys/procfs.h>
#endif

/* Not all platforms bring in <linux/elf.h> via <sys/procfs.h>.  If
   <sys/procfs.h> wasn't enough to find elf_fpregset_t, try the kernel
   headers also (but don't if we don't need to).  */
#ifndef HAVE_ELF_FPREGSET_T
# ifdef HAVE_LINUX_ELF_H
#  include <linux/elf.h>
# endif
#endif

/* ANDROID: for AT_PHDR and AT_PHNUM */
#include <linux/auxvec.h>

typedef enum
{
  PS_OK,			/* Success.  */
  PS_ERR,			/* Generic error.  */
  PS_BADPID,			/* Bad process handle.  */
  PS_BADLID,			/* Bad LWP id.  */
  PS_BADADDR,			/* Bad address.  */
  PS_NOSYM,			/* Symbol not found.  */
  PS_NOFREGS			/* FPU register set not available.  */
} ps_err_e;

#ifndef HAVE_LWPID_T
typedef unsigned int lwpid_t;
#endif

#ifndef HAVE_PSADDR_T
typedef void *psaddr_t;
#endif

// mchinen: this hack is needed to compile for android platform 21 sysroot
// we make x86 and arm build against 19, but aarch64 does not exist until 21.
// https://code.google.com/p/android/issues/detail?id=86712),
// http://blog.csdn.net/bupt073114/article/details/25211319
#if defined(__aarch64__)
typedef unsigned long elf_greg_t;
typedef elf_greg_t elf_gregset_t[35];
#endif

#ifndef HAVE_PRGREGSET_T
typedef elf_gregset_t prgregset_t;
#endif

#endif /* HAVE_PROC_SERVICE_H */

/* Structure that identifies the target process.  */
struct ps_prochandle
{
  /* We don't need to track anything.  All context is served from the
     current inferior.  */
};

#endif /* gdb_proc_service.h */
