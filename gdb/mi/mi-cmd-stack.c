/* MI Command Set - stack commands.
   Copyright (C) 2000, 2002-2005, 2007-2012 Free Software Foundation,
   Inc.
   Contributed by Cygnus Solutions (a Red Hat company).

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

#include "defs.h"
#include "arch-utils.h"
#include "target.h"
#include "frame.h"
#include "value.h"
#include "mi-cmds.h"
#include "ui-out.h"
#include "symtab.h"
#include "block.h"
#include "stack.h"
#include "dictionary.h"
#include "gdb_string.h"
#include "language.h"
#include "valprint.h"
#include "exceptions.h"
#include "objfiles.h"
#include "psymtab.h"
#include <ctype.h>  /* for isnumber */

enum what_to_list { locals, arguments, all };

static void list_args_or_locals (enum what_to_list what, 
				 enum print_values values,
				 struct frame_info *fi);

/* Print a list of the stack frames.  Args can be none, in which case
   we want to print the whole backtrace, or a pair of numbers
   specifying the frame numbers at which to start and stop the
   display.  If the two numbers are equal, a single frame will be
   displayed.  */

void
mi_cmd_stack_list_frames (char *command, char **argv, int argc)
{
  int frame_low;
  int frame_high;
  int i;
  struct cleanup *cleanup_stack;
  struct frame_info *fi;

  if (argc > 2 || argc == 1)
    error (_("-stack-list-frames: Usage: [FRAME_LOW FRAME_HIGH]"));

  if (argc == 2)
    {
      frame_low = atoi (argv[0]);
      frame_high = atoi (argv[1]);
    }
  else
    {
      /* Called with no arguments, it means we want the whole
         backtrace.  */
      frame_low = -1;
      frame_high = -1;
    }

  /* Let's position fi on the frame at which to start the
     display. Could be the innermost frame if the whole stack needs
     displaying, or if frame_low is 0.  */
  for (i = 0, fi = get_current_frame ();
       fi && i < frame_low;
       i++, fi = get_prev_frame (fi));

  if (fi == NULL)
    error (_("-stack-list-frames: Not enough frames in stack."));

  cleanup_stack = make_cleanup_ui_out_list_begin_end (current_uiout, "stack");

  /* Now let's print the frames up to frame_high, or until there are
     frames in the stack.  */
  for (;
       fi && (i <= frame_high || frame_high == -1);
       i++, fi = get_prev_frame (fi))
    {
      QUIT;
      /* Print the location and the address always, even for level 0.
         If args is 0, don't print the arguments.  */
      print_frame_info (fi, 1, LOC_AND_ADDRESS, 0 /* args */ );
    }

  do_cleanups (cleanup_stack);
}

/* Apple addition begin */

/* Helper print function for mi_cmd_stack_list_frames_lite */

/* FRAME_NUM will be unmodified if this function only prints a single
   concrete frame.  It will be incremented once for each inlined frame
   that is printed in addition to the concrete frame.  */

static void 
mi_print_frame_info_lite_base (struct ui_out *uiout,
             int with_names,
             int *frame_num,
             CORE_ADDR pc,
             CORE_ADDR fp)
{
  char num_buf[8];
  struct cleanup *list_cleanup;
  struct gdbarch *gdbarch = get_current_arch ();
  struct obj_section *osect;

#if 0
// Apportable TODO
  print_inlined_frames_lite (uiout, with_names, frame_num, pc, fp);
#endif

  sprintf (num_buf, "%d", *frame_num);
  ui_out_text (uiout, "Frame ");
  ui_out_text(uiout, num_buf);
  ui_out_text(uiout, ": ");
  list_cleanup = make_cleanup_ui_out_tuple_begin_end (uiout, num_buf);
  ui_out_field_core_addr (uiout, "pc", gdbarch, pc);
  ui_out_field_core_addr (uiout, "fp", gdbarch, fp);

  osect = find_pc_section (pc);
  if (osect != NULL && osect->objfile != NULL && osect->objfile->name != NULL)
      ui_out_field_string (uiout, "shlibname", osect->objfile->name);
  else 
      ui_out_field_string (uiout, "shlibname", "<UNKNOWN>");

  if (with_names)
    {
      struct minimal_symbol *msym ;
      struct obj_section *osect;
      int has_debug_info = 0;

      /* APPLE LOCAL: if we are going to print names, we should raise
         the load level to ALL.  We will avoid doing psymtab to symtab,
         since we just want the function */

#if 0
// Apportable TODO
      pc_set_load_state (pc, OBJF_SYM_ALL, 0);
#endif
      msym = lookup_minimal_symbol_by_pc (pc);
      if (msym == NULL)
  ui_out_field_string (uiout, "func", "<\?\?\?\?>");
      else
  {
    const char *name = SYMBOL_PRINT_NAME (msym);
    if (name == NULL)
      ui_out_field_string (uiout, "func", "<\?\?\?\?>");
    else
      ui_out_field_string (uiout, "func", name);
  } 
      /* This is a pretty quick and dirty way to check whether there
   are debug symbols for this PC...  I don't care WHAT symbol
   contains the PC, just that there's some psymtab that
   does.  */
      osect = find_pc_sect_in_ordered_sections (pc, NULL);
      if (osect != NULL && osect->the_bfd_section != NULL)
  {
    struct partial_symtab *psymtab_for_pc = find_pc_sect_psymtab_apple (pc, osect);
    if (psymtab_for_pc != NULL)
      has_debug_info = 1;
    else
      has_debug_info = 0;
    
  }
      ui_out_field_int (uiout, "has_debug", has_debug_info);
    }
  ui_out_text (uiout, "\n");
  do_cleanups (list_cleanup);
}

