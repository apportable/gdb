# Pretty-printers for google3.

# Copyright (C) 2009, 2010 Google, Inc.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gdb
import gdb.printing
import gdb.types
#import itertools
import libstdcxx.v6.printers
import re


class GoogScopedPointerPrinter:
    "Print base/scoped_ptr"

    size_type = gdb.lookup_type('unsigned long')

    def __init__(self, val):
        self.val = val

    def to_string(self):
        ptr = self.val['ptr_']
        return '(%s) 0x%x' % (ptr.type,
                              ptr.cast(GoogScopedPointerPrinter.size_type))


# Not really Google-specific, but deprecated in libstdc++
class _HashTableIterator:
    "Iterate over elements of __gnu_cxx::hashtable"

    def __init__ (self, val):
        self.val = val
        self.size = val['_M_num_elements']
        buckets = val['_M_buckets']['_M_impl']
        start = buckets['_M_start']
        finish = buckets['_M_finish']
        self.nbuckets = long (finish - start)
        self.count = 0
        self.bucket = 0
        self.listpos = 0

    def __iter__ (self):
        return self

    def __len__(self):
        return int (self.size)

    def next (self):
        if self.size <= self.count or self.nbuckets <= self.bucket:
            raise StopIteration
        v = self.val['_M_buckets']['_M_impl']['_M_start']
        while self.bucket < self.nbuckets:
            if v[self.bucket]:
                break
            self.bucket = self.bucket + 1
        if self.nbuckets <= self.bucket:
            raise StopIteration
        xl = v[self.bucket]
        lpos = 0
        while lpos < self.listpos:
            xl = xl['_M_next']
            lpos = lpos + 1
            if not xl:
                self.listpos = 0
                self.bucket = self.bucket + 1
                return self.next()
        self.count = self.count + 1
        self.listpos = self.listpos + 1
        return xl['_M_val']


class HashTablePrinter:
    "Print a __gnu_cxx::hash_map or hash_set"

    class _iter:
        def __init__ (self, size, is_map, val):
            self.count = 0
            self.is_map = is_map
            self.htiter = _HashTableIterator (val)

        def __iter__(self):
            return self

        def next(self):
            if self.is_map:
                if self.count % 2 == 0:
                    self.item = self.htiter.next()
                    item = self.item['first']
                else:
                    item = self.item['second']
            else:
                self.item = self.htiter.next()
                item = self.item
            result = ('[%d]' % self.count, item)
            self.count = self.count + 1
            return result

    def __init__ (self, typename, is_map, val):
        val = val['_M_ht']
        self.typename = typename
        self.val = val
        self.is_map = is_map
        self.size = val['_M_num_elements']
        self.iter = self._iter (self.size, is_map, val)

    def to_string (self):
        return '%s with %d elements' % (self.typename, self.size)

    def children (self):
        return self.iter

    def display_hint (self):
        if self.is_map: return 'map'
        return None


class ProtoArrayPrinter:
    """Generic ProtoArray printer."""

    def __init__(self, val, space_field, size_field, name):
        self.val = val
        self.name = name
        self.size_field = size_field
        self.space_field = space_field

    def to_string(self):
        first = True
        space = self.val[self.space_field]
        n = self.val[self.size_field]
        if n == -842150451:  # 0xCDCDCDCD
            return '*** DANGLING ***'
        if n <= 0:
            return ''
        limit = gdb.parameter('print elements')
        if limit and limit < n:
          # Ensure a reasonable limit (http://b/4551340)
          n = limit
        result = ''
        for i in range(n):
            if not first:
                result += ' '
            value = space[i]
            if self.name:
                result += '%s:' % self.name

            try:
                result += str(value)
            except RuntimeError, err:
                result += '<GDB/Python runtime error: %s>' % err
                break

            first = False
        if self.name:
            return result
        return '<' + result + '>'


