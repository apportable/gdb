# Pretty-printers for libstc++.

# Copyright (C) 2008, 2009, 2010 Free Software Foundation, Inc.

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
import itertools


class StdPointerPrinter:
    "Print a smart pointer of some kind"

    def __init__ (self, typename, val):
        self.typename = typename
        self.val = val

    def to_string (self):
        if self.val['_M_refcount']['_M_pi'] == 0:
            return '%s (empty) %s' % (self.typename, self.val['_M_ptr'])
        return '%s (count %d) %s' % (self.typename,
                                     self.val['_M_refcount']['_M_pi']['_M_use_count'],
                                     self.val['_M_ptr'])


class UniquePointerPrinter:
    "Print a unique_ptr"

    def __init__ (self, val):
        self.val = val

    def to_string (self):
        return self.val['_M_t']


class StdListPrinter:
    "Print a std::list"

    class _iterator:
        def __init__(self, nodetype, head):
            self.nodetype = nodetype
            self.base = head['_M_next']
            self.head = head.address
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            if self.base == self.head:
                raise StopIteration
            elt = self.base.cast(self.nodetype).dereference()
            self.base = elt['_M_next']
            count = self.count
            self.count = self.count + 1
            return ('[%d]' % count, elt['_M_data'])

    def __init__(self, typename, val):
        self.typename = typename
        self.val = val

    def children(self):
        itype = self.val.type.template_argument(0)
        # If the inferior program is compiled with -D_GLIBCXX_DEBUG
        # some of the internal implementation details change.
        if self.typename == "std::list":
            nodetype = gdb.lookup_type('std::_List_node<%s>' % itype).pointer()
        elif self.typename == "std::__debug::list":
            nodetype = gdb.lookup_type('std::__norm::_List_node<%s>' % itype).pointer()
        else:
            raise "Cannot cast list node for list printer."
        return self._iterator(nodetype, self.val['_M_impl']['_M_node'])

    def to_string(self):
        if self.val['_M_impl']['_M_node'].address == self.val['_M_impl']['_M_node']['_M_next']:
            return 'empty %s' % (self.typename)
        return '%s' % (self.typename)


class StdListIteratorPrinter:
    "Print std::list::iterator"

    def __init__(self, typename, val):
        self.val = val
        self.typename = typename

    def to_string(self):
        itype = self.val.type.template_argument(0)
        # If the inferior program is compiled with -D_GLIBCXX_DEBUG
        # some of the internal implementation details change.
        if self.typename == "std::_List_iterator" or self.typename == "std::_List_const_iterator":
            nodetype = gdb.lookup_type('std::_List_node<%s>' % itype).pointer()
        elif self.typename == "std::__norm::_List_iterator" or self.typename == "std::__norm::_List_const_iterator":
            nodetype = gdb.lookup_type('std::__norm::_List_node<%s>' % itype).pointer()
        else:
            raise "Cannot cast list node for list iterator printer."
        return self.val['_M_node'].cast(nodetype).dereference()['_M_data']


class StdSlistPrinter:
    "Print a __gnu_cxx::slist"

    class _iterator:
        def __init__(self, nodetype, head):
            self.nodetype = nodetype
            self.base = head['_M_head']['_M_next']
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            if self.base == 0:
                raise StopIteration
            elt = self.base.cast(self.nodetype).dereference()
            self.base = elt['_M_next']
            count = self.count
            self.count = self.count + 1
            return ('[%d]' % count, elt['_M_data'])

    def __init__(self, val):
        self.val = val

    def children(self):
        itype = self.val.type.template_argument(0)
        nodetype = gdb.lookup_type('__gnu_cxx::_Slist_node<%s>' % itype).pointer()
        return self._iterator(nodetype, self.val)

    def to_string(self):
        if self.val['_M_head']['_M_next'] == 0:
            return 'empty __gnu_cxx::slist'
        return '__gnu_cxx::slist'


