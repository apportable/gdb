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

#include "config.h"
#ifdef HAVE_SYSLOG_H
#define _GNU_SOURCE /* for vasprintf */
#include <limits.h>
#include <sys/stat.h>
#include <stdarg.h>
#include <stdio.h>
#include <syslog.h>
#include <time.h>
#include <utime.h>
#ifdef GDBSERVER
#include <unistd.h>
#include "server.h"
#include "../usage-logging.h"
#else
#include "defs.h"
#include "gdb_assert.h"
#include "gdb_string.h"
#include "version.h"
#include "usage-logging.h"
#endif

/* Convert HAVE_GOOGLEISMS to something we can use post-cpp.
   It simplifies the code to not have to #ifdef-out everything
   when not in effect.  */
#ifdef HAVE_GOOGLEISMS
#define HAVE_USAGE_LOGGING 1
#else
#define HAVE_USAGE_LOGGING 0
#endif

/* ??? We don't necessarily want to base this on --prefix as we want to use
   the same file even when configuring for a place other than /usr.
   Ideally we want a configure option, but that can wait.  */
static const char usage_logging_checkpoint_file[] =
  "/usr/lib/gdb/logging-checkpoint";

#define GDB_SYSLOG_PRIORITY LOG_INFO
#define GDB_SYSLOG_FACILITY LOG_USER
#define GDB_SYSLOG_OPTIONS LOG_PID

#define CHECKPOINT_INTERVAL 10
#define CHECKPOINT_MODE 0222
#define PARENT_MODE 0755

enum usage_logging_state
{
  USAGE_LOGGING_UNKNOWN,
  USAGE_LOGGING_ENABLED,
  USAGE_LOGGING_DISABLED
};

static enum usage_logging_state usage_logging_state = USAGE_LOGGING_UNKNOWN;

/* Record the output in a buffer so that we don't call syslog for
   each command.
   The recorded log times will be wrong unless you call usage_log_flush
   when you need to.  For command logging, wrong times is ok, it's a
   tradeoff we make, the time to execute the command is included in the
   log message.  */
#define LOG_BUFFER_SIZE 10
static char *log_buffer[LOG_BUFFER_SIZE];
static int next_buffer = 0;

/* Maximum number of log messages.
   If someone is running a long running script, there's no point in
   collecting tons of data, it's probably a lot of repetition.
   This needed to be increased from 1000 when logging of types printed
   was added.  The current value is a semi-conservative guess.  */
#define MAX_LOG_MESSAGES 50000
static int log_message_count = 0;

/* Print a maximum of this many log messages per second.
   Too many per second can affect gdb's performance.  Google Ref #5378698.
   The value here doesn't affect gdb in directed tests, and there is room
   for growth.  OTOH, at some point too many commands per second is going
   to reduce the S/N ratio of the logs.  This value is a tradeoff.
   We really only have to worry about losing data during a backtrace
   which can trigger a lot of printing-type messages.
   Printing a large amount of data can, obviously, also trigger a lot of
   printing-type messages, but after this many such messages, the S/N ratio
   goes down.  */
#define MAX_LOG_MESSAGES_PER_SECOND 1000

/* Used to throttle our logging.
   Otherwise, in a scripted environment we can overload syslog and bring gdb to
   a crawl.  */
static time_t last_message_time;

/* The number of messages we have printed since the last time
   last_message_time was updated.  */
static int nr_messages_this_second = 0;

/* Return non-zero if usage logging is enabled.  */

int
usage_log_enabled (void)
{
  return usage_logging_state == USAGE_LOGGING_ENABLED;
}

/* Flush the log buffer.  */

void
usage_log_flush (void)
{
  int i;
  int num_flushed = next_buffer;

  if (usage_logging_state == USAGE_LOGGING_DISABLED)
    return;
  gdb_assert (usage_logging_state == USAGE_LOGGING_ENABLED);

  for (i = 0; i < next_buffer; ++i)
    {
      syslog (GDB_SYSLOG_PRIORITY, "%s", log_buffer[i]);
      free (log_buffer[i]);
      log_buffer[i] = NULL; /* defensive programming */
    }

  /* Keep track of the number of messages.
     We may overrun MAX_LOG_MESSAGES by a little.  That's ok.  */
  log_message_count += next_buffer;

  next_buffer = 0;

  /* Add a message to the log if we reach the max and start dropping the
     remainder.  */
  if (log_message_count - num_flushed < MAX_LOG_MESSAGES
      && log_message_count >= MAX_LOG_MESSAGES)
    {
      usage_log_printf ("status: max %d messages reached, dropping remainder",
			MAX_LOG_MESSAGES);
      /* We just flushed the buffer, and have now added something to it.
	 If we exit without flushing this message, that's ok.  */
    }
}