class Proto1ArrayPrinter(ProtoArrayPrinter):
    """ProtoArray compiled with cc_api_version = 1."""
    def __init__(self, val, name = ''):
        tp = gdb.types.get_basic_type(val.type)
        typename = tp.tag
        match = re.compile(r"ProtoArray<(.+)>").match(typename)
        if match:
            p2 = "proto2::RepeatedField<%s>" % match.group(1)
            if inherits_from_p(tp, [ p2 ]):
                ProtoArrayPrinter.__init__(self, val, 'elements_',
                                           'current_size_', name)
            else:
                ProtoArrayPrinter.__init__(self, val, 'space_',
                                           'size_', name)
        else:
            raise ("Unexpected type %s, please notify gdb-team" %
                   typename)


class Proto2ArrayPrinter(ProtoArrayPrinter):
    """ProtoArray compiled with cc_api_version = 2."""
    def __init__(self, val, name = ''):
        ProtoArrayPrinter.__init__(self, val, 'elements_', 'current_size_',
                                   name)


class ProtoPtrArrayPrinter:
    """Generic ProtoPtrArray printer."""

    def __init__(self, val, space_field, size_field, name):
        self.val = val
        self.name = name
        self.size_field = size_field
        self.space_field = space_field

    def to_string(self):
        first = True
        space = self.val[self.space_field]
        n = self.val[self.size_field]
        if n == -842150451:  # 0xCDCDCDCD
            return '*** DANGLING ***'
        if n <= 0:
            return ''
        limit = gdb.parameter('print elements')
        if limit and limit < n:
          # Ensure a reasonable limit (http://b/4551340)
          n = limit
        result = ''
        tp = self.val.type.template_argument(0).pointer()
        for i in range(n):
            if not first:
                result += ' '
            value = space[i].cast(tp).dereference()
            if self.name:
                result += '%s:' % self.name

            try:
                result += str(value)
            except RuntimeError, err:
                result += '<GDB/Python runtime error: %s>' % err
                break

            first = False
        if self.name:
            return result
        return '<' + result + '>'


class Proto1PtrArrayPrinter(ProtoPtrArrayPrinter):
    """ProtoPtrArray compiled with cc_api_version = 1."""
    def __init__(self, val, name = ''):
        tp = gdb.types.get_basic_type(val.type)
        if inherits_from_p(tp, [ "proto2::internal::RepeatedPtrFieldBase" ]):
            ProtoPtrArrayPrinter.__init__(self, val, 'elements_',
                                          'current_size_', name)
        else:
            ProtoPtrArrayPrinter.__init__(self, val, 'space_',
                                          'size_', name)


class Proto2PtrArrayPrinter(ProtoPtrArrayPrinter):
    """ProtoPtrArray compiled with cc_api_version = 2."""
    def __init__(self, val, name = ''):
        ProtoPtrArrayPrinter.__init__(self, val, 'elements_', 'current_size_',
                                      name)


class ProtoMessagePrinter:
  """Common to proto1 and proto2."""

  def __init__(self, val):
    self.val = val
    self.type = gdb.types.get_basic_type(val.type)
    self.uint_type = gdb.lookup_type('unsigned int')

  def repeated_field(self, name):
    """Convert a repeated field to string."""
    val = self.val[name]
    tp = val.type
    if tp.code == gdb.TYPE_CODE_PTR and name == 'items_':
      # message-set
      n = val['size_']
      if n == 0:
          return '<>'
      return '[ MessageSet with %d element%s ]' % (n, n != 1 and 's' or '')
    if tp.tag[:10] == 'ProtoArray':
      return Proto1ArrayPrinter(val, name[:-1]).to_string()
    elif tp.tag[:21] ==  'proto2::RepeatedField':
      return Proto2ArrayPrinter(val, name[:-1]).to_string()
    elif tp.tag[:13] == 'ProtoPtrArray':
      return Proto1PtrArrayPrinter(val, name[:-1]).to_string()
    elif tp.tag[:24] == 'proto2::RepeatedPtrField':
      return Proto2PtrArrayPrinter(val, name[:-1]).to_string()
    else:
      raise RuntimeError("Don't know how to handle " + tp.tag)

  def to_string_repeated_only(self):
    """Print ProtocolMessage containing only repeated fields."""

    result = '<'
    first = True

    # Skip first field: ProtocolMessage...
    for field in self.type.fields()[1:]:
      fname = field.name
      # print 'YY %s' % fname
      if fname == 'unknown_fields_':
        break
      if fname[:1] == '_':
        # _cached_byte_size_
        continue
      try:
        bitpos = field.bitpos
      except:
        # skip static fields
        continue

      try:
        t = self.repeated_field(fname)
        if t:
          if not first:
            result += ' '
          first = False
          result += t
      except RuntimeError, err:
        result += '<%s: GDB/Python runtime error: %s>' % (fname, err)

    return result + '>'

  def string_to_octal(self, value):
      length = value['_M_string_length']
      begin = value['_M_dataplus']['_M_p']
      limit = gdb.parameter('print elements')
      nchars = length
      if limit and limit < nchars:
          nchars = limit

      result = ''
      for i in range(nchars):
          uc = int(begin[i])
          if uc < 0:
              uc += 255
          result += '\\%03o' % uc

      if nchars < length:
          result += '...'
      return result


