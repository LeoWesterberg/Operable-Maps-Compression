# Run main locally
import sys
from pathlib import Path  # if you haven't already done so
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))

from algos.base import CompressionAlgorithm
from algos.fpd_extended_lib.intersection_chunk_bbox_wrapper import *
from algos.fpd_extended_lib.add_vertex import *
from algos.fpd_extended_lib.operations import *
from algos.fpd_extended_lib.helpers import *
from algos.fpd_extended_lib.compress import *
from algos.fpd_extended_lib.decompress import *

from collections import deque
import shapely
import shapely.wkt
from bitarray import bitarray, util, bits2bytes

#####                 #####
# --- FP-DELTA BASELINE ---#
#####                 #####

# char: 8 bits
# float: 32 bits
# double: 64 bits
# int: 32 bits
# long: 64 bits


class FpdExtended(CompressionAlgorithm):

    # ---- HELPER METHODS

    # Export some helper functions
    get_chunks = lambda self, bin, include_ring_start=True: get_chunks(bin, include_ring_start)
    access_vertex_chk = lambda self, bin, chk_offset, delta_size, idx, cache=None: access_vertex_chk(bin, chk_offset, delta_size, idx, cache)
    access_vertex = lambda self, bin, access_idx, cache=[]: access_vertex(bin, access_idx, cache)
    get_chunk = lambda self, bin, access_idx, cache=[]: access_chunk(bin, access_idx, cache)

    # Intersection
    get_chunk_bounds = lambda self, bin: get_chunk_bounds(bin)

# ---- UNARY ---- #
    compress = compress
    decompress = decompress

# ---- UNARY ---- #
    vertices = vertices
    type = type
    bounding_box = bounding_box
    add_vertex = add_vertex

# ---- BINARY ---- #
    is_intersecting = is_intersecting
    intersection = intersection