/* Add text to the log buffer.  */

static void
log_vprintf (const char *msg, va_list args)
{
  /* If the buffer is full, flush it first.  */
  if (next_buffer == LOG_BUFFER_SIZE)
    usage_log_flush ();

  /* Ignore memory allocation failures, we'll probably crash on an
     xmalloc failure soon anyway.  */
  if (vasprintf (&log_buffer[next_buffer], msg, args) != -1)
    ++next_buffer;
}

/* Add text to the log buffer.  */

static void
log_printf (const char *msg, ...)
{
  va_list args;

  va_start (args, msg);
  log_vprintf (msg, args);
  va_end (args);
}

/* gdbserver doesn't have fprintf_unfiltered.
   Wrap the call into something both gdb and gdbserver versions can use.  */

static void
fprintf_stdlog (const char *msg, ...)
{
  va_list args;

  va_start (args, msg);

#ifdef GDBSERVER
  vfprintf (stderr, msg, args);
#else
  vfprintf_unfiltered (gdb_stdlog, msg, args);
#endif

  va_end (args);
}

/* Return non-zero if the checkpoint file is legit,
   e.g., it exists and all the permissions are ok,
   and we're not within the logging interval.  */

static int
verify_checkpoint (const char *checkpoint_file)
{
  struct stat checkpoint_stat, parent_stat;
  char *parent = xstrdup (checkpoint_file);
  char *last_slash = strrchr (parent, '/');

  gdb_assert (last_slash != NULL);
  *last_slash = '\0';

  if (lstat (parent, &parent_stat) == -1)
    {
      fprintf_stdlog ("Unable to lstat() logging checkpoint parent directory: %s.\n",
		      strerror (errno));
      free (parent);
      return 0;
    }
  free (parent);
  parent = NULL;

  if (lstat (checkpoint_file, &checkpoint_stat) == -1)
    {
      fprintf_stdlog ("Unable to lstat() logging checkpoint: %s.\n",
		      strerror (errno));
      return 0;
    }

  if (checkpoint_stat.st_uid != 0 || checkpoint_stat.st_gid != 0
      || (checkpoint_stat.st_mode & ~S_IFMT) != CHECKPOINT_MODE
      || ! S_ISDIR (checkpoint_stat.st_mode))
    {
      fprintf_stdlog ("Logging checkpoint verification failed: bad owner or mode.\n");
      return 0;
    }

  if (parent_stat.st_uid != 0 || parent_stat.st_gid != 0
      || (parent_stat.st_mode & ~S_IFMT) != PARENT_MODE
      || ! S_ISDIR (parent_stat.st_mode))
    {
      fprintf_stdlog ("Logging checkpoint parent directory verification failed: bad owner or mode.\n");
      return 0;
    }

  {
    time_t checkpoint_time = checkpoint_stat.st_mtime;
    time_t current_time = time (NULL);
    if ((current_time - checkpoint_time) < CHECKPOINT_INTERVAL)
      return 0;
  }

  return 1;
}

/* Check if we've been invoked too soon since the last checkpoint,
   and update the checkpoint if not for the next time gdb is started.
   Returns non-zero if it's ok to continue logging.

   The throttling we do here is the same as is done on prod by
   command_wrapper.  It is for use at the gdb-invocation level.
   For per-log-message throttling, grep for last_message_time.
   [It is a bit clumsy to have both sets of throttling.  Cautious-R-Us.]  */

static int
try_to_write_checkpoint (const char *checkpoint_file)
{
  if (! verify_checkpoint (checkpoint_file))
    return 0;

  /* Update mtime to 'now' (as indicated by utime(file, _NULL_)).  */
  if (utime (checkpoint_file, NULL) == -1)
    {
      fprintf_stdlog ("Unable to update mtime of logging checkpoint: %s\n",
		      strerror (errno));
      return 0;
    }

  return 1;
}

/* Return non-zero if we're running on prod (and logging has already been done
   by command_wrapper).  */

static int
on_prod_p (const char *exe_path)
{
  const char *dot = strrchr (exe_path, '.');

  if (dot != NULL && strcmp (dot, ".orig") == 0)
    return 1;
  return 0;
}

/* Return non-zero if we're running on prod using a best guess.
   This is called when we don't have /proc/self/exe (e.g. upx'd gdb).
   Note: What we really care about here is whether we were invoked with
   command_wrapper.  */

static int
no_path_on_prod_p (void)
{
  if (access ("/usr/bin/gdb32.orig", X_OK) == 0)
    return 1;
  return 0;
}

/* Return non-zero if we're running in the build directory.
   We may be running the testsuite.  While we throttle the logging frequency
   it'll still generate a lot of noise in syslog.  */