class Proto1MessagePrinter(ProtoMessagePrinter):
    def __init__(self, val):
        ProtoMessagePrinter.__init__(self, val)

    def to_string(self):
        """Print ProtocolMessage compiled with cc_api_version = 1."""

        if not gdb.types.has_field(self.val.type, 'hasbits_'):
            # This message contains only repeated fields.
            return self.to_string_repeated_only()

        result = '<'
        first = True

        try:
            hasbits = self.val['hasbits_']
            bits = 0
            for i in range(hasbits.type.sizeof):
                bits |= (hasbits[i].cast(self.uint_type) << (8*i))
        except RuntimeError, err:
            return '<<GDB/Python runtime error: %s>>' % err

        # Skip first field: ProtocolMessage...
        for field in self.type.fields()[1:]:
            field_name = field.name
            if (field_name == 'unknown_fields_' or
                field_name == 'hasbits_' or
                field_name[:1] == '_'):
                continue

            # Strip trailing '_'.
            name = field.name[:-1]
            kBit_name = 'kHasBit_' + name

            try:
                bitpos = field.bitpos
            except:
                # skip static fields
                continue

            try:
                kBit = self.val[kBit_name]
            except:
                kBit = None

            try:
                if kBit is None:
                    t = self.repeated_field(field.name)
                    if t:
                        if not first:
                            result += ' '
                        result += t
                        first = False
                elif kBit >= 0:
                    if bits & (1 << kBit):
                        if not first:
                            result += ' '
                        value = self.val[field.name]
                        if value.type.code == gdb.TYPE_CODE_PTR:
                            # optional fields are represented as pointers
                            value = value.dereference()
                        try:
                            result += '%s:%s' % (name, value)
                        except UnicodeEncodeError:
                            # A string containing non-ASCII chars.
                            result += '%s:%s' % (name, self.string_to_octal(value))

                        first = False
                else:
                    # kHasBit_* should never be negative,
                    # but it has happened (http://b/3190112).  Cope.
                    # It should be rare, and when this happens we want
                    # to know about it so it can be fixed.
                    if not first:
                        result += ' '
                    result += "<%s: bad kHasBit value: %d>" % (field.name, kBit)
                    first = False
            except RuntimeError, err:
                result += '<%s: GDB/Python runtime error: %s>' % (name, err)

        return result + '>'


