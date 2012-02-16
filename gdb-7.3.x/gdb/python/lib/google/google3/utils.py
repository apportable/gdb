# Collection of google3 gdb utilities for use by system.gdbinit.

import sys
import os
import gdb

# Look for FILE in the current directory, and every parent directory until
# we find it.
# Return the path of FILE if found or None if not found.

def _find_file (file):
  cwd = os.getcwd ()
  while cwd != "/":
    if cwd == "/auto" or cwd == "/home":
      # For http://b/3349958, don't ask automounter to try mounting
      # "/{home,auto}/build-info.txt"
      # As of 2011/01/13, /etc/auto.master on corp gLucid has just "/home"
      # and "/auto".  We could parse /etc/auto.master instead of hard-coding
      # this, but I think that would be an overkill.
      return None
    trial = "%s/%s" % (cwd, file)
    if os.path.exists (trial):
      return trial
    cwd = os.path.dirname (cwd)
  return None

# Assuming FILE contains lines of the form "key value", return the value
# of KEY, or None if not found.

def _find_key (file, key):
  f = open (file)
  for line in f:
    if line.startswith ("%s " % key):
      f.close ()
      value = line[len (key) + 1 : ].strip ()
      return value
  f.close ()
  return None

# Return true if FILE contains TEXT.
# Returns false if not found or if FILE is inaccessible.

def _file_contains(file, text):
  try:
    f = open(file)
    try:
      for line in f:
        if text in line:
          f.close()
          return True
    finally:
      f.close()
    return False
  except IOError:
    return False

# Return the path of the parent of the top level google3 directory,
# or None if we're not in a google3 tree.
# Things are slightly tricky because we have to handle the case of being
# in an arbitrary location in the build tree, and there is no published
# interface for getting back to the source tree, and obtaining a published
# interface has proved problematic.  http://b/2260941  http://b/2316983
#
# We *have* to do something, telling GDB users they're out of luck is a
# non-starter.  For now we use an unpublished interface that at least
# The Powers That Be are not unhappy with us using.
# We keep looking up the build tree for file build-info.txt.
# Inside that file there is BUILD_DIRECTORY which we can use.

def _get_google3_path ():
  build_info_txt = _find_file ("build-info.txt")
  if build_info_txt is not None:
    build_directory = _find_key (build_info_txt, "BUILD_DIRECTORY")
    if build_directory is not None:
      return build_directory
  cwd = os.getcwd ()
  if cwd.endswith ("/google3"):
    return cwd
  cwd_index = cwd.rfind ("/google3/")
  if cwd_index > 0:
    return cwd[0 : cwd_index + 8]
  return None

# Utility to append PATH to sys.path (if not already present).

def _append_sys_path(path):
  # Python2 canonicalizes directories in sys.path, so we do too.
  path = os.path.abspath(path)
  if os.path.exists(path) and \
      path not in sys.path:
    sys.path.append(path)

# Add google3 paths to the source search directory if necessary.
#
# WITH_GOOGLE3_IMPORT is true if we're in a tree new enough that we
# import google3.  This affects sys.path.
# ref: http://b/4088983, http://b/4495043
#
# Note: There's an unfortunate inconsistency in path usage.
# Paths in dwarf debug info are recorded with a compilation directory of
# /proc/self/cwd which is a google3 directory, and the file name being a
# relative path from there.  Because of this, paths recorded in
# .debug_gdb_scripts use the same relative starting point - they are
# searched for using the same path list as source files.
# Alas python modules in google3 are searched from a starting point of the
# parent of google3.  So for example if the source search path is
# $HOME/src/google3 the python sys.path entry is $HOME/src.
# It's not a problem per se, other than a potential source of confusion.