static int
in_build_dir_p (const char *exe_path)
{
  char *parent_path = xstrdup (exe_path);
  char *slash;
  const char *parent_dir;

  /* ??? IWBN to use ldirname,lbasename here, but gdbserver doesn't have these
   and gdbserver can't use libiberty.  Sigh.  */

  slash = strrchr (parent_path, '/');
  gdb_assert (slash != NULL);
  *slash = '\0';
  slash = strrchr (parent_path, '/');
  gdb_assert (slash != NULL);
  parent_dir = slash + 1;

  if (strcmp (parent_dir, "gdb") == 0
      || strcmp (parent_dir, "gdbserver") == 0
      /* This test catches testsuite/xgdb that's run by the testsuite.  */
      || strcmp (parent_dir, "testsuite") == 0)
    {
      free (parent_path);
      return 1;
    }

  free (parent_path);
  return 0;
}

/* Return non-zero if we're running in the build directory using
   a best guess.
   This is called when we don't have /proc/self/exe (e.g. upx'd gdb).
   We may be running the testsuite.  While we throttle the logging frequency
   it'll still generate a lot of noise in syslog.

   Note: This test is less preferable to in_build_dir_p.  We don't really
   care what directory we're in, we care what gdb we're running.
   This test will flag running /usr/bin/gdb in gdb/testsuite.  */

static int
no_path_in_build_dir_p (void)
{
  char path[PATH_MAX + 1];
  int i, len, max_test_file_len;
  static const char * const test_files[] =
  {
    "/usage-logging.o",
    "/../usage-logging.o",
    "/../../usage-logging.o",
    NULL
  };

  /* Compute how much space we need in `path' to hold any element of
     `test_files'.  This is used to prevent overflowing the buffer.  */
  max_test_file_len = 0;
  for (i = 0; test_files[i] != NULL; ++i)
    {
      len = strlen (test_files[i]);
      if (max_test_file_len < len)
	max_test_file_len = len;
    }

  len = readlink ("/proc/self/cwd", path, sizeof (path) - max_test_file_len - 1);
  if (len <= 0)
    return 0; /* Blech.  Might as well say we're not in build dir.  */

  for (i = 0; test_files[i] != NULL; ++i)
    {
      strcpy (&path[len], test_files[i]);
      if (access (path, R_OK) == 0)
	return 1;
    }

  return 0;
}

/* Copy STR to DST, \-escaping it as necessary for syslog.
   Control chars are escaped as \xXX (except for obvious ones like \n).
   NOTE: This means one byte can expand to four bytes in the output.
   Backslash (\) and double-quote (") are also \-escaped.
   If the string contains a space it is wrapped in double-quotes.
   Returns a pointer to the end of the copied string (a la stpcpy).  */

static char *
copy_for_syslog (char *dst, const char *src)
{
  int quote_string = strchr (src, ' ') != NULL;

  if (quote_string)
    *dst++ = '"';

  while (*src)
    {
      /* command_wrapper_lib.cc:kBadSyslogChars is "\t\f\n\r\v".
	 We just escape all non-printable (ascii) chars.
	 Getting any fancier for this logging is left for another day.  */

      switch (*src)
	{
	case '\n': *dst++ = '\\'; *dst++ = 'n'; break;
	case '\r': *dst++ = '\\'; *dst++ = 'r'; break;
	case '\t': *dst++ = '\\'; *dst++ = 't'; break;
	case '\\': *dst++ = '\\'; *dst++ = '\\'; break;
	case '"':  *dst++ = '\\'; *dst++ = '"'; break;
	default:
	  {
	    unsigned char c = *src;
	    static const char hex[] = "0123456789abcdef";

	    if (c < 32 || c >= 127)
	      {
		*dst++ = '\\';
		*dst++ = 'x';
		*dst++ = hex[c >> 4];
		*dst++ = hex[c & 15];
	      }
	    else
	      {
		*dst++ = *src;
	      }
	    break;
	  }
	}

      ++src;
    }

  if (quote_string)
    *dst++ = '"';

  *dst = '\0';
  return dst;
}

/* Subroutine of usage_log_start to simplify it.  */