class Proto2MessagePrinter(ProtoMessagePrinter):
  def __init__(self, val):
    ProtoMessagePrinter.__init__(self, val)

  def sort_data_fields(self, field_number_fields, data_fields):
      """Sort data_fields in the order they appear in _has_bits_.

      Proto-v2 no longer has kHasBit_ fields.  We need these values in order
      to properly index _has_bits_, which can be different than the order
      gdb records them as due to CL 15224047 which reorders data fields a
      bit so that they pack better.
      To achieve the sort we do use the order of the corresponding
      kFooFieldNumber field.

      Args:
        field_number_fields: A list of the k<name>FieldNumber fields of the
          type, sorted by appearance in the source file.
          This takes dubious advantage of the fact that the order of appearance
          in the debug info is the same.
          TODO(dje): Use `offsets_' from the reflection type?
        data_fields: An unsorted list of the data fields.

      Returns:
        None if there are no duplicates, or the index of the first duplicated
        field (rare, but possible).
        Duplicates can happen because of the ambiguous mapping from field name
        and camelcase name to sorting index.  It's very rare, but we need to
        handle it.

        The sorted field list is recorded in data_fields.
      """

      def dict_key(field_name):
          """Return a dictionary key for field_name.

          Args:
            field_name: Either the name of a data field or a kFooFieldNumber
              field.

          Result:
            The key.
            For example, if the data_field is named "foo_bar_", the
            field-number-field will be named kFooBarFieldNumber.
            We want the same key for both.
            NOTE: This isn't perfect, foo_bar_ and fo_obar_ will have the
            same key.  The caller needs to catch duplicates.
          """
          return field_name.lower().replace("_", "")

      sort_dict = {}
      i = 0
      dup_index = None
      for f in field_number_fields:
          # Take "Foo" from "kFooFieldNumber", and pass that to dict_key.
          key = dict_key(f.name[1:-11])
          # Watch for duplicates.
          # Once we find a duplicate, all subsequent entries are possibly
          # invalid because we will have lost track of its index in _has_bits_.
          if key in sort_dict:
              index = sort_dict[key]
              if dup_index is None or index < dup_index:
                  dup_index = index
          else:
              sort_dict[key] = i
          i += 1
      data_fields.sort(key = lambda x: sort_dict[dict_key(x.name)])
      return dup_index

  def sorted_printable_fields(self):
      """Return sorted list of fields to print.

      The field list we get may not be the same as how they appear in the
      .proto file, the protocol compiler may have reordered them.
      We need to sort the fields according to how they appear
      in the .proto file.  This is done for two reasons:
      1) The user would probably like to see them in that order,
      2) but more importantly, values in _has_bits_ are still organized
         according to source file order!

      Result:
        Tuple of (extension_field, dup_index, sorted_data_fields).
        extension_field: "_extension_" field or None if not present.
        dup_index: None or the index of the first duplicate field.
          See sort_data_fields.

      TODO(dje): Use the 'offsets_' member of the reflection object?
      """

      extension_field = None
      data_fields = []
      field_number_fields = []
      # "(_[0-9]*)?" is to handle
      # net/proto2/compiler/cpp/internal/helpers.cc:FieldConstantName,
      # it may add "_<field-number>" to "k<name>FieldNumber".
      field_number_field_re = re.compile('^k.*FieldNumber(_[0-9]*)?$')

      # Fetch the fields we need to do the printing.
      # Skip the first field, it's proto2::Message.
      for field in self.type.fields()[1:]:
          if field.name == '_extensions_':
              extension_field = field
              continue
          # _unknown_fields_, _has_bits_, _cached_size_, etc.
          if field.name[:1] == '_':
              continue
          if field_number_field_re.match(field.name):
              field_number_fields.append(field)
              continue
          # Data fields have a bitpos member.
          try:
              bitpos = field.bitpos
              data_fields.append(field)
          except:
              continue # skip static fields

      # The test uses >= because extension fields get a FieldNumber field,
      # but don't add new data fields.
      assert len(field_number_fields) >= len(data_fields)

      dup_index = self.sort_data_fields(field_number_fields, data_fields)
      return (extension_field, dup_index, data_fields)

  def to_string(self):
      """Print ProtocolMessage compiled with cc_api_version = 2."""

      if not gdb.types.has_field(self.val.type, '_has_bits_'):
          # This message contains only repeated fields.
          return self.to_string_repeated_only()

      result = '<'
      first = True

      try:
          bits = self.val['_has_bits_'][0]

          (extension_field, dup_index, data_fields) = \
              self.sorted_printable_fields()

          # There are no kHas... constants in v2 :-(
          # So we count them explicitly.
          kBit = -1

          if extension_field is not None:
              extensions = self.val['_extensions_']['extensions_']
              node_count = extensions['_M_t']['_M_impl']['_M_node_count']
              result += '[ MessageSet with %d element%s ]' \
                  % (node_count, node_count != 1 and 's' or '')
      except RuntimeError, err:
          return '<<%GDB/Python runtime error: %s>>' % err

      for field in data_fields:

          # Strip trailing '_'.
          name = field.name[:-1]
          kBit += 1

          if (dup_index is not None and
                kBit >= dup_index):
              result += ' remaining fields are unavailable>'
              return result

          try:
              if bits & (1 << kBit):
                  if not first:
                      result += ' '
                  value = self.val[field.name]
                  if value.type.code == gdb.TYPE_CODE_PTR:
                      # optional fields are represented as pointers
                      value = value.dereference()
                  try:
                      result += '%s:%s' % (name, value)
                  except UnicodeEncodeError:
                      # A string containing non-ASCII chars.
                      result += '%s:%s' % (name, self.string_to_octal(value))

                  first = False
              else:
                  # Could be missing, or repeated field.
                  tp = field.type.strip_typedefs()
                  if tp.tag and re.compile('^proto2::Repeated').match(tp.tag):
                      t = self.repeated_field(field.name)
                      if t:
                          if not first:
                              result += ' '
                          first = False
                          result += t
          except RuntimeError, err:
              result += '<%s: GDB/Python runtime error: %s>' % (name, err)

      return result + '>'