class StdSlistIteratorPrinter:
    "Print __gnu_cxx::slist::iterator"

    def __init__(self, val):
        self.val = val

    def to_string(self):
        itype = self.val.type.template_argument(0)
        nodetype = gdb.lookup_type('__gnu_cxx::_Slist_node<%s>' % itype).pointer()
        return self.val['_M_node'].cast(nodetype).dereference()['_M_data']


class StdVectorPrinter:
    "Print a std::vector"

    class _iterator:
        def __init__ (self, start, finish):
            self.item = start
            self.finish = finish
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            if self.item == self.finish:
                raise StopIteration
            count = self.count
            self.count = self.count + 1
            elt = self.item.dereference()
            self.item = self.item + 1
            return ('[%d]' % count, elt)

    def __init__(self, typename, val):
        self.typename = typename
        self.val = val

    def children(self):
        return self._iterator(self.val['_M_impl']['_M_start'],
                              self.val['_M_impl']['_M_finish'])

    def to_string(self):
        start = self.val['_M_impl']['_M_start']
        finish = self.val['_M_impl']['_M_finish']
        end = self.val['_M_impl']['_M_end_of_storage']
        return ('%s of length %d, capacity %d'
                % (self.typename, int (finish - start), int (end - start)))

    def display_hint(self):
        return 'array'


class StdVectorIteratorPrinter:
    "Print std::vector::iterator"

    def __init__(self, val):
        self.val = val

    def to_string(self):
        return self.val['_M_current'].dereference()


class StdStackOrQueuePrinter:
    "Print a std::stack or std::queue"

    def __init__ (self, typename, val):
        self.typename = typename
        self.visualizer = gdb.default_visualizer(val['c'])

    def children (self):
        return self.visualizer.children()

    def to_string (self):
        return '%s wrapping: %s' % (self.typename,
                                    self.visualizer.to_string())

    def display_hint (self):
        if hasattr (self.visualizer, 'display_hint'):
            return self.visualizer.display_hint ()
        return None


class RbtreeIterator:
    def __init__(self, rbtree):
        self.size = rbtree['_M_t']['_M_impl']['_M_node_count']
        self.node = rbtree['_M_t']['_M_impl']['_M_header']['_M_left']
        self.count = 0

    def __iter__(self):
        return self

    def __len__(self):
        return int (self.size)

    def next(self):
        if self.count == self.size:
            raise StopIteration
        result = self.node
        self.count = self.count + 1
        if self.count < self.size:
            # Compute the next node.
            node = self.node
            if node.dereference()['_M_right']:
                node = node.dereference()['_M_right']
                while node.dereference()['_M_left']:
                    node = node.dereference()['_M_left']
            else:
                parent = node.dereference()['_M_parent']
                while node == parent.dereference()['_M_right']:
                    node = parent
                    parent = parent.dereference()['_M_parent']
                if node.dereference()['_M_right'] != parent:
                    node = parent
            self.node = node
        return result


# This is a pretty printer for std::_Rb_tree_iterator (which is
# std::map::iterator), and has nothing to do with the RbtreeIterator
# class above.

class StdRbtreeIteratorPrinter:
    "Print std::map::iterator"

    def __init__ (self, val):
        self.val = val

    def to_string (self):
        valuetype = self.val.type.template_argument(0)
        nodetype = gdb.lookup_type('std::_Rb_tree_node < %s >' % valuetype)
        nodetype = nodetype.pointer()
        return self.val.cast(nodetype).dereference()['_M_value_field']


class StdDebugIteratorPrinter:
    "Print a debug enabled version of an iterator"

    def __init__ (self, val):
        self.val = val

    # Just strip away the encapsulating __gnu_debug::_Safe_iterator
    # and return the wrapped iterator value.
    def to_string (self):
        itype = self.val.type.template_argument(0)
        return self.val['_M_current'].cast(itype)


