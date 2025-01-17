from bitarray import bitarray, util
import time
import shapely
import struct
import algos.fpd_extended_lib.intersection_chunk_bbox_wrapper 
from algos.fpd_extended_lib.low_level import *
import algos.fpd_extended_lib.cfg as cfg
from shapely import GeometryType as GT
from algos.fpd_extended_lib.entropy_coder import decompress_chunk, decode_entropy_param


# Structural things (per type):
def sequence_decoder(bin, seq_list, delta_size):
    LOAD_DT_BITSIZE = (cfg.COMPRESS_CHUNK or cfg.USE_ENTROPY) and not cfg.DISABLE_RANDOM_ACCESS
    chk_size = bytes_to_uint(bin, cfg.D_CNT_SIZE)

    if LOAD_DT_BITSIZE:
        delta_bytes_size = chk_size * delta_size * 2 - bytes_to_int(bin, cfg.D_BITSIZE_SIZE)

    # Extract reset point
    x = bytes_to_double(bin)
    y = bytes_to_double(bin)

    if cfg.COMPRESS_CHUNK:
        chk_deltas_offset = cfg.offset
        bin, coord_bit_len = decompress_chunk(bin, chk_deltas_offset, delta_bytes_size) 
   
    seq_list.append((x, y))
    # Loop through deltas in chunk
    for _ in range(chk_size):
        x = bytes_to_decoded_coord(bin, x, delta_size)
        y = bytes_to_decoded_coord(bin, y, delta_size)
        seq_list.append((x, y))
    if cfg.COMPRESS_CHUNK:
        cfg.offset = chk_deltas_offset + coord_bit_len
    return bin

def ring_decoder(bin, polygon_list, delta_size):
    # Extract number of chunks for a ring
    chks_in_ring = bytes_to_uint(bin, cfg.RING_CHK_CNT_SIZE)
    
    ring_coords = []
    # Loop through chunks in ring
    for i in range(chks_in_ring):
        bin = sequence_decoder(bin, ring_coords, delta_size)
    polygon_list.append(ring_coords)
    return bin

def polygon_decoder(bin, multipolygon_coords, delta_size):
    # Extract number of rings for a polygon
    rings_in_poly = bytes_to_uint(bin, cfg.POLY_RING_CNT_SIZE)
    polygon_coords = []
    # Loop through rings in polygon
    for _ in range(rings_in_poly):
        bin = ring_decoder(bin, polygon_coords, delta_size)
    multipolygon_coords.append(shapely.Polygon(shell=polygon_coords[0], holes=polygon_coords[1:]))
    return bin

def decode_header(bin):
    from algos.fpd_extended_lib.intersection_chunk_bbox_wrapper import intersection_skip_header
   
    if cfg.USE_ENTROPY:
        delta_size, type, entropy_param = struct.unpack_from('!BBB', bin)
        type = GT(type)
        decode_entropy_param(entropy_param, delta_size)
        cfg.offset += 3 * 8  # Offset is 3 bytes for BBB + FLOAT_SIZE * 4 for bounding box
    else:
        delta_size, type = struct.unpack_from('!BB', bin)
        cfg.offset += 2 * 8  # Offset is 3 bytes for BBB + FLOAT_SIZE * 4 for bounding box
    
    type = GT(type)
    if not cfg.DISABLE_OPTIMIZED_BOUNDING_BOX:
        cfg.offset += 4 * cfg.FLOAT_SIZE
    intersection_skip_header(bin) # Circular import
    return delta_size, type

def fp_delta_decoding(bin_in):
    cfg.offset = 0
    bin = bitarray(endian='big')
    bin.frombytes(bin_in)

    delta_size, type = decode_header(bin)
    cfg.binary_length = len(bin)
    coords = []
    if type == GT.LINESTRING:
        while (cfg.offset + cfg.EOF_THRESHOLD <= cfg.binary_length):  # While != EOF
            bin = sequence_decoder(bin, coords, delta_size)
        geometry = shapely.LineString(coords)

    elif type == GT.POLYGON:
        while (cfg.offset + cfg.EOF_THRESHOLD <= cfg.binary_length):  # While != EOF, i.e. at least one byte left
            bin = ring_decoder(bin, coords, delta_size)

        geometry = shapely.Polygon(shell=coords[0], holes=coords[1:])

    elif type == GT.MULTIPOLYGON:
        while (cfg.offset + cfg.EOF_THRESHOLD <= cfg.binary_length):  # While != EOF
            bin = polygon_decoder(bin, coords, delta_size)
        geometry = shapely.MultiPolygon(coords)
    return geometry

def decompress(self, bin):
    s = time.perf_counter()
    cfg_start_state = (cfg.ENTROPY_METHOD, cfg.ENTROPY_PARAM, cfg.USE_ENTROPY)
    geometry = fp_delta_decoding(bin)
    (cfg.ENTROPY_METHOD, cfg.ENTROPY_PARAM, cfg.USE_ENTROPY) = cfg_start_state
    t = time.perf_counter()
    return t - s, geometry