static void
mi_print_frame_info_with_names_lite (struct ui_out *uiout,
        int *frame_num,
        CORE_ADDR pc,
        CORE_ADDR fp)
{
  mi_print_frame_info_lite_base (uiout, 1, frame_num, pc, fp);
}

static void
mi_print_frame_info_lite (struct ui_out *uiout,
        int *frame_num,
        CORE_ADDR pc,
        CORE_ADDR fp)
{
  mi_print_frame_info_lite_base (uiout, 0, frame_num, pc, fp);
}

/* Print a list of the PC and Frame Pointers for each frame in the stack;
   also return the total number of frames. An optional argument "-limit"
   can be give to limit the number of frames printed. 
   An optional "-names (0|1)" flag can be given which if 1 will cause the names to
   get printed with the backtrace.
  */

void
mi_cmd_stack_list_frames_lite (char *command, char **argv, int argc)
{
    int limit;
    int start;
    int count_limit;
    int names;
    int valid;
    unsigned int count = 0;
    void (*print_fun) (struct ui_out*, int*, CORE_ADDR, CORE_ADDR);
    struct ui_out *uiout = current_uiout;

#ifndef FAST_COUNT_STACK_DEPTH
    int i;
    struct frame_info *fi;
#endif

    if (!target_has_stack)
        error ("mi_cmd_stack_list_frames_lite: No stack.");

    if ((argc > 8))
        error ("mi_cmd_stack_list_frames_lite: Usage: [-names (0|1)] [-start start-num] "
               "[-limit max_frame_number] [-count_limit how_many_to_count]");

    limit = -1;
    names = 0;
    count_limit = -1;
    start = 0;

    while (argc > 0)
      {
  if (strcmp (argv[0], "-limit") == 0)
    {
      if (argc == 1)
        error ("mi_cmd_stack_list_frames_lite: No argument to -limit.");

      if (! isnumber (argv[1][0]))
        error ("mi_cmd_stack_list_frames_lite: Invalid argument to -limit.");
      limit = atoi (argv[1]);
      argc -= 2;
      argv += 2;
    }
  else if (strcmp (argv[0], "-start") == 0)
          {
            if (argc == 1)
              error ("mi_cmd_stack_list_frames_lite: No argument to -start.");

            if (! isnumber (argv[1][0]))
              error ("mi_cmd_stack_list_frames_lite: Invalid argument to -start.");
            start = atoi (argv[1]);
            argc -= 2;
            argv += 2;
          }
  else if (strcmp (argv[0], "-count_limit") == 0)
          {
            if (argc == 1)
              error ("mi_cmd_stack_list_frames_lite: No argument to -count_limit.");

            if (! isnumber (argv[1][0]))
              error ("mi_cmd_stack_list_frames_lite: Invalid argument to -count_limit.");
            count_limit = atoi (argv[1]);
            argc -= 2;
            argv += 2;
          }
  else if (strcmp (argv[0], "-names") == 0)
    {
      if (argc == 1)
        error ("mi_cmd_stack_list_frames_lite: No argument to -names.");

      if (! isnumber (argv[1][0]))
        error ("mi_cmd_stack_list_frames_lite: Invalid argument to -names.");
      names = atoi (argv[1]);
      argc -= 2;
      argv += 2;
    }
  else
    error ("mi_cmd_stack_list_frames_lite: invalid flag: %s", argv[0]);
      }
  

    if (names)
      print_fun = mi_print_frame_info_with_names_lite;
    else
      print_fun = mi_print_frame_info_lite;

#ifdef FAST_COUNT_STACK_DEPTH
    valid = FAST_COUNT_STACK_DEPTH (count_limit, start, limit, &count, print_fun);
#else
    /* Start at the inner most frame */
    {
      struct cleanup *list_cleanup;
      for (fi = get_current_frame (); fi ; fi = get_next_frame(fi))
        ;

      fi = get_current_frame ();
      
      if (fi == NULL)
        error ("mi_cmd_stack_list_frames_lite: No frames in stack.");
      
      list_cleanup = make_cleanup_ui_out_list_begin_end (uiout, "frames");
      
      for (i = 0; fi != NULL; (fi = get_prev_frame (fi)), i++) 
  {
    QUIT;
    
    if ((limit == -1) || (i >= start && i < limit))
      {
        int j;
        print_fun (uiout, &i, get_frame_pc (fi), 
                                        get_frame_base(fi));
              j = frame_relative_level (fi);
              while ((j < i) && (fi != NULL))
                {
                  fi = get_prev_frame (fi);
                  ++j;
                }
              if (fi == NULL)
                  break;
      }
    if (count_limit != -1 && i > count_limit)
      break;
  }
      
      count = i;
      valid = 1;
      do_cleanups (list_cleanup);
    }
#endif
    
    ui_out_text (uiout, "Valid: ");
    ui_out_field_int (uiout, "valid", valid);
    ui_out_text (uiout, "\nCount: ");
    ui_out_field_int (uiout, "count", count);
    ui_out_text (uiout, "\n");
}