class StdMapPrinter:
    "Print a std::map or std::multimap"

    # Turn an RbtreeIterator into a pretty-print iterator.
    class _iter:
        def __init__(self, rbiter, type):
            self.rbiter = rbiter
            self.count = 0
            self.type = type

        def __iter__(self):
            return self

        def next(self):
            if self.count % 2 == 0:
                n = self.rbiter.next()
                n = n.cast(self.type).dereference()['_M_value_field']
                self.pair = n
                item = n['first']
            else:
                item = self.pair['second']
            result = ('[%d]' % self.count, item)
            self.count = self.count + 1
            return result

    def __init__ (self, typename, val):
        self.typename = typename
        self.val = val
        self.iter = RbtreeIterator (val)

    def to_string (self):
        return '%s with %d elements' % (self.typename, len (self.iter))

    def children (self):
        keytype = self.val.type.template_argument(0).const()
        valuetype = self.val.type.template_argument(1)
        nodetype = gdb.lookup_type('std::_Rb_tree_node< std::pair< %s, %s > >' % (keytype, valuetype))
        nodetype = nodetype.pointer()
        return self._iter (self.iter, nodetype)

    def display_hint (self):
        return 'map'


class StdSetPrinter:
    "Print a std::set or std::multiset"

    # Turn an RbtreeIterator into a pretty-print iterator.
    class _iter:
        def __init__(self, rbiter, type):
            self.rbiter = rbiter
            self.count = 0
            self.type = type

        def __iter__(self):
            return self

        def next(self):
            item = self.rbiter.next()
            item = item.cast(self.type).dereference()['_M_value_field']
            # FIXME: this is weird ... what to do?
            # Maybe a 'set' display hint?
            result = ('[%d]' % self.count, item)
            self.count = self.count + 1
            return result

    def __init__ (self, typename, val):
        self.typename = typename
        self.val = val
        self.iter = RbtreeIterator (val)

    def to_string (self):
        return '%s with %d elements' % (self.typename, len (self.iter))

    def children (self):
        keytype = self.val.type.template_argument(0)
        nodetype = gdb.lookup_type('std::_Rb_tree_node< %s >' % keytype).pointer()
        return self._iter (self.iter, nodetype)


class StdBitsetPrinter:
    "Print a std::bitset"

    def __init__(self, typename, val):
        self.typename = typename
        self.val = val

    def to_string (self):
        # If template_argument handled values, we could print the
        # size.  Or we could use a regexp on the type.
        return '%s' % (self.typename)

    def children (self):
        words = self.val['_M_w']
        wtype = words.type

        # The _M_w member can be either an unsigned long, or an
        # array.  This depends on the template specialization used.
        # If it is a single long, convert to a single element list.
        if wtype.code == gdb.TYPE_CODE_ARRAY:
            tsize = wtype.target ().sizeof
        else:
            words = [words]
            tsize = wtype.sizeof

        nwords = wtype.sizeof / tsize
        result = []
        byte = 0
        while byte < nwords:
            w = words[byte]
            bit = 0
            while w != 0:
                if (w & 1) != 0:
                    # Another spot where we could use 'set'?
                    result.append(('[%d]' % (byte * tsize * 8 + bit), 1))
                bit = bit + 1
                w = w >> 1
            byte = byte + 1
        return result


class StdDequePrinter:
    "Print a std::deque"

    class _iter:
        def __init__(self, node, start, end, last, buffer_size):
            self.node = node
            self.p = start
            self.end = end
            self.last = last
            self.buffer_size = buffer_size
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            if self.p == self.last:
                raise StopIteration

            result = ('[%d]' % self.count, self.p.dereference())
            self.count = self.count + 1

            # Advance the 'cur' pointer.
            self.p = self.p + 1
            if self.p == self.end:
                # If we got to the end of this bucket, move to the
                # next bucket.
                self.node = self.node + 1
                self.p = self.node[0]
                self.end = self.p + self.buffer_size

            return result

    def __init__(self, typename, val):
        self.typename = typename
        self.val = val
        self.elttype = val.type.template_argument(0)
        size = self.elttype.sizeof
        if size < 512:
            self.buffer_size = int (512 / size)
        else:
            self.buffer_size = 1

    def to_string(self):
        start = self.val['_M_impl']['_M_start']
        end = self.val['_M_impl']['_M_finish']

        delta_n = end['_M_node'] - start['_M_node'] - 1
        delta_s = start['_M_last'] - start['_M_cur']
        delta_e = end['_M_cur'] - end['_M_first']

        size = self.buffer_size * delta_n + delta_s + delta_e

        return '%s with %d elements' % (self.typename, long (size))

    def children(self):
        start = self.val['_M_impl']['_M_start']
        end = self.val['_M_impl']['_M_finish']
        return self._iter(start['_M_node'], start['_M_cur'], start['_M_last'],
                          end['_M_cur'], self.buffer_size)

    def display_hint (self):
        return 'array'


