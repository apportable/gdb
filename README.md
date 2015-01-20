Apportable gdb
==============

Apportable gdb is a fork of the [Android NDK gdb](https://android.googlesource.com/toolchain/gdb/). It also includes patches from the [Fennec Android fork of gdb](https://github.com/darchons/android-gdb)

The primary differentiator of the Apportable gdb fork is the addition of Objective C debugging support.


Building Production Version of gdb
----------------------------------

- git clone git@github.com:apportable/gdb.git
- mkdir gdb_build
- cd gdb_build
- CFLAGS="-g -O2 -Wno-unused-value -Wno-unused-function" ~/gdb/configure --target=arm-elf-linux --enable-targets=all --with-python=yes
- make
- ls -l gdb/gdb


Building Debug Version of gdb
-----------------------------

- git clone git@github.com:apportable/gdb.git (if not already done)
- mkdir gdb_debug
- cd gdb_debug
- CFLAGS="-g -Wno-unused-value -Wno-unused-function" ~/gdb/configure --target=arm-elf-linux --enable-targets=all --with-python=yes
- make
- ls -l gdb/gdb


Debugging gdb
-------------
- Rebuild/debug your program ...
- In another shell  ps -ef | grep gdb
- gdb attach {pid of built gdb}
- set any breakpoints in gdb source
- continue