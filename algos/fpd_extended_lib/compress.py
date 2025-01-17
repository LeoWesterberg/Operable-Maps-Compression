from collections import deque
import shapely
import math
from bitarray import bitarray, util, bits2bytes
import time
from shapely import GeometryType as GT
from algos.fpd_extended_lib.intersection_chunk_bbox_wrapper import *
from algos.fpd_extended_lib.low_level import *
from algos.fpd_extended_lib.entropy_coder import encode, get_entropy_metadata, compress_chunk

def get_zz_encoded_delta(prev_coord, curr_coord):
    return zz_encode(double_as_long(curr_coord) - double_as_long(prev_coord))

def deltas_fit_in_bits(d_x, d_y, max_bits):
    return (d_x == 0 or math.log2(d_x) < max_bits) and (d_y == 0 or math.log2(d_y) < max_bits)

# Returns the number of coords in each ring for a polygon. If multipolygon, index on polygon first
def point_count(geometry):
    coords = shapely.get_coordinates(geometry)

    if shapely.get_type_id(geometry) == GT.LINESTRING:
        return [0, len(coords)]

    ring_count = deque([])
    if shapely.get_type_id(geometry) == GT.POLYGON:
        ring_count.append(len(geometry.exterior.coords))
        for i in range(len(geometry.interiors)):
            ring_count.append(len(geometry.interiors[i].coords))

    elif shapely.get_type_id(geometry) == GT.MULTIPOLYGON:
        for polygon in list(geometry.geoms):
            poly_ring_count = deque()
            poly_ring_count.append(len(list(polygon.exterior.coords)))
            for i in range(len(polygon.interiors)):
                poly_ring_count.append(len(polygon.interiors[i].coords))
            ring_count.append(poly_ring_count)
    return ring_count

def append_header(bits, geometry, d_size, deltas):
    global_use_entropy = cfg.USE_ENTROPY
    (cfg.ENTROPY_METHOD, cfg.USE_ENTROPY, cfg.ENTROPY_PARAM) = get_entropy_metadata(deltas, d_size)
    # Meta data
    bits.frombytes(uchar_to_bytes(d_size))
    bits.frombytes(uchar_to_bytes(int(shapely.get_type_id(geometry))))  # 1 byte is enough for storing type
    if global_use_entropy:
        bits.frombytes(uchar_to_bytes(cfg.ENTROPY_PARAM))
    # Bounding Box
    if not cfg.DISABLE_OPTIMIZED_BOUNDING_BOX:
        bounds = shapely.bounds(geometry)
        bits.frombytes(double_to_bytes(bounds[0]))
        bits.frombytes(double_to_bytes(bounds[1]))
        bits.frombytes(double_to_bytes(bounds[2]))
        bits.frombytes(double_to_bytes(bounds[3]))
    intersection_reserve_header(bits)

def append_delta_pair(bits, d_x_zig, d_y_zig, d_size):
        x_bytes = uint_to_ba(d_x_zig, d_size)
        y_bytes = uint_to_ba(d_y_zig, d_size)
        if cfg.USE_ENTROPY:
            x_bytes, len_x = encode(x_bytes, d_size)
            y_bytes, len_y = encode(y_bytes, d_size)
        bits.extend(x_bytes)
        bits.extend(y_bytes)
        return (d_size, d_size) if not cfg.USE_ENTROPY else (len_x, len_y)