class StdDequeIteratorPrinter:
    "Print std::deque::iterator"

    def __init__(self, val):
        self.val = val

    def to_string(self):
        return self.val['_M_cur'].dereference()


class StdStringPrinter:
    "Print a std::basic_string of some kind"

    def __init__(self, encoding, val):
        self.encoding = encoding
        self.val = val

    def get_length(self):
        typename = str(gdb.types.get_basic_type(self.val.type))
        if typename[:5] == "std::":
            # std::wstring or std::string
            begin = self.val['_M_dataplus']['_M_p']
            # http://b/4378978
            try:
              type = gdb.lookup_type('%s::_Rep' % typename)
            except RuntimeError:
              # Try again, stripping off std::.
              type = gdb.lookup_type('%s::_Rep' % typename[5:])
            type = type.pointer()
            length = begin.cast(type)[-1]['_M_length']
        else:
            # versa_string aka google3 string
            length = self.val['_M_string_length']
        return length

    def to_string(self):
        # Look up the target encoding as late as possible.
        encoding = self.encoding

        result = []
        begin = self.val['_M_dataplus']['_M_p']
        length = self.get_length()
        limit = gdb.parameter('print elements')
        if limit != None:
            nchars = min(length, limit)
        else:
            nchars = length

        if encoding == 0:
            encoding = gdb.parameter('target-charset')
            try:
                return begin.string(encoding, length = length)
            except:
                return begin

        elif encoding == 1:
            encoding = gdb.parameter('target-wide-charset')

            # GRTE python does not understand UCS-4
            # Hack courtesy jyasskin.
            if encoding == 'UCS-4':
                for i in range(nchars):
                    # Don't crash on bad characters.
                    try:
                        result.append(unichr(begin[i]))
                    except:
                        result.append("\\x%x/" % begin[i])
                if nchars < length:
                    result.append('...')
                return ''.join(result)
            # End GRTE hack.

        # FIXME: WideEncoding didn't get brought over from archer.
        #elif isinstance(encoding, WideEncoding):
        #    encoding = encoding.value
        return self.val['_M_dataplus']['_M_p'].string(encoding)

    def display_hint (self):
        return 'string'


class Tr1HashtableIterator:
    def __init__ (self, hash):
        self.count = 0
        self.n_buckets = hash['_M_element_count']
        if self.n_buckets == 0:
            self.node = False
        else:
            self.bucket = hash['_M_buckets']
            self.node = self.bucket[0]
            self.update ()

    def __iter__ (self):
        return self

    def update (self):
        # If we advanced off the end of the chain, move to the next
        # bucket.
        while self.node == 0:
            self.bucket = self.bucket + 1
            self.node = self.bucket[0]

       # If we advanced off the end of the bucket array, then
       # we're done.
        if self.count == self.n_buckets:
            self.node = False
        else:
            self.count = self.count + 1

    def next (self):
        if not self.node:
            raise StopIteration
        result = self.node.dereference()['_M_v']
        self.node = self.node.dereference()['_M_next']
        self.update ()
        return result