def main():
    import random
    import json
    import pandas as pd
    import tqdm
    from shapely.geometry import shape
    from alg_fpd import Fpd
    x = FpdExtended()
    # geom1 = shapely.wkt.loads('POLYGON ((-24.3 10.48, -19.32 12.44, -15.3 14.2, -15.3 13.78, -15.3 13.9, -15.06 10.4, -17.44 11.38, -19.18 11.46, -14.82 9.08, -12.9 10.14, -12.08 7.86, -14.36 5.94, -15.92 8.34, -16.86 3.48, -19.38 4.4, -18.2 6.52, -20.08 7.4, -24.34 6.68, -24.24 8.66, -27.52 11.1,  -27.0 11.1, -24.3 10.48))')
    geom_fail1 = shapely.wkt.loads('POLYGON ((20 0, -0.0915645 10.7002538, -0.0976896 10.6750084, 0 0, 10 10, 20 0))')
    geom_fail = shapely.wkt.loads('POLYGON ((17.4936737 59.4842568, 17.4936823 59.4844573, 17.4938883 59.4845793, 17.4941801 59.4845401, 17.4945578 59.4842917, 17.4946951 59.4842743, 17.4948496 59.4842873, 17.4949526 59.4842176, 17.4948753 59.4841086, 17.4949182 59.4839997, 17.4953474 59.4838036, 17.4958195 59.483359, 17.496077 59.4832718, 17.4962486 59.4831672, 17.4963087 59.4829232, 17.4966434 59.482605, 17.4967207 59.4823609, 17.4966692 59.4822345, 17.4964117 59.482143, 17.4961971 59.4821604, 17.4960426 59.4822215, 17.4960083 59.4824394, 17.495725 59.4825614, 17.4955706 59.4826835, 17.4953045 59.4827575, 17.4947466 59.4827445, 17.4940513 59.4830626, 17.4940256 59.4832065, 17.4942659 59.4832806, 17.4943861 59.4833547, 17.4940685 59.4835987, 17.4940943 59.4837905, 17.4940771 59.4839779, 17.4936737 59.4842568))')
    geom1 = shapely.wkt.loads('LINESTRING (-24.3 10.48, -19.32 12.44, -15.3 14.2)')
    geom2 = shapely.wkt.loads('POLYGON ((-9.9 16.85, -5.95 17.67, -6.19 13.49, -9.81 12.74, -7.35 9.2, -6.82 6.19, -10 6, -12.36 5.75, -14.59 8.1, -12 10, -13.93 12.31, -17.35 12.45, -16.83 15.6, -20.45 14.6, -22.36 12, -22 9.37, -27.1 6.48, -30 11.7, -27.9 15.5, -21.46 17.26, -19.6 16.1, -14.77 17.6, -11.43 13.32, -9.9 16.85))')

    geom3 = shapely.wkt.loads("MULTIPOLYGON (((13.193709 55.7021381, 13.1937743 55.7021279, 13.1938355 55.7021184, 13.1938461 55.702109, 13.1938566 55.7020984, 13.1938611 55.7020902, 13.1938655 55.7020774, 13.1938655 55.7020633, 13.1938583 55.7020408, 13.1938402 55.7020014, 13.1937184 55.7017259, 13.1937008 55.7016876, 13.1936836 55.7016654, 13.1936537 55.7016428, 13.1936223 55.7016242, 13.1935741 55.7016036, 13.1935354 55.7015911, 13.1935006 55.701584, 13.1934829 55.701598, 13.1934673 55.7016115, 13.1934736 55.7016164, 13.1934776 55.7016216, 13.1934875 55.7016633, 13.1934985 55.7016898, 13.1935196 55.7017337, 13.1935659 55.7018353, 13.1936162 55.7018282, 13.1936551 55.7019155, 13.1936651 55.7019377, 13.1936955 55.7020047, 13.1936497 55.7020119, 13.193709 55.7021381)), ((13.1938175 55.7017126, 13.1938602 55.7017068, 13.1939048 55.7017007, 13.1938998 55.7016861, 13.193892 55.7016685, 13.1938831 55.7016589, 13.193871 55.701651, 13.1938602 55.701646, 13.1938405 55.7016438, 13.193822 55.7016456, 13.1938062 55.7016517, 13.1937985 55.7016571, 13.1937953 55.7016646, 13.1937979 55.7016746, 13.1938017 55.7016836, 13.1938052 55.7016908, 13.1938175 55.7017126)), ((13.1940245 55.7019788, 13.19398 55.7019848, 13.1939372 55.7019907, 13.1939585 55.7020383, 13.1939692 55.7020479, 13.1939841 55.7020512, 13.1939975 55.7020519, 13.1940079 55.702051, 13.1940198 55.7020497, 13.1940317 55.7020463, 13.1940395 55.7020422, 13.1940435 55.7020369, 13.1940452 55.7020314, 13.1940457 55.7020218, 13.1940245 55.7019788)), ((13.1939779 55.7015541, 13.1939529 55.701555, 13.1939622 55.7015658, 13.1939755 55.7015942, 13.194075 55.7018201, 13.1941382 55.7019637, 13.1941483 55.7019866, 13.194164 55.7020087, 13.1941899 55.7020304, 13.1942142 55.7020424, 13.1942291 55.7020486, 13.1942638 55.702042, 13.195019 55.7018988, 13.1948681 55.7018923, 13.1944181 55.7018687, 13.1944172 55.7018717, 13.194395 55.7018706, 13.1942164 55.7018622, 13.194172 55.7017564, 13.1941218 55.701761, 13.1941279 55.7017262, 13.1941357 55.7016818, 13.1940872 55.7015737, 13.1940769 55.7015503, 13.1939779 55.7015541), (13.1942341 55.7020059, 13.1942075 55.7020095, 13.1941895 55.7019673, 13.1941696 55.701921, 13.1941936 55.7019177, 13.1941884 55.7019055, 13.19426 55.7018958, 13.1942645 55.7019063, 13.1943172 55.7018991, 13.1943567 55.7019912, 13.1943041 55.7019984, 13.1943086 55.7020089, 13.1942394 55.7020183, 13.1942341 55.7020059)))")

    geom4 = shapely.wkt.loads(
        "LINESTRING (13.199378 55.7034667, 13.1999441 55.7033986, 13.200125 55.7033882, 13.2002723 55.7033936, 13.2004383 55.7034097, 13.2005935 55.7034211, 13.2007699 55.703423, 13.2011275 55.7034136, 13.2012413 55.7034103, 13.2012947 55.7034088)")

    geom5 = shapely.wkt.loads('POLYGON ((13.1848537 55.7057363, 13.1848861 55.705646, 13.1848603 55.7056619, 13.1846238 55.7056422, 13.1846085 55.7057159, 13.1846356 55.7057179, 13.1848537 55.7057363), (13.1846694 55.705714, 13.1846543 55.7057128, 13.1846563 55.705705, 13.1846714 55.7057062, 13.1846694 55.705714), (13.1847425 55.7057123, 13.1847405 55.7057201, 13.1847254 55.7057188, 13.1847274 55.705711, 13.1847425 55.7057123), (13.1848001 55.7057179, 13.1848152 55.7057192, 13.1848131 55.705727, 13.1847981 55.7057258, 13.1848001 55.7057179), (13.1848068 55.7056929, 13.1848088 55.7056851, 13.1848239 55.7056863, 13.1848218 55.7056941, 13.1848068 55.7056929), (13.1847507 55.7056878, 13.1847356 55.7056865, 13.1847377 55.7056787, 13.1847528 55.70568, 13.1847507 55.7056878), (13.1846811 55.7056732, 13.184679 55.705681, 13.184664 55.7056798, 13.184666 55.705672, 13.1846811 55.7056732))')

    geom6 = shapely.wkt.loads(
        'POLYGON ((13.1848537 55.7057363, 13.1848861 55.705646, 13.184812 55.705646, 13.1848537 55.7057363))')
    geom7 = shapely.wkt.loads('MULTIPOLYGON (((13.1848537 55.7057363, 13.1848861 55.705646, 13.1848861 55.705646, 13.1848537 55.7057363), (13.1847425 55.7057123, 13.1847274 55.705711, 13.1847300 55.705712, 13.1847425 55.7057123)), ((13.1848537 55.7057363, 13.1848861 55.705646, 13.1848841 55.705626, 13.1848537 55.7057363), (13.1847425 55.7057123, 13.1847274 55.705711, 13.1848861 55.705646, 13.1847425 55.7057123)))')
    geom8 = shapely.wkt.loads('POLYGON ((13.1776776 55.7099071, 13.1768495 55.7101072, 13.1769163 55.7101952, 13.1770482 55.7101633, 13.1772273 55.71012, 13.177429 55.7100713, 13.1776196 55.7100252, 13.1777443 55.7099951, 13.1776776 55.7099071))')
    from algos.fpd_extended_lib.entropy_coder import encode, decode
    #bin = b'\x0c\x03\x00s$r\xaf\x8c~z?s$\x95\xa3\x8c~\x85\x80\x00\x00\x00\x02s$r\xaf\x8c~z?s$\x93\x08\x8c~\x82\x10s$r\xaf\x8c~z?s$\x95\xa3\x8c~\x85\x80\x00\x00\x00\x08\x00\x00\x072I0\x88\xc7\xe7\xa3\xf1\x80$\x1c\xc9\x1c\xab\xe3\x1f\xa0\x84\x14\xe1\xb8)8\x9fw\xf8\xd8\x7f\x08\xf3{\x90\xe6f\xf8\x96@'
    bin = x.compress(geom8)[1]
    #print(x.get_chunk(bin, 0))
    #bin = open('data/testbench_compressed_single/1164', 'rb').read()
    #print(bin)
    geom = x.decompress(bin)[1]
    # print(geom)
    # print(geom_fail)
    #print(x.get_chunks(bin))
    print(geom_fail == geom)
    
    return
    import bench_utils
    K = 10
    diff_sum = 0
    df, unary_idxs = bench_utils.read_dataset("data/world.json")
    for idx in unary_idxs: # List of single idxs
        t, bin = x.compress(shape(df.iloc[idx + 1]))
        t, geomx = x.decompress(bin)
        break

if __name__ == "__main__":
    main()
