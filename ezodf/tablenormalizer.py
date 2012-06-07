#!/usr/bin/env python
#coding:utf-8
# Purpose: table nomalizer
# Created: 14.02.2011
# Copyright (C) 2011, Manfred Moitzi
# License: GPLv3
from __future__ import unicode_literals, print_function, division
__author__ = "mozman <mozman@gmx.at>"

import copy

from .tableutils import new_empty_cell, get_table_rows, is_table
from .tableutils import get_min_max_cell_count, count_cells_in_row
from .tableutils import RepetitionAttribute

class TableNormalizer(object):
    def __init__(self, xmlnode):
        if not is_table(xmlnode):
            raise ValueError('invalid xmlnode')
        self.xmlnode = xmlnode

    def expand_repeated_table_content(self):
        def expand_element(xmlnode, count):
            while count > 1:
                clone = copy.deepcopy(xmlnode)
                xmlnode.addnext(clone)
                count -= 1

        def expand_cell(xmlcell):
            repeat = RepetitionAttribute(xmlcell)
            count = repeat.cols
            if count > 1:
                del repeat.cols
                expand_element(xmlcell, count)
                
        def do_not_expand_cell(xmlcell):
            repeat = RepetitionAttribute(xmlcell)
            if repeat.cols > 1:
                del repeat.cols

        def expand_cells(xmlrow):
            # do not expand last column
            for xmlcell in xmlrow[:-1]:
                expand_cell(xmlcell)
            do_not_expand_cell(xmlrow[-1])

        def expand_row(xmlrow):
            count = RepetitionAttribute(xmlrow).rows
            del RepetitionAttribute(xmlrow).rows
            expand_element(xmlrow, count)
            
        def do_not_expand_row(xmlrow):
            repeat = RepetitionAttribute(xmlrow)
            if repeat.rows > 1:
                del repeat.rows
            
        rows = get_table_rows(self.xmlnode)
        for xmlrow in rows[:-1]: # do not expand last row
            expand_cells(xmlrow)
            if RepetitionAttribute(xmlrow).rows > 1:
                expand_row(xmlrow)  
        do_not_expand_row(rows[-1])

    def align_table_columns(self):
        def append_cells(xmlrow, count):
            for _ in range(count):
                xmlrow.append(new_empty_cell())

        def _align_table_columns(required_cells_per_row):
            for xmlrow in get_table_rows(self.xmlnode):
                count = count_cells_in_row(xmlrow)
                if count < required_cells_per_row:
                    append_cells(xmlrow, required_cells_per_row - count)

        cmin, cmax = get_min_max_cell_count(self.xmlnode)
        if cmin != cmax:
            _align_table_columns(cmax)

def normalize_table(xmlnode):
    normalizer = TableNormalizer(xmlnode)
    normalizer.expand_repeated_table_content()
    normalizer.align_table_columns()