def fp_delta_encoding(geometry, d_size, deltas):
    # List of resulting bytes.
    bits = bitarray(endian='big')
    # Init with 'd_size', 'geom_type'
    append_header(bits, geometry, d_size, deltas)
    STORE_DT_BITSIZE = (cfg.COMPRESS_CHUNK or cfg.USE_ENTROPY) and not cfg.DISABLE_RANDOM_ACCESS

    # Type specific variables
    geo_type = shapely.get_type_id(geometry)
    is_linestring = geo_type == GT.LINESTRING
    is_multipolygon = geo_type == GT.MULTIPOLYGON
    is_polygon = geo_type == GT.POLYGON

    # Fetches number of points in each ring, nestled for multipoly
    poly_buffer = point_count(geometry)
    ring_buffer = poly_buffer if is_polygon else []  # Not nestled for poly, else overwritten below

    prev_x, prev_y = 0, 0  # Absolute value of previous coord
    chk_dt_cnt = 0  # Cnt of 'deltas in chunk'
    chk_dt_bitsize = 0  # Size of 'deltas in chunk'
    chk_hdr_offset = 0  # Pointer to 'deltas of chunk'
    num_chks_ring = 0  # Cnt of 'number of chunks for current ring'
    num_chks_ring_idx = 0  # Pointer to latest 'number of chunks for ring'
    rem_points_ring = 0  # Cnt of 'points left to process in current ring'

    # Loop all coordinates
    for x, y in shapely.get_coordinates(geometry):
        if not is_linestring and rem_points_ring == 1:  # Is the whole ring processed? We skip last coordinate
            # Store number of chunks used for the ring
            rem_points_ring = 0
            bits[num_chks_ring_idx:num_chks_ring_idx + cfg.RING_CHK_CNT_SIZE] = uint_to_ba(num_chks_ring, cfg.RING_CHK_CNT_SIZE)
            num_chks_ring = 0
            intersection_add_point(*intersection_first_coord_ring)
            continue  # Skip last coordinate
        d_x_zig = get_zz_encoded_delta(prev_x, x)  # Calculated delta based on previous iteration
        d_y_zig = get_zz_encoded_delta(prev_y, y)
        prev_x, prev_y = (x, y)

        # ---- CREATE NEW CHUNK? If 'first chunk', 'delta doesn't fit', 'new ring', or 'reached max deltas'
        if chk_hdr_offset == 0 or not deltas_fit_in_bits(d_x_zig, d_y_zig, d_size) or rem_points_ring == 0 or chk_dt_cnt == cfg.MAX_NUM_DELTAS:
            # If not 'first chunk' -> save previous chunk's size
            if chk_hdr_offset != 0:
                bits[chk_hdr_offset:chk_hdr_offset + cfg.D_CNT_SIZE] = uint_to_ba(chk_dt_cnt, cfg.D_CNT_SIZE)
                if cfg.COMPRESS_CHUNK: # Compress previous chunk
                    bits, chk_dt_bitsize = compress_chunk(bits, chk_hdr_offset, chk_dt_bitsize)
                if STORE_DT_BITSIZE:
                    bits[chk_hdr_offset + cfg.D_CNT_SIZE:chk_hdr_offset + cfg.D_CNT_SIZE + cfg.D_BITSIZE_SIZE] = int_to_ba(chk_dt_cnt * d_size * 2 - chk_dt_bitsize, cfg.D_BITSIZE_SIZE)

            ###### ---- INITIALIZE NEW CHUNK ----- ######
            chk_dt_cnt, chk_dt_bitsize = 0, 0
            intersection_new_chunk()
            intersection_add_point(x, y)

            ### __ RING/MULTI-POLYGON META-DATA __ ###
            if not is_linestring:
                # Ran out of points -> fetch number of points in next ring
                if rem_points_ring == 0:
                    # Check if we ran out of rings -> fetch rings of NEXT POLYGON
                    if is_multipolygon and len(ring_buffer) == 0:
                        ring_buffer = poly_buffer.popleft()
                        bits.extend(uint_to_ba(len(ring_buffer), cfg.POLY_RING_CNT_SIZE))  # Append 'nbr of rings in poly'
                    # Set 'remaining points' to cnt in new ring
                    rem_points_ring = ring_buffer.popleft()
                    num_chks_ring_idx = len(bits)
                    bits.extend(uint_to_ba(0, cfg.RING_CHK_CNT_SIZE))  # Reserve space for number of chunks for current ring
                    num_chks_ring = 1
                    intersection_first_coord_ring = (x, y)
                else:
                    num_chks_ring += 1
                    intersection_add_point(x, y, previous_chunk=True)
                    
             #add next chunks first point to bounding box
            if is_linestring and get_chunk_bboxes_len() > 1:
                intersection_add_point(x, y, previous_chunk=True)

            ### __ ------------ END ------------- __ ###

            # Preparing chunk size (number of deltas)
            chk_hdr_offset = len(bits)
            bits.extend(uint_to_ba(0, cfg.D_CNT_SIZE)) # Reserve space for 'chk_dt_cnt'
            if STORE_DT_BITSIZE:
                # Size of chunk is needed when variable-length compression is used
                bits.extend(uint_to_ba(0, cfg.D_BITSIZE_SIZE)) # Reserve space for bit size of deltas

            # Add full coordinates
            bits.frombytes(double_to_bytes(x))
            bits.frombytes(double_to_bytes(y))
        else:
            # Delta fits, append it
            (len_x, len_y) = append_delta_pair(bits, d_x_zig, d_y_zig, d_size)
            chk_dt_cnt += 1
            chk_dt_bitsize += len_x + len_y
            intersection_add_point(x, y)

        # Coord has been processed, remove it
        rem_points_ring -= 1

    # All points processed. Update size of final chunk
    if cfg.COMPRESS_CHUNK:
        bits, chk_dt_bitsize = compress_chunk(bits, chk_hdr_offset, chk_dt_bitsize)

    bits[chk_hdr_offset:chk_hdr_offset + cfg.D_CNT_SIZE] = uint_to_ba(chk_dt_cnt, cfg.D_CNT_SIZE)
    if STORE_DT_BITSIZE:
        # Store the gain from compression/entropy coding
        bits[chk_hdr_offset + cfg.D_CNT_SIZE:chk_hdr_offset + cfg.D_CNT_SIZE + cfg.D_BITSIZE_SIZE] = int_to_ba(chk_dt_cnt * d_size * 2 - chk_dt_bitsize, cfg.D_BITSIZE_SIZE)
   
    bits = intersection_append_header(bits)
    
    # util.pprint(bits)
    #print([int.from_bytes(i, 'big') for i in bits.tobytes()], '\n')
    return bits.tobytes()

