from collections import deque
import time
import struct
import math
import numpy as np
from shapely import GeometryType as GT
import bisect
from bitarray import bitarray, util, bits2bytes


# Only used for non-timed operations
def get_chunks(self, bin_in):
    chunks = []
    self.offset = 0
    bin = bitarray(endian='big')
    bin.frombytes(bin_in)

    delta_size, type = self.decode_header(bin)
    # Type specific variables
    is_linestring = type == GT.LINESTRING
    is_multipolygon = type == GT.MULTIPOLYGON

    chunks_in_ring_left = 0  # Used for iteration
    chunks_in_ring = 0
    rings_left = 0

    is_last_ring_chunk = []
    bin_len = len(bin)
    while (self.offset + self.EOF_THRESHOLD <= bin_len):
        if is_multipolygon and rings_left == 0:
            rings_left = self.bytes_to_uint(bin, self.POLY_RING_CNT_SIZE)
        if not is_linestring and chunks_in_ring_left == 0:
            chunks_in_ring_left = self.bytes_to_uint(bin, self.RING_CHK_CNT_SIZE)
            chunks_in_ring = chunks_in_ring_left

        # Go through chunk (inlined sequence decode)
        deltas_in_chunk = self.bytes_to_uint(bin, self.D_CNT_SIZE)
        # Extract reset point
        x = self.bytes_to_double(bin)
        y = self.bytes_to_double(bin)
        # if chunks_in_ring_left == chunks_in_ring:
        # x_ring, y_ring = (x, y)

        chunk = [[x, y]]
        # Loop through deltas in chunk
        for _ in range(deltas_in_chunk):
            x = self.bytes_to_decoded_coord(bin, x, delta_size)
            y = self.bytes_to_decoded_coord(bin, y, delta_size)
            chunk.append([x, y])
        chunks.append(chunk)
        is_last_ring_chunk.append(False)
        chunks_in_ring_left -= 1
        if chunks_in_ring_left == 0:
            # chunks.append([x_ring, y_ring])
            rings_left -= 1
            is_last_ring_chunk[-1] = True
    return chunks, is_last_ring_chunk


def access_vertex(self, bin_in, access_idx, cache=[], getBoundsData=False):
    if not getBoundsData and access_idx in cache:
        return cache[access_idx], cache, None
    old_offset = self.offset
    self.offset = 0
    bin = bitarray(endian='big')
    bin.frombytes(bin_in)

    if 'header' in cache:
        delta_size, type = cache['header']
        self.offset = cache['offset']
    else:
        delta_size, type = self.decode_header(bin)
    # Type specific variables
    is_linestring = type == GT.LINESTRING
    is_multipolygon = type == GT.MULTIPOLYGON
    is_polygon = type == GT.POLYGON

    idx_found = False
    ring_beg_idx, ring_end_idx, poly_beg_idx, poly_end_idx = None, None, None, None

    p_idx = 0
    chunks_in_ring_left = 0  # Used for iteration
    rings_left = 0
    while (p_idx <= access_idx or getBoundsData):
        if is_multipolygon and rings_left == 0:
            rings_left = self.bytes_to_uint(bin, self.POLY_RING_CNT_SIZE)
            if getBoundsData:
                if not idx_found:
                    poly_beg_idx = p_idx

        if not is_linestring and chunks_in_ring_left == 0:
            chunks_in_ring_left = self.bytes_to_uint(bin, self.RING_CHK_CNT_SIZE)
            if not idx_found:
                ring_beg_idx = p_idx

        deltas_in_chunk_offset = self.offset
        deltas_in_chunk = self.bytes_to_uint(bin, self.D_CNT_SIZE)

        # Found chunk containing vertex?
        if not idx_found and (p_idx <= access_idx and access_idx <= p_idx + deltas_in_chunk):
            idx_found = True
            (x, y), cache = self.access_vertex_chk(bin, deltas_in_chunk_offset, access_idx - p_idx, delta_size, cache, offset_idx=p_idx)
            if not getBoundsData:
                break

        # Jump to next chunk
        p_idx += 1 + deltas_in_chunk
        self.offset += self.FLOAT_SIZE * 2 + delta_size * 2 * deltas_in_chunk
        chunks_in_ring_left -= 1
        if (chunks_in_ring_left == 0):
            if idx_found:
                ring_end_idx = p_idx - 1
            rings_left -= 1
        if (rings_left == 0):
            if idx_found and is_multipolygon:
                poly_end_idx = p_idx - 1

        if getBoundsData and ((is_multipolygon and poly_end_idx != None) or (is_polygon and ring_end_idx != None) or is_linestring):
            break
    self.offset = old_offset
    return (x, y), cache, None if not getBoundsData else (ring_beg_idx, ring_end_idx, poly_beg_idx, poly_end_idx)

    # Supply the offset to D_CNT, and idx is the index within the chunk
    # @profile