/* Apple addition end */

void
mi_cmd_stack_info_depth (char *command, char **argv, int argc)
{
  int frame_high;
  int i;
  struct frame_info *fi;

  if (argc > 1)
    error (_("-stack-info-depth: Usage: [MAX_DEPTH]"));

  if (argc == 1)
    frame_high = atoi (argv[0]);
  else
    /* Called with no arguments, it means we want the real depth of
       the stack.  */
    frame_high = -1;

  for (i = 0, fi = get_current_frame ();
       fi && (i < frame_high || frame_high == -1);
       i++, fi = get_prev_frame (fi))
    QUIT;

  ui_out_field_int (current_uiout, "depth", i);
}

static enum print_values
parse_print_values (char *name)
{
   if (strcmp (name, "0") == 0
       || strcmp (name, mi_no_values) == 0)
     return PRINT_NO_VALUES;
   else if (strcmp (name, "1") == 0
	    || strcmp (name, mi_all_values) == 0)
     return PRINT_ALL_VALUES;
   else if (strcmp (name, "2") == 0
	    || strcmp (name, mi_simple_values) == 0)
     return PRINT_SIMPLE_VALUES;
   else
     error (_("Unknown value for PRINT_VALUES: must be: \
0 or \"%s\", 1 or \"%s\", 2 or \"%s\""),
	    mi_no_values, mi_all_values, mi_simple_values);
}

/* Print a list of the locals for the current frame.  With argument of
   0, print only the names, with argument of 1 print also the
   values.  */

void
mi_cmd_stack_list_locals (char *command, char **argv, int argc)
{
  struct frame_info *frame;

  if (argc != 1)
    error (_("-stack-list-locals: Usage: PRINT_VALUES"));

   frame = get_selected_frame (NULL);

   list_args_or_locals (locals, parse_print_values (argv[0]), frame);
}

/* Print a list of the arguments for the current frame.  With argument
   of 0, print only the names, with argument of 1 print also the
   values.  */