# WARNING: The real StringPiece pretty-printer now lives in
# google3/devtools/gdb/component/core/stringpiece.py.
# This is kept, for now, to support older binaries.

class StringPiecePrinter:
    """Print StringPiece, as defined in strings/stringpiece.h."""

    def __init__ (self, val):
        self.val = val

    def to_string (self):
        limit = gdb.parameter('print elements')
        length = self.val['length_']
        if limit and limit < length:
          length = limit

        ptr = self.val['ptr_']
        s = ptr.string('ISO-8859-1', 'ignore', length)
        if limit is not None and length > limit:
            s += " ..."
        return "StringPiece of length %d: \"%s\"" % (length, s)


# WARNING: The real StringPiece pretty-printer now lives in
# google3/devtools/gdb/component/core/cord.py.
# This is kept, for now, to support older binaries.

class CordPrinter:
    """Print Cord, as defined in strings/cord.h."""

    # CordRep tags. They must match those defined in cord.cc.
    TAG_CONCAT = 0
    TAG_FUNCTION = 1
    TAG_SUBSTRING = 2
    TAG_FLAT = 3
    OLD_TAG_FLAT = 4 # prior to CL 16155200

    def __init__ (self, val):
        self.val = val
        # Record whether we have a new-style (post CL 16155200) Cord
        # or an old-style Cord.
        try:
            contents = val["contents_"]
            self.has_contents = True
        except RuntimeError:
            self.has_contents = False

    def to_string(self):
        """GDB calls this to compute the pretty-printed form."""
        if self.has_contents:
            # Cord has member "contents", it uses the new InlinedRep class.
            contents = self.val["contents_"]
            u = contents["u_"]
            data = u["data"]
            if self.is_tree(self.val):
                rep_ptr = data.cast(u["aligner"].type.pointer())
                rep = rep_ptr.dereference()
                body = self.print_rep(rep)
                length = rep["length"]
                refcount = rep["refcount"]
            else:
                N = contents["N"]
                length = data[N]
                body = data.string("ISO-8859-1", "ignore", length)
                refcount = 1
        else:
            # Old-style cord, no InlinedRep.
            rep = self.val["rep_"]
            body = self.print_rep(rep)
            length = rep["length"]
            refcount = rep["refcount"]
        limit = gdb.parameter("print elements")
        if limit and limit < len(body):
          body = body[0:limit] + " ..."
        return "Cord of length %d, refcnt %d: \"%s\"" % (length, refcount, body)

    def is_tree(self, cord):
        contents = cord["contents_"]
        N = contents["N"]
        data = contents["u_"]["data"]
        return data[N] > N

    def print_rep(self, rep):
        """Print a CordRep object."""

        length = rep["length"]
        tag = rep["tag"]

        # >= is used because of the way cord is implemented.
        # There are multiple tag values >= TAG_FLAT.
        # Each one indicates a different allocation size.
        if (self.has_contents and tag >= self.TAG_FLAT) or \
              (not self.has_contents and tag >= self.OLD_TAG_FLAT):
            data = rep["data"]
            return data.string("ISO-8859-1", "ignore", length)

        if tag == self.TAG_CONCAT:
            concat = rep["concat"]
            left = self.print_rep(concat["left"])
            right = self.print_rep(concat["right"])
            return left + right

        if tag == self.TAG_SUBSTRING:
            substr = rep["substring"]
            s = self.print_rep(substr["child"])
            start = substr["start"]
            # start and length have type gdb.Value which isn't currently
            # usable in a slice, so convert to ints.
            return s[int(start) : int(start + length)]

        if tag == self.TAG_FUNCTION:
            return "<cord function>"

        # This path shouldn't be taken, except when Cord is corrupted.
        return "<unknown tag: %d>" % tag