def _add_google3_paths(google3_path, with_google3_import):
  # Start with a canonicalized path.
  google3_parent_path = os.path.abspath(os.path.dirname(google3_path))
  # For consistency, reestablish google3 relative to that.
  google3_path = "%s/google3" % google3_parent_path
  readonly_path = None
  readonly_google3_path = None

  directories = gdb.parameter("directories")
  if directories.find("/google3/") < 0 \
        and directories.find ("/google3:") < 0:
    # Update the source search paths.
    if os.path.exists("%s/READONLY/google3" % google3_parent_path):
      readonly_path = "%s/READONLY" % google3_parent_path
      readonly_google3_path = "%s/google3" % readonly_path
      gdb.execute("dir %s" % readonly_google3_path)
    gdb.execute("dir %s" % google3_path)

  if with_google3_import:
    # Google3 python files are looked up from a starting point of the parent
    # of google3.
    # Only add the google3 parent.  The "import google3" we do later will
    # add the necessary support for finding things in READONLY.
    _append_sys_path(google3_parent_path)
    # Import google3/__init__.py.
    # It provides the necessary support to handle importing modules across a
    # split srcfs tree.  E.g., google3/devtools/__init__.py and
    # READONLY/google3/devtools/gdb/component/__init__.py.
    # Without help, python can't find google3.devtools.gdb.component.
    # http://b/4088983
    if os.path.exists("%s/__init__.py" % google3_path):
      import google3
    else:
      # Alas, google3/__init__.py may not exist.  It must be in
      # ../READONLY/google3/__init__.py.  Oy vey!
      if os.path.exists("%s/__init__.py" % readonly_google3_path):
        # Python2 canonicalizes directories in sys.path, so we do too.
        abs_readonly_path = os.path.abspath(readonly_path)
        was_in_sys_path = abs_readonly_path in sys.path
        if not was_in_sys_path:
          _append_sys_path(abs_readonly_path)
        import google3
        if not was_in_sys_path:
          sys.path.remove(abs_readonly_path)
      else:
        raise RuntimeError("Can't find google3/__init__.py")
  else:
    if readonly_google3_path is not None:
      _append_sys_path(readonly_google3_path)
    _append_sys_path(google3_path)

# Return true if the google3 tree is new enough that we can use
# google3/__init__.py to handle module searching.
# ref: bugs 4088983, 4495043
#
# TODO(dje): Over time we may want some sort of version number of the
# google3 gdb code.  Alas we currently don't have one, other than trying to
# determine the CL of a particular file.
# The salient change is that files now import modules with google3 in the
# module path.

def _use_google3_import(google3_path):
  test_file = "devtools/gdb/component/core/stringpiece.py"
  return _file_contains("%s/%s" % (google3_path, test_file),
                        "google3.devtools") \
      or _file_contains("%s/../READONLY/google3/%s" % (google3_path, test_file),
                        "google3.devtools")

# Set up gdb to debug google3 code.
# Most of the setup should be done by google3 source files.
# This does the minimum to bootstrap the process.

def _add_google3_settings(google3_path):
  with_google3_import = _use_google3_import(google3_path)

  _add_google3_paths(google3_path, with_google3_import)

  if with_google3_import:
    # This is ideally the last thing we do, we want as much google3
    # initialization to live in google3.
    # Be careful not to fail if gdbinit.py isn't present.
    # Eventually we'll want to remove this and expect gdbinit.py to be present.
    # But that will have to wait until it's reasonable and the standard
    # timeframe for that is one year (12q2), http://b/4518701.
    # We only do this if with_google3_import because gdbinit.py was created
    # at about the same time that we fixed http://b/4495043.
    try:
      from google3.devtools.gdb.component.gdbinit import InitializeGDBForGoogle3
      InitializeGDBForGoogle3()
    except ImportError:
      pass

# If we're in a google3 tree:
# - ensure google3 (+READONLY) is in gdb's directory search path
#   and python's module search path if we're in a google3 tree
# - change various defaults for use with google3 code

def maybe_add_google3_settings():
  google3_path = _get_google3_path()
  if google3_path != None:
    _add_google3_settings(google3_path)