void
mi_cmd_stack_list_args (char *command, char **argv, int argc)
{
  int frame_low;
  int frame_high;
  int i;
  struct frame_info *fi;
  struct cleanup *cleanup_stack_args;
  enum print_values print_values;
  struct ui_out *uiout = current_uiout;

  if (argc < 1 || argc > 3 || argc == 2)
    error (_("-stack-list-arguments: Usage: "
	     "PRINT_VALUES [FRAME_LOW FRAME_HIGH]"));

  if (argc == 3)
    {
      frame_low = atoi (argv[1]);
      frame_high = atoi (argv[2]);
    }
  else
    {
      /* Called with no arguments, it means we want args for the whole
         backtrace.  */
      frame_low = -1;
      frame_high = -1;
    }

  print_values = parse_print_values (argv[0]);

  /* Let's position fi on the frame at which to start the
     display. Could be the innermost frame if the whole stack needs
     displaying, or if frame_low is 0.  */
  for (i = 0, fi = get_current_frame ();
       fi && i < frame_low;
       i++, fi = get_prev_frame (fi));

  if (fi == NULL)
    error (_("-stack-list-arguments: Not enough frames in stack."));

  cleanup_stack_args
    = make_cleanup_ui_out_list_begin_end (uiout, "stack-args");

  /* Now let's print the frames up to frame_high, or until there are
     frames in the stack.  */
  for (;
       fi && (i <= frame_high || frame_high == -1);
       i++, fi = get_prev_frame (fi))
    {
      struct cleanup *cleanup_frame;

      QUIT;
      cleanup_frame = make_cleanup_ui_out_tuple_begin_end (uiout, "frame");
      ui_out_field_int (uiout, "level", i);
      list_args_or_locals (arguments, print_values, fi);
      do_cleanups (cleanup_frame);
    }

  do_cleanups (cleanup_stack_args);
}

/* Print a list of the local variables (including arguments) for the 
   current frame.  ARGC must be 1 and ARGV[0] specify if only the names,
   or both names and values of the variables must be printed.  See 
   parse_print_value for possible values.  */

void
mi_cmd_stack_list_variables (char *command, char **argv, int argc)
{
  struct frame_info *frame;

  if (argc != 1)
    error (_("Usage: PRINT_VALUES"));

  frame = get_selected_frame (NULL);

  list_args_or_locals (all, parse_print_values (argv[0]), frame);
}

/* Print single local or argument.  ARG must be already read in.  For
   WHAT and VALUES see list_args_or_locals.

   Errors are printed as if they would be the parameter value.  Use
   zeroed ARG iff it should not be printed according to VALUES.  */

static void
list_arg_or_local (const struct frame_arg *arg, enum what_to_list what,
		   enum print_values values)
{
  struct cleanup *old_chain;
  struct cleanup *cleanup_tuple = NULL;
  struct ui_out *uiout = current_uiout;
  struct ui_file *stb;

  stb = mem_fileopen ();
  old_chain = make_cleanup_ui_file_delete (stb);

  gdb_assert (!arg->val || !arg->error);
  gdb_assert ((values == PRINT_NO_VALUES && arg->val == NULL
	       && arg->error == NULL)
	      || values == PRINT_SIMPLE_VALUES
	      || (values == PRINT_ALL_VALUES
		  && (arg->val != NULL || arg->error != NULL)));
  gdb_assert (arg->entry_kind == print_entry_values_no
	      || (arg->entry_kind == print_entry_values_only
	          && (arg->val || arg->error)));

  if (values != PRINT_NO_VALUES || what == all)
    cleanup_tuple = make_cleanup_ui_out_tuple_begin_end (uiout, NULL);

  fputs_filtered (SYMBOL_PRINT_NAME (arg->sym), stb);
  if (arg->entry_kind == print_entry_values_only)
    fputs_filtered ("@entry", stb);
  ui_out_field_stream (uiout, "name", stb);

  if (what == all && SYMBOL_IS_ARGUMENT (arg->sym))
    ui_out_field_int (uiout, "arg", 1);

  if (values == PRINT_SIMPLE_VALUES)
    {
      check_typedef (arg->sym->type);
      type_print (arg->sym->type, "", stb, -1);
      ui_out_field_stream (uiout, "type", stb);
    }

  if (arg->val || arg->error)
    {
      volatile struct gdb_exception except;

      if (arg->error)
	except.message = arg->error;
      else
	{
	  /* TRY_CATCH has two statements, wrap it in a block.  */

	  TRY_CATCH (except, RETURN_MASK_ERROR)
	    {
	      struct value_print_options opts;

	      get_raw_print_options (&opts);
	      opts.deref_ref = 1;
	      common_val_print (arg->val, stb, 0, &opts,
				language_def (SYMBOL_LANGUAGE (arg->sym)));
	    }
	}
      if (except.message)
	fprintf_filtered (stb, _("<error reading variable: %s>"),
			  except.message);
      ui_out_field_stream (uiout, "value", stb);
    }

  if (values != PRINT_NO_VALUES || what == all)
    do_cleanups (cleanup_tuple);
  do_cleanups (old_chain);
}