def calculate_delta_size(geometry=None, coords=None, return_deltas=False):
    deltas = [[], []]
    RESET_POINT_SIZE = cfg.FLOAT_SIZE * 2 + cfg.D_CNT_SIZE
    if geometry != None:
        coords = shapely.get_coordinates(geometry)
    prev = coords[0]
    bit_cnts = {}
    for coord in coords[1:]:
        bit_cnt = 0
        for i in range(2):
            d = get_zz_encoded_delta(prev[i], coord[i])
            d_bit_cnt = 1 if d == 0 else math.ceil(math.log2(d))
            bit_cnt = max(bit_cnt, d_bit_cnt)
            if return_deltas:
                deltas[0].append(coord[i] - prev[i])
                deltas[1].append(d)

        if bit_cnt not in bit_cnts:
            bit_cnts[bit_cnt] = 1
        else:
            bit_cnts[bit_cnt] += 1
        prev = coord
    bit_cnts = dict(sorted(bit_cnts.items(), reverse=True))
    #bit_lens = range(32, -1, -1)

    tot_size = {}
    upper_cnt = 0
    lower_cnt = len(coords)  - 1
    #for n in bit_lens:
    for n in bit_cnts.keys():
        tot_size[n] = n * lower_cnt * 2 + RESET_POINT_SIZE * upper_cnt
        #if n in bit_cnts:
        lower_cnt -= bit_cnts[n]
        upper_cnt += bit_cnts[n]
    optimal_delta_size = min(tot_size, key=tot_size.get)
    return optimal_delta_size, [bit_cnts, tot_size], deltas

def compress(self, geometry):
    s = time.perf_counter()
    cfg.ENTROPY_STATE = (cfg.ENTROPY_METHOD, cfg.ENTROPY_PARAM, cfg.USE_ENTROPY)
    optimal_size, _, deltas = calculate_delta_size(geometry, return_deltas=True)
    bin = fp_delta_encoding(geometry, optimal_size, deltas[1])
    (cfg.ENTROPY_METHOD, cfg.ENTROPY_PARAM, cfg.USE_ENTROPY) = cfg.ENTROPY_STATE
    t = time.perf_counter()
    return t - s, bin