class ArrayIterator:
    """Helper class used to print array elements."""

    def __init__ (self, array, size):
        self.pointer = array
        self.size = size
        self.count = 0

    def __iter__ (self):
        return self

    def next (self):
        if self.count >= self.size:
            raise StopIteration
        elt = self.pointer.dereference()
        count = self.count
        self.pointer = self.pointer + 1
        self.count = self.count + 1
        return ('[%d]' % count, elt)


class FixedArrayPrinter:
    """Print FixedArray, as defined in util/gtl/fixedarray.h."""

    def __init__(self, val):
        self.val = val

    def to_string (self):
        return "FixedArray of length %d" % self.val["size_"];

    def children(self):
        return ArrayIterator(self.val["array_"], self.val["size_"])


class InlinedVectorPrinter:
    """Print InlinedVector, as defined in util/gtl/inlined_vector.h."""

    def __init__(self, val):
        self.val = val
        self.size = self.val["tag_"] >> 1

        # LSB of tag_ == 0  => Elements are stored in u_.inlined.storage
        # LSB of tag_ == 1  => Elements are stored in u_.allocated.space
        inlined = ((self.val["tag_"] & 1) == 0)
        if inlined:
            itype = self.val.type.template_argument(0)
            # Cast u_.inlined.storage to T*
            self.array = self.val["u_"]["inlined"]["storage"].cast(
                itype.pointer())
        else:
            self.array = self.val["u_"]["allocated"]["space"]

    def to_string (self):
        return "util::gtl::InlinedVector of length %d" % self.size

    def children(self):
        return ArrayIterator(self.array, self.size)


# This is currently lacking support for 'is_base_class':
#  http://sourceware.org/ml/archer/2009-q2/msg00176.html
#  http://sourceware.org/ml/archer/2009-q3/msg00001.html
# TODO(dje): baseclass support is present now

def inherits_from_p(tp, candidates):
    """Determine if TP 'is a' (inherits from) one of candidates."""

    fields = tp.fields()
    if len(fields):
        f0 = fields[0]
        # A field may have the same type as enclosing class (if the field
        # is static). If the first field is static, we aren't inheriting
        # from anything.
        try:
            bitpos = f0.bitpos
        except:
            # a static field
            return None

        f0type = f0.type
        if not f0type:
            return None
        f0type = f0type.strip_typedefs()
        if f0type.tag in candidates:
            return True
        return inherits_from_p(f0type, candidates)
    return None


def register_google3_printers (obj):
    "Register google3 pretty-printers with objfile Obj."

    if obj is None:
        obj = gdb

    gdb.printing.register_pretty_printer (obj, build_google3_printer())

    # N.B. We need to register the protobuf2 printer *before* the protobuf1
    # printer, new printers are added to the head of the list.
    # Protobuf1's MessageProtocol class inherits from protobuf2's
    # proto2::Message class!  Thus we need to look for protobuf1's first,
    # due to the way we recognize protobuf1's we also recognize them as
    # protobuf2's.
    gdb.printing.register_pretty_printer (obj, Protobuf2PrettyPrinter ())
    gdb.printing.register_pretty_printer (obj, Protobuf1PrettyPrinter ())