static void
usage_log_start_1 (int argc, char **argv)
{
  char *user = getenv ("USER");
  int uid = getuid ();
  char path[PATH_MAX + 1];
  int i, len;
  char *text;
  char *p;

  len = readlink ("/proc/self/exe", path, sizeof (path) - 1);
  if (len > 0)
    {
      path[len] = '\0';

      /* Don't log if we're running on prod, we use command_wrapper there.  */
      if (on_prod_p (path))
	{
	  usage_logging_state = USAGE_LOGGING_DISABLED;
	  return;
	}

      /* Don't log invocations of gdb when run from the build directory.  */
      if (in_build_dir_p (path))
	{
	  usage_logging_state = USAGE_LOGGING_DISABLED;
	  return;
	}
    }
  else
    {
      /* This happens for upx'd executables.  Blech.  */
      strcpy (path, "/proc-self-exe-unavailable-maybe-upx-gdb");

      /* Don't log if we're running on prod, we use command_wrapper there.  */
      if (no_path_on_prod_p ())
	{
	  usage_logging_state = USAGE_LOGGING_DISABLED;
	  return;
	}

      /* Don't log invocations of gdb when run from the build directory.  */
      if (no_path_in_build_dir_p ())
	{
	  usage_logging_state = USAGE_LOGGING_DISABLED;
	  return;
	}
    }

  switch (usage_logging_state)
    {
    case USAGE_LOGGING_UNKNOWN:
      if (! try_to_write_checkpoint (usage_logging_checkpoint_file))
	{
	  usage_logging_state = USAGE_LOGGING_DISABLED;
	  return;
	}
      usage_logging_state = USAGE_LOGGING_ENABLED;
      break;
    default:
      gdb_assert (usage_logging_state == USAGE_LOGGING_ENABLED);
      break;
    }

  /* Only need to do this once.  */
  openlog ("gdb", GDB_SYSLOG_OPTIONS, GDB_SYSLOG_FACILITY);

  next_buffer = 0;

  if (user != NULL)
    usage_log_printf ("session starting, version %s, user %s, exe %s",
		      version, user, path);
  else
    usage_log_printf ("session starting, version %s, uid %d, exe %s",
		      version, uid, path);

  len = readlink ("/proc/self/cwd", path, sizeof (path) - 1);
  if (len <= 0)
    return;
  path[len] = '\0';
  usage_log_printf ("cwd: %s\n", path);

  len = 0;
  for (i = 0; i < argc; ++i)
    len += strlen (argv[i]) * 4; /* *4: see copy_for_syslog */
  text = xmalloc (len + argc + 1);
  p = copy_for_syslog (text, argv[0]);
  for (i = 1; i < argc; ++i)
    {
      *p++ = ' ';
      p = copy_for_syslog (p, argv[i]);
    }
  usage_log_printf ("exec: %s\n", text);
  free (text);
  usage_log_flush ();

  last_message_time = time (NULL);
  nr_messages_this_second = 0;
}

/* Called at the start of gdb to log start-up.  */

void
usage_log_start (int argc, char **argv)
{
  if (usage_logging_state == USAGE_LOGGING_DISABLED)
    return;

  if (HAVE_USAGE_LOGGING)
    usage_log_start_1 (argc, argv);
  else
    usage_logging_state = USAGE_LOGGING_DISABLED;
}

/* Called when gdb is exiting.  */

void
usage_log_end (int exit_code)
{
  if (usage_logging_state == USAGE_LOGGING_DISABLED)
    return;

  /* Reset the message count in case we reached the max.
     We're done, and we want *our* message emitted.  */
  log_message_count = 0;
  nr_messages_this_second = 0;

  usage_log_printf ("session ending, exit code %d", exit_code);
  usage_log_flush ();
  closelog ();
}

void
usage_log_printf (const char *msg, ...)
{
  va_list args;
  time_t now;

  if (usage_logging_state == USAGE_LOGGING_DISABLED)
    return;
  gdb_assert (usage_logging_state == USAGE_LOGGING_ENABLED);

  if (log_message_count >= MAX_LOG_MESSAGES)
    return;

  now = time (NULL);
  if (now != last_message_time)
    {
      /* Before we reset the counter, it would be good to know how many
	 messages were dropped.  */
      if (nr_messages_this_second > MAX_LOG_MESSAGES_PER_SECOND)
	log_printf ("messages dropped: %d, too many per second\n",
		    nr_messages_this_second - MAX_LOG_MESSAGES_PER_SECOND);
      last_message_time = now;
      nr_messages_this_second = 0;
    }
  ++nr_messages_this_second;

  if (nr_messages_this_second <= MAX_LOG_MESSAGES_PER_SECOND)
    {
      va_start (args, msg);
      log_vprintf (msg, args);
      va_end (args);
    }
}
#else
/* Disabled for Windows which doesn't provide syslog.h upon which logging service
   depends.  Note that usage-logging isn't upstreamed yet */

int usage_log_enabled (void)
{
    return 0;
}

void usage_log_start (int argc, char **argv)
{
}

void usage_log_end (int exit_code)
{
}

void usage_log_printf (const char *msg, ...)
{
}

void usage_log_flush (void)
{
}

#endif