class Tr1UnorderedSetPrinter:
    "Print a tr1::unordered_set"

    def __init__ (self, typename, val):
        self.typename = typename
        self.val = val

    def to_string (self):
        return '%s with %d elements' % (self.typename, self.val['_M_element_count'])

    @staticmethod
    def format_count (i):
        return '[%d]' % i

    def children (self):
        counter = itertools.imap (self.format_count, itertools.count())
        return itertools.izip (counter, Tr1HashtableIterator (self.val))


class Tr1UnorderedMapPrinter:
    "Print a tr1::unordered_map"

    def __init__ (self, typename, val):
        self.typename = typename
        self.val = val

    def to_string (self):
        return '%s with %d elements' % (self.typename, self.val['_M_element_count'])

    @staticmethod
    def flatten (list):
        for elt in list:
            for i in elt:
                yield i

    @staticmethod
    def format_one (elt):
        return (elt['first'], elt['second'])

    @staticmethod
    def format_count (i):
        return '[%d]' % i

    def children (self):
        counter = itertools.imap (self.format_count, itertools.count())
        # Map over the hash table and flatten the result.
        data = self.flatten (itertools.imap (self.format_one, Tr1HashtableIterator (self.val)))
        # Zip the two iterators together.
        return itertools.izip (counter, data)

    def display_hint (self):
        return 'map'


def register_libstdcxx_printers (obj):
    """Register libstdc++ pretty-printers with objfile Obj."""

    if obj == None:
        obj = gdb

    gdb.printing.register_pretty_printer (obj, build_libstdcxx_printer())