# Protobuffers have to be handled differently as there isn't a consistent
# naming convention (and thus a simple regexp can't work).

class Protobuf1PrettyPrinter (gdb.printing.PrettyPrinter):
    """Protobuf v1 pretty-printer."""

    def __init__ (self):
        super (Protobuf1PrettyPrinter, self).__init__ ("builtin-protobuf1")

    @staticmethod
    def is_proto1_message(tp):
        return inherits_from_p(tp, ['ProtocolMessage',
                                    'ProtocolMessageGroup'])

    def __call__ (self, val):
        tp = gdb.types.get_basic_type (val.type)
        typename = tp.tag
        if typename is None:
            return None
        # TODO(dje): Is this noticeably expensive?
        if Protobuf1PrettyPrinter.is_proto1_message (tp):
            return Proto1MessagePrinter (val)
        return None


class Protobuf2PrettyPrinter (gdb.printing.PrettyPrinter):
    """Protobuf v2 pretty-printer."""

    def __init__ (self):
        super (Protobuf2PrettyPrinter, self).__init__ ("builtin-protobuf2")

    @staticmethod
    def is_proto2_message(tp):
        return inherits_from_p(tp, ['proto2::Message',
                                    'proto2::internal::GenericRepeatedField'])

    def __call__ (self, val):
        tp = gdb.types.get_basic_type (val.type)
        typename = tp.tag
        if typename is None:
            return None
        # TODO(dje): Is this noticeably expensive?
        if Protobuf2PrettyPrinter.is_proto2_message (tp):
            return Proto2MessagePrinter (val)
        return None


def build_google3_printer():
    # google3 objects with builtin pretty-printing support.
    # TODO(dje): Move all of this to google3.

    pp = gdb.printing.RegexpCollectionPrettyPrinter("builtin-google3")

    pp.add_printer('scoped_ptr', '^scoped_ptr<.*>$',
                   GoogScopedPointerPrinter)

    # For versa_string:
    pp.add_printer('basic_string<char>', '^basic_string<char.*>$',
                   lambda val: libstdcxx.v6.printers.StdStringPrinter(0, val))
    pp.add_printer('basic_string<wchar_t>', '^basic_string<wchar_t.*>$',
                   lambda val: libstdcxx.v6.printers.StdStringPrinter(1, val))

    pp.add_printer('__gnu_cxx::hash_map', '^__gnu_cxx::hash_map<.*>$',
                   lambda val: HashTablePrinter('__gnu_cxx::hash_map',
                                                True, val))
    pp.add_printer('__gnu_cxx::hash_set', '^__gnu_cxx::hash_set<.*>$',
                   lambda val: HashTablePrinter('__gnu_cxx::hash_set',
                                                False, val))

    # ProtocolBuffer support
    # These are for printing parts of protocol buffers.
    # The top level printer has to be handled differently as there is no
    # consistent naming scheme.
    pp.add_printer('ProtoArray', '^ProtoArray<.*>$',
                   Proto1ArrayPrinter)
    pp.add_printer('ProtoPtrArray', '^ProtoPtrArray<.*>$',
                   Proto1PtrArrayPrinter)
    pp.add_printer('proto2::RepeatedField', '^proto2::RepeatedField<.*>$',
                   Proto2ArrayPrinter)
    pp.add_printer('proto2::RepeatedPtrField', '^proto2::RepeatedPtrField<.*>$',
                   Proto2PtrArrayPrinter)

    pp.add_printer('Cord', '^Cord$', CordPrinter)
    pp.add_printer('StringPiece', '^StringPiece$', StringPiecePrinter)
    pp.add_printer('FixedArray', '^FixedArray<.*>$',
                   FixedArrayPrinter)
    pp.add_printer('util::gtl::InlinedVector', '^util::gtl::InlinedVector<.*>$',
                   InlinedVectorPrinter)

    return pp