/* Print a list of the locals or the arguments for the currently
   selected frame.  If the argument passed is 0, printonly the names
   of the variables, if an argument of 1 is passed, print the values
   as well.  */

static void
list_args_or_locals (enum what_to_list what, enum print_values values,
		     struct frame_info *fi)
{
  struct block *block;
  struct symbol *sym;
  struct block_iterator iter;
  struct cleanup *cleanup_list;
  struct type *type;
  char *name_of_result;
  struct ui_out *uiout = current_uiout;

  block = get_frame_block (fi, 0);

  switch (what)
    {
    case locals:
      name_of_result = "locals";
      break;
    case arguments:
      name_of_result = "args";
      break;
    case all:
      name_of_result = "variables";
      break;
    default:
      internal_error (__FILE__, __LINE__,
		      "unexpected what_to_list: %d", (int) what);
    }

  cleanup_list = make_cleanup_ui_out_list_begin_end (uiout, name_of_result);

  while (block != 0)
    {
      ALL_BLOCK_SYMBOLS (block, iter, sym)
	{
          int print_me = 0;

	  switch (SYMBOL_CLASS (sym))
	    {
	    default:
	    case LOC_UNDEF:	/* catches errors        */
	    case LOC_CONST:	/* constant              */
	    case LOC_TYPEDEF:	/* local typedef         */
	    case LOC_LABEL:	/* local label           */
	    case LOC_BLOCK:	/* local function        */
	    case LOC_CONST_BYTES:	/* loc. byte seq.        */
	    case LOC_UNRESOLVED:	/* unresolved static     */
	    case LOC_OPTIMIZED_OUT:	/* optimized out         */
	      print_me = 0;
	      break;

	    case LOC_ARG:	/* argument              */
	    case LOC_REF_ARG:	/* reference arg         */
	    case LOC_REGPARM_ADDR:	/* indirect register arg */
	    case LOC_LOCAL:	/* stack local           */
	    case LOC_STATIC:	/* static                */
	    case LOC_REGISTER:	/* register              */
	    case LOC_COMPUTED:	/* computed location     */
	      if (what == all)
		print_me = 1;
	      else if (what == locals)
		print_me = !SYMBOL_IS_ARGUMENT (sym);
	      else
		print_me = SYMBOL_IS_ARGUMENT (sym);
	      break;
	    }
	  if (print_me)
	    {
	      struct symbol *sym2;
	      struct frame_arg arg, entryarg;

	      if (SYMBOL_IS_ARGUMENT (sym))
		sym2 = lookup_symbol (SYMBOL_LINKAGE_NAME (sym),
				      block, VAR_DOMAIN,
				      (int *) NULL);
	      else
		sym2 = sym;
	      gdb_assert (sym2 != NULL);

	      memset (&arg, 0, sizeof (arg));
	      arg.sym = sym2;
	      arg.entry_kind = print_entry_values_no;
	      memset (&entryarg, 0, sizeof (entryarg));
	      entryarg.sym = sym2;
	      entryarg.entry_kind = print_entry_values_no;

	      switch (values)
		{
		case PRINT_SIMPLE_VALUES:
		  type = check_typedef (sym2->type);
		  if (TYPE_CODE (type) != TYPE_CODE_ARRAY
		      && TYPE_CODE (type) != TYPE_CODE_STRUCT
		      && TYPE_CODE (type) != TYPE_CODE_UNION)
		    {
		case PRINT_ALL_VALUES:
		      read_frame_arg (sym2, fi, &arg, &entryarg);
		    }
		  break;
		}

	      if (arg.entry_kind != print_entry_values_only)
		list_arg_or_local (&arg, what, values);
	      if (entryarg.entry_kind != print_entry_values_no)
		list_arg_or_local (&entryarg, what, values);
	      xfree (arg.error);
	      xfree (entryarg.error);
	    }
	}

      if (BLOCK_FUNCTION (block))
	break;
      else
	block = BLOCK_SUPERBLOCK (block);
    }
  do_cleanups (cleanup_list);
}

void
mi_cmd_stack_select_frame (char *command, char **argv, int argc)
{
  if (argc == 0 || argc > 1)
    error (_("-stack-select-frame: Usage: FRAME_SPEC"));

  select_frame_command (argv[0], 1 /* not used */ );
}

void
mi_cmd_stack_info_frame (char *command, char **argv, int argc)
{
  if (argc > 0)
    error (_("-stack-info-frame: No arguments allowed"));

  print_frame_info (get_selected_frame (NULL), 1, LOC_AND_ADDRESS, 0);
}