def build_libstdcxx_printer():
    # libstdc++ objects requiring pretty-printing.
    # In order from:
    # http://gcc.gnu.org/onlinedocs/libstdc++/latest-doxygen/a01847.html

    pp = gdb.printing.RegexpCollectionPrettyPrinter("builtin-libstdc++")

    pp.add_printer('std::basic_string<char>', '^std::basic_string<char,.*>$', lambda val: StdStringPrinter (0, val))
    pp.add_printer('std::basic_string<wchar_t>', '^std::basic_string<wchar_t,.*>$', lambda val: StdStringPrinter (1, val))
    pp.add_printer('std::basic_string<char16_t>', '^std::basic_string<char16_t,.*>$', lambda val: StdStringPrinter ('UTF-16', val))
    pp.add_printer('std::basic_string<char32_t>', '^std::basic_string<char32_t,.*>$', lambda val: StdStringPrinter ('UTF-32', val))
    pp.add_printer('std::bitset', '^std::bitset<.*>$', lambda val: StdBitsetPrinter ("std::bitset", val))
    pp.add_printer('std::deque', '^std::deque<.*>$', lambda val: StdDequePrinter ("std::deque", val))
    pp.add_printer('std::list', '^std::list<.*>$', lambda val: StdListPrinter ("std::list", val))
    pp.add_printer('std::map', '^std::map<.*>$', lambda val: StdMapPrinter ("std::map", val))
    pp.add_printer('std::multimap', '^std::multimap<.*>$', lambda val: StdMapPrinter ("std::multimap", val))
    pp.add_printer('std::multiset', '^std::multiset<.*>$', lambda val: StdSetPrinter ("std::multiset", val))
    pp.add_printer('std::priority_queue', '^std::priority_queue<.*>$', lambda val: StdStackOrQueuePrinter ("std::priority_queue", val))
    pp.add_printer('std::queue', '^std::queue<.*>$', lambda val: StdStackOrQueuePrinter ("std::queue", val))
    pp.add_printer('std::set', '^std::set<.*>$', lambda val: StdSetPrinter ("std::set", val))
    pp.add_printer('std::stack', '^std::stack<.*>$', lambda val: StdStackOrQueuePrinter ("std::stack", val))
    pp.add_printer('std::unique_ptr', '^std::unique_ptr<.*>$', UniquePointerPrinter)
    pp.add_printer('std::vector', '^std::vector<.*>$', lambda val: StdVectorPrinter ("std::vector", val))
    # vector<bool>

    # Printer registrations for classes compiled with -D_GLIBCXX_DEBUG.
    pp.add_printer('std::__debug::bitset', '^std::__debug::bitset<.*>$', lambda val: StdBitsetPrinter ("std::__debug::bitset", val))
    pp.add_printer('std::__debug::deque', '^std::__debug::deque<.*>$', lambda val: StdDequePrinter ("std::__debug::deque", val))
    pp.add_printer('std::__debug::list', '^std::__debug::list<.*>$', lambda val: StdListPrinter ("std::__debug::list", val))
    pp.add_printer('std::__debug::map', '^std::__debug::map<.*>$', lambda val: StdMapPrinter ("std::__debug::map", val))
    pp.add_printer('std::__debug::multimap', '^std::__debug::multimap<.*>$', lambda val: StdMapPrinter ("std::__debug::multimap", val))
    pp.add_printer('std::__debug::multiset', '^std::__debug::multiset<.*>$', lambda val: StdSetPrinter ("std::__debug::multiset", val))
    pp.add_printer('std::__debug::priority_queue', '^std::__debug::priority_queue<.*>$', lambda val: StdStackOrQueuePrinter ("std::__debug::priority_queue", val))
    pp.add_printer('std::__debug::queue', '^std::__debug::queue<.*>$', lambda val: StdStackOrQueuePrinter ("std::__debug::queue", val))
    pp.add_printer('std::__debug::set', '^std::__debug::set<.*>$', lambda val: StdSetPrinter ("std::__debug::set", val))
    pp.add_printer('std::__debug::stack', '^std::__debug::stack<.*>$', lambda val: StdStackOrQueuePrinter ("std::__debug::stack", val))
    pp.add_printer('std::__debug::unique_ptr', '^std::__debug::unique_ptr<.*>$', UniquePointerPrinter)
    pp.add_printer('std::__debug::vector', '^std::__debug::vector<.*>$', lambda val: StdVectorPrinter ("std::__debug::vector", val))

    # These are the TR1 and C++0x printers.
    # For array - the default GDB pretty-printer seems reasonable.
    pp.add_printer('std::shared_ptr', '^std::shared_ptr<.*>$', lambda val: StdPointerPrinter ('std::shared_ptr', val))
    pp.add_printer('std::weak_ptr', '^std::weak_ptr<.*>$', lambda val: StdPointerPrinter ('std::weak_ptr', val))
    pp.add_printer('std::unordered_map', '^std::unordered_map<.*>$', lambda val: Tr1UnorderedMapPrinter ('std::unordered_map', val))
    pp.add_printer('std::unordered_set', '^std::unordered_set<.*>$', lambda val: Tr1UnorderedSetPrinter ('std::unordered_set', val))
    pp.add_printer('std::unordered_multimap', '^std::unordered_multimap<.*>$', lambda val: Tr1UnorderedMapPrinter ('std::unordered_multimap', val))
    pp.add_printer('std::unordered_multiset', '^std::unordered_multiset<.*>$', lambda val: Tr1UnorderedSetPrinter ('std::unordered_multiset', val))

    pp.add_printer('std::tr1::shared_ptr', '^std::tr1::shared_ptr<.*>$', lambda val: StdPointerPrinter ('std::tr1::shared_ptr', val))
    pp.add_printer('std::tr1::weak_ptr', '^std::tr1::weak_ptr<.*>$', lambda val: StdPointerPrinter ('std::tr1::weak_ptr', val))
    pp.add_printer('std::tr1::unordered_map', '^std::tr1::unordered_map<.*>$', lambda val: Tr1UnorderedMapPrinter ('std::tr1::unordered_map', val))
    pp.add_printer('std::tr1::unordered_set', '^std::tr1::unordered_set<.*>$', lambda val: Tr1UnorderedSetPrinter ('std::tr1::unordered_set', val))
    pp.add_printer('std::tr1::unordered_multimap', '^std::tr1::unordered_multimap<.*>$', lambda val: Tr1UnorderedMapPrinter ('std::tr1::unordered_multimap', val))
    pp.add_printer('std::tr1::unordered_multiset', '^std::tr1::unordered_multiset<.*>$', lambda val: Tr1UnorderedSetPrinter ('std::tr1::unordered_multiset', val))

    # These are the C++0x printer registrations for -D_GLIBCXX_DEBUG cases.
    # The tr1 namespace printers do not seem to have any debug
    # equivalents, so do no register them.
    pp.add_printer('std::__debug::unordered_map', '^std::__debug::unordered_map<.*>$', lambda val: Tr1UnorderedMapPrinter ('std::__debug::unordered_map', val))
    pp.add_printer('std::__debug::unordered_set', '^std::__debug::unordered_set<.*>$', lambda val: Tr1UnorderedSetPrinter ('std::__debug::unordered_set', val))
    pp.add_printer('std::__debug::unordered_multimap', '^std::__debug::unordered_multimap<.*>$', lambda val: Tr1UnorderedMapPrinter ('std::__debug::unordered_multimap',  val))
    pp.add_printer('std::__debug::unordered_multiset', '^std::__debug::unordered_multiset<.*>$', lambda val: Tr1UnorderedSetPrinter ('std::__debug:unordered_multiset', val))

    # Extensions.
    pp.add_printer('__gnu_cxx::slist', '^__gnu_cxx::slist<.*>$', StdSlistPrinter)

    if True:
        # These shouldn't be necessary, if GDB "print *i" worked.
        # But it often doesn't, so here they are.
        pp.add_printer('std::_List_iterator', '^std::_List_iterator<.*>$', lambda val: StdListIteratorPrinter ("std::_List_iterator",val))
        pp.add_printer('std::_List_const_iterator', '^std::_List_const_iterator<.*>$', lambda val: StdListIteratorPrinter ("std::_List_const_iterator",val))
        pp.add_printer('std::_Rb_tree_iterator', '^std::_Rb_tree_iterator<.*>$', lambda val: StdRbtreeIteratorPrinter (val))
        pp.add_printer('std::_Rb_tree_const_iterator', '^std::_Rb_tree_const_iterator<.*>$', lambda val: StdRbtreeIteratorPrinter (val))
        pp.add_printer('std::_Deque_iterator', '^std::_Deque_iterator<.*>$', lambda val: StdDequeIteratorPrinter (val))
        pp.add_printer('std::_Deque_const_iterator', '^std::_Deque_const_iterator<.*>$', lambda val: StdDequeIteratorPrinter (val))
        pp.add_printer('__gnu_cxx::__normal_iterator', '^__gnu_cxx::__normal_iterator<.*>$', lambda val: StdVectorIteratorPrinter (val))
        pp.add_printer('__gnu_cxx::_Slist_iterator', '^__gnu_cxx::_Slist_iterator<.*>$', lambda val: StdSlistIteratorPrinter (val))

        # Debug (compiled with -D_GLIBCXX_DEBUG) printer registrations.
        # The Rb_tree debug iterator when unwrapped from the encapsulating __gnu_debug::_Safe_iterator
        # does not have the __norm namespace. Just use the existing printer registration for that.
        pp.add_printer('__gnu_debug::_Safe_iterator', '^__gnu_debug::_Safe_iterator<.*>$', lambda val: StdDebugIteratorPrinter (val))
        pp.add_printer('std::__norm::_List_iterator', '^std::__norm::_List_iterator<.*>$', lambda val: StdListIteratorPrinter ("std::__norm::_List_iterator",val))
        pp.add_printer('std::__norm::_List_const_iterator', '^std::__norm::_List_const_iterator<.*>$', lambda val: StdListIteratorPrinter ("std::__norm::_List_const_iterator",val))
        pp.add_printer('std::__norm::_Deque_const_iterator', '^std::__norm::_Deque_const_iterator<.*>$', lambda val: StdDequeIteratorPrinter (val))
        pp.add_printer('std::__norm::_Deque_iterator', '^std::__norm::_Deque_iterator<.*>$', lambda val: StdDequeIteratorPrinter (val))

    return pp