def access_vertex_chk(self, bin, chk_offset, idx, delta_size, cache=None, offset_idx=0):
    if cache != None and idx + offset_idx in cache:
        return cache[idx + offset_idx], cache
    old_offset = self.offset
    self.offset = chk_offset + self.D_CNT_SIZE
    # Extract reset point
    x, y = (self.bytes_to_double(bin), self.bytes_to_double(bin))
    # Loop through deltas in chunk
    for idx in range(idx):
        if cache != None and idx + offset_idx in cache:
            self.offset += delta_size * 2
            (x, y) = cache[idx + offset_idx]
        else:
            x = self.bytes_to_decoded_coord(bin, x, delta_size)
            y = self.bytes_to_decoded_coord(bin, y, delta_size)
            if cache != None:
                cache[idx + offset_idx] = (x, y)
    self.offset = old_offset
    return (x, y), cache


def type(self, bin):
    s = time.perf_counter()
    type = struct.unpack_from('!B', bin, offset=1)[0]  # 1 Byte offset
    if type == GT.LINESTRING:
        type = 'LineString'
    elif type == GT.POLYGON:
        type = 'Polygon'
    elif type == GT.MULTIPOLYGON:
        type = 'MultiPolygon'
    t = time.perf_counter()
    return t - s, type


def bounding_box(self, bin):
    s = time.perf_counter()

    bounds = []
    res = bitarray()
    res.frombytes(bin)
    bounds = list(struct.unpack_from('!dddd', bin, offset=2))  # Skip first part of header
    t = time.perf_counter()
    return t - s, bounds


def vertices(self, bin_in):
    s = time.perf_counter()

    coords = []
    self.offset = 0
    bin = bitarray(endian='big')
    bin.frombytes(bin_in)

    delta_size, type = self.decode_header(bin)
    # Type specific variables
    is_linestring = type == GT.LINESTRING
    is_multipolygon = type == GT.MULTIPOLYGON

    chunks_in_ring_left = 0  # Used for iteration
    chunks_in_ring = 0
    rings_left = 0
    bin_len = len(bin)
    while (self.offset + self.EOF_THRESHOLD <= bin_len):
        if is_multipolygon and rings_left == 0:
            rings_left = self.bytes_to_uint(bin, self.POLY_RING_CNT_SIZE)
        if not is_linestring and chunks_in_ring_left == 0:
            chunks_in_ring_left = self.bytes_to_uint(bin, self.RING_CHK_CNT_SIZE)
            chunks_in_ring = chunks_in_ring_left

        # Go through chunk (inlined sequence decode)
        deltas_in_chunk = self.bytes_to_uint(bin, self.D_CNT_SIZE)
        # Extract reset point
        x = self.bytes_to_double(bin)
        y = self.bytes_to_double(bin)
        if chunks_in_ring_left == chunks_in_ring:
            x_ring, y_ring = (x, y)
        coords.append([x, y])
        # Loop through deltas in chunk
        for _ in range(deltas_in_chunk):
            x = self.bytes_to_decoded_coord(bin, x, delta_size)
            y = self.bytes_to_decoded_coord(bin, y, delta_size)
            coords.append([x, y])
        chunks_in_ring_left -= 1
        if chunks_in_ring_left == 0:
            coords.append([x_ring, y_ring])
            rings_left -= 1

    coords = np.array(coords)

    t = time.perf_counter()
    return t - s, coords
