from collections import defaultdict
import shapely
import numpy as np
from algos.alg_fpd_extended import FpdExtended
from intersection.plotting import plot_chunks_bounds, plot_geometry, plot_intersecting_points, create_canvas, plot_line
import matplotlib.pyplot as plt
import math

fpd = FpdExtended()


def is_bbox_intersecting(bbox_1, bbox_2):
    x_l_1, y_b_1, x_r_1, y_t_1 = bbox_1  # Left, bottom, right, top
    x_l_2, y_b_2, x_r_2, y_t_2 = bbox_2
    bbox = [max(x_l_1, x_l_2), max(y_b_1, y_b_2), min(x_r_1, x_r_2), min(y_t_1, y_t_2)]
    x_l, y_b, x_r, y_t = bbox
    return True if x_r >= x_l and y_t >= y_b else False


def common_bbox(bins):  # Returns lower left corner, upper right corner in 1D array
    x_l_1, y_b_1, x_r_1, y_t_1 = fpd.bounding_box(bins[0])[1]  # Left, bottom, right, top
    x_l_2, y_b_2, x_r_2, y_t_2 = fpd.bounding_box(bins[1])[1]
    bbox = [max(x_l_1, x_l_2), max(y_b_1, y_b_2), min(x_r_1, x_r_2), min(y_t_1, y_t_2)]
    x_l, y_b, x_r, y_t = bbox

    if x_r < x_l or y_t < y_b:
        type = 'None'
    elif x_l_1 == x_l_2 and y_b_1 == y_b_2 and x_r_1 == x_r_2 and y_t_1 == y_t_2:
        type = 'Equal'
    elif x_l_1 > x_l_2 and y_b_1 > y_b_2 and x_r_1 < x_r_2 and y_t_1 < y_t_2:
        type = '1 in 2'
    elif x_l_1 < x_l_2 and y_b_1 < y_b_2 and x_r_1 > x_r_2 and y_t_1 > y_t_2:
        type = '2 in 1'
    else:
        type = 'Partial'

    return (bbox, type) if type != 'None' else (None, type)


# --------- METHODS REQUIRING IMPLEMENTATIONS IN FPDE ---------------
# def slow_get_chunk(bin, idx, include_next=True):
#     chunks, is_last_chunk_ring = fpd.get_chunks(bin)
#     _, type = fpd.type(bin)
#     vertices = chunks[idx]
#     if not is_last_chunk_ring[idx] and type != 'LineString':
#         vertices += [chunks[idx + 1][0]]
#     return vertices

#chunks_bounds, _ = calculate_chunks_bounds(bin)
# --------- /END/ METHODS REQUIRING IMPLEMENTATIONS IN FPDE ---------------
def get_chunks_idxs_within_bounds(bin, bbox):
    chunks_bounds = fpd.get_chunk_bounds(bin)
    chunks_idxs = [i for i in range(len(chunks_bounds)) if is_bbox_intersecting(bbox, chunks_bounds[i])]
    return chunks_idxs

get_chunk = lambda bin, idx: fpd.get_chunk(bin, idx)[0] # Can also use slow above for debugging

def chunk_to_shape(chk): return shapely.Point(chk[0]) if len(chk) == 1 else shapely.LineString(chk)


def is_contained_within(containee, container, debug_correct_ans=None, plot_all=False):
    '''
    Containee is either FPDE binary object or a tuple of coordinates.
    '''
    if fpd.type(container)[1] == 'LineString':
        return False

    # Origin
    if type(containee) == bytes:
        x, y = fpd.access_vertex(containee, 0)[0]
    else:
        x, y = containee

    # Outher bounding box
    x_l, y_b, x_r, y_t = fpd.bounding_box(container)[1]
    distances = [(x_l - x, 0), (0, y_b - y), (x_r - x, 0), (0, y_t - y)]
    # Is point outside bounding box?
    if distances[0][0] > 0 or distances[1][1] > 0 or distances[2][0] < 0 or distances[3][1] < 0:
        return False

    ray_end = min(distances, key=lambda x: np.linalg.norm(x))
    ray_end = (x + ray_end[0], y + ray_end[1])
    ray = shapely.LineString([(x, y), ray_end])

    # Create list of segments for other shape, if the chunk collides with LineString
    chks = get_chunks_idxs_within_bounds(container, ray.bounds)
    segments = [chunk_to_shape(get_chunk(container, c)) for c in chks]
    intersecting_points = []
    for i in segments:
        if i.intersects(ray):
            intersecting_points += list(shapely.get_coordinates(i.intersection(ray)))
    # DEBUG
    # if plot_all or debug_correct_ans != None and debug_correct_ans != (len(intersecting_points) % 2 == 1):
    #     print(fpd.type(container)[1], fpd.type(containee)[1])
    #     plot_chunks_bounds(container, include_next_chunk_start=True, avoid_show=True)
    #     plot_chunks_bounds(containee, include_next_chunk_start=True, avoid_create_frame=True)
    #     plot_chunks_bounds(container, include_next_chunk_start=True, avoid_show=True, idxs=chks)
    #     for cs in segments:
    #         plot_geometry(cs)
    #     plot_geometry(ray, solid=False)
    #     plot_intersecting_points(intersecting_points)
    #     plot_chunks_bounds(containee, include_next_chunk_start=False, avoid_create_frame=True, idxs=[], txt=f" : was {len(intersecting_points) % 2 == 1} expected {debug_correct_ans}")
    # END DEBUG
    return len(intersecting_points) % 2 == 1

def is_point_on_segment(seg, pt):
    seg_pt_1, seg_pt_2, pt = (np.array(seg[0]), np.array(seg[1]), np.array(pt))
    return abs(np.linalg.norm(seg_pt_1 - pt) + np.linalg.norm(seg_pt_2 - pt) - np.linalg.norm(seg_pt_1 - seg_pt_2)) < 1e-15

# Based on the common bbox, extracts the chunks for both geometries within the bbox,
# and performs intersection testing between the line segments.
def line_intersection(bins, bbox, debug_correct_ans, res_list=None, plot_all=False):
    chk_idxs = [[], []]
    chks = [[], []]
    polylines = [[], []]
    for i in range(2):
        chk_idxs[i] = get_chunks_idxs_within_bounds(bins[i], bbox)
        chks[i] = [get_chunk(bins[i], c_i) for c_i in chk_idxs[i]]
        # Each chunk becomes a polyline
        polylines[i] = [chunk_to_shape(c) for c in chks[i]]

    intersecting_points = []

    for i in polylines[0]:
        for j in polylines[1]:
            if i.intersects(j):
                # DEBUG ------------------
                # if plot_all or debug_correct_ans != None and debug_correct_ans != True:
                #     for cs in polylines[0] + polylines[1]:
                #         plot_geometry(cs)
                #     plot_intersecting_points(list(shapely.get_coordinates(i.intersection(j))))
                #     plot_chunks_bounds(bins[0], include_next_chunk_start=True, avoid_show=True, idxs=chk_idxs[0])
                #     plot_chunks_bounds(bins[1], include_next_chunk_start=True, avoid_create_frame=True, idxs=chk_idxs[1], txt=f" : was True expected {debug_correct_ans}")
                # END ----------------------
                if res_list == None:
                    return True
                intersecting_points += list(shapely.get_coordinates(i.intersection(j)))

    if len(intersecting_points) == 0:
        return False

    ## Append to res_list
    res_list.append(intersecting_points)
    segments = [[], []]
    seg_to_cross = [defaultdict(list), defaultdict(list)]
    cross_to_seg = [[[], []] for _ in range(len(intersecting_points))]
    for s in range(2):
        segments[s] = [[c[i], c[i+1]] for c in chks[s] for i in range(len(c) - 1)]

        # Fix check restart
        for seg_idx, seg in enumerate(segments[s]):
            for p_idx, p in enumerate(intersecting_points):
                #plot_intersecting_points([p])
                if is_point_on_segment(seg, p):
                    #plot_geometry(shapely.LineString(seg))
                    seg_to_cross[s][seg_idx].append(p_idx)
                    cross_to_seg[p_idx][s].append(seg_idx)
                # else:
                #     plot_geometry(shapely.LineString(seg), solid=False)
            seg_to_cross[s][seg_idx].sort(key=lambda x: np.linalg.norm(segments[s][seg_idx][0] - intersecting_points[x])) # Sort ordered by distance from p[0]
    res_list.append(segments)
    res_list.append(seg_to_cross)
    res_list.append(cross_to_seg)


def is_intersecting(bins, debug_correct_ans=None, plot_all=False):
    bbox, overlap_type = common_bbox(bins)
    if bbox == None:
        return False

    # Bounding boxes intersect. Assume no intersection, ensure that no intersection is in fact occuring:
    # 1. Find all chunks which are inside the common bounding box
    #    Construct LineStrings and check for intersections
    if line_intersection(bins, bbox, debug_correct_ans, plot_all=plot_all):
        return True

    # 2. Ensure that the polygon is not fully contained
    #    Send ray and verify that it hits other polygon zero or even amount of times
    #    - Possibly pick point closest to other polygon's bounding box

    if overlap_type == '1 in 2':
        return is_contained_within(bins[0], bins[1], debug_correct_ans, plot_all)
    elif overlap_type == '2 in 1':
        return is_contained_within(bins[1], bins[0], debug_correct_ans, plot_all)
    return False

def intersection(bins, debug_correct_ans=None, plot_all=False):
    bbox, overlap_type = common_bbox(bins)
    if bbox == None:
        return shapely.Polygon(None)

    # Bounding boxes intersect. Assume no intersection, ensure that no intersection is in fact occuring:
    # 1. Find all chunks which are inside the common bounding box
    #    Construct LineStrings and check for intersections
    line_data = []
    line_intersection(bins, bbox, debug_correct_ans, line_data, plot_all)

    # 2. Ensure that the polygon is not fully contained
    #    Send ray and verify that it hits other polygon zero or even amount of times
    #    - Possibly pick point closest to other polygon's bounding box
    if len(line_data) == 0:
        if overlap_type == '1 in 2' and is_contained_within(bins[0], bins[1], debug_correct_ans, plot_all):
            return fpd.decompress(bins[0])[1]
        elif overlap_type == '2 in 1' and is_contained_within(bins[1], bins[0], debug_correct_ans, plot_all):
            return fpd.decompress(bins[1])[1]
        return shapely.Polygon(None)

    # Have intersecting points, construct resulting polygon
    # 1. Create set of intersection points, mapping: intersection point <-> line segments
    # 2. Take random intersection point from set, follow path inside both shapes
    # 3. Continue until encountering intersection point or already visited point

    def seg_to_point(s, seg_idx, v_idx):
        if v_idx > 1:
            return intersecting_points[seg_to_cross[s][seg_idx][v_idx - 2]]
        else:
            return segments[s][seg_idx][v_idx]

    def seg_to_middle_point(s, seg_idx, v_idxs):
        l = seg_to_point(s, seg_idx, v_idxs[0])
        r = seg_to_point(s, seg_idx, v_idxs[1])
        return [(l[0] + r[0]) / 2, (l[1] + r[1]) / 2]


    def DEBUG_print_paths(paths, c_i=None):
        if c_i != None:
            print(f"--: {intersecting_points[c_i]} :--")
        print("Raw:", paths)
        str = ""
        for p in paths:
            s, seg_idx, v_idxs, p_dir = p
            p_dir_sym = '+' if p_dir == 1 else '-'
            str += f'[{seg_to_point(s, seg_idx, v_idxs[0])} -> {seg_to_point(s, seg_idx, v_idxs[1])} ({p_dir_sym})], '
        print(str)


    # Returns the possible paths (directed segment) from an intersection point. Also checks that it is within both shapes.
    def possible_paths(c_i):
        possible_paths = []
        seg_idxs = cross_to_seg[c_i]
        for s in range(2):
            for seg_idx in seg_idxs[s]:
                seg_cross_cnt = len(seg_to_cross[s][seg_idx])
                # Get possible successor points
                # Where is the current cross?
                c_i_in_seg = seg_to_cross[s][seg_idx].index(c_i) + 2 # Index of vertex within segment

                # Get previous cross point if exists
                start_v = c_i_in_seg - 1 if c_i_in_seg != 2 else 0 # V:0 left of segment, V:1 right in segment, V:2+ intersection points
                if not np.array_equal(seg_to_point(s, seg_idx, start_v), seg_to_point(s, seg_idx, c_i_in_seg)): # Dont add line segments consisting of one point
                    possible_paths.append((s, seg_idx, (start_v, c_i_in_seg), -1)) # Vertex 2 being the first cross, 0 is first in traversal order

                # Has cross point after?
                end_v = c_i_in_seg + 1 if c_i_in_seg - 1 != seg_cross_cnt else 1
                if not np.array_equal(seg_to_point(s, seg_idx, c_i_in_seg), seg_to_point(s, seg_idx, end_v)):
                    possible_paths.append((s, seg_idx, (c_i_in_seg, end_v), 1)) # Vertex 2 being the first cross, 0 is first in traversal order

        #DEBUG_print_paths(possible_paths, c_i)
        possible_paths = list(filter(lambda p: is_contained_within(seg_to_middle_point(*p[0:3]), bins[(p[0] + 1) % 2]), possible_paths))
        # print("")
        # DEBUG_print_paths(possible_paths)
        # print("---")
        return possible_paths



    intersecting_points, segments, seg_to_cross, cross_to_seg = line_data
    #print("Intersecting Points:", intersecting_points)
    cross_left = set(range(len(intersecting_points)))
    processed_ways = [[set(), set()] for _ in range(len(intersecting_points))]
    res_segs = []
    while len(cross_left) > 0:
        c_i = cross_left.pop()
        paths = possible_paths(c_i)
        # if len(paths) == 0:
        #     print("FOUND POINT INTERSECTION")
        while len(paths) > 0:
            path = paths.pop()
            s, seg_idx, v_idxs, p_dir = path
            start_idx = 0 if p_dir == 1 else 1 # Start index
            end_idx = 1 if p_dir == 1 else 0

            if seg_idx in processed_ways[c_i][s]:
                continue

            # V_idxs contains: start_idx, end_index. I.e. the direction to traverse.
            while True: # While no cross point
                res_segs.append([seg_to_point(s, seg_idx, v_idxs[0]), seg_to_point(s, seg_idx, v_idxs[1])]) # Add segment to resulting shape
                e_v = v_idxs[end_idx] # Find index of actual end vertex (i.e. flip segment based on direction)

                next_seg_idx = seg_idx + p_dir
                if e_v > 1: # Is cross point?
                    encountered_c_idx = seg_to_cross[s][seg_idx][e_v - 2]
                    processed_ways[encountered_c_idx][s].add(seg_idx)
                    break
                elif next_seg_idx == -1 or seg_idx == len(segments[s]) or not np.array_equal(seg_to_point(s, seg_idx, e_v), seg_to_point(s, seg_idx, start_idx)):
                    break # Break if no more segments, or if path formed by segments is not continuous
                else:
                    seg_idx = next_seg_idx # Next segment
                    seg_cross_cnt = len(seg_to_cross[s][seg_idx])
                    if p_dir == 1:
                        v_idxs = [0, 2 if seg_cross_cnt != 0 else 1] # Has next line-segment crosspoint? If so take the first cross point as segment end-point.
                    else:
                        v_idxs = [2 if seg_cross_cnt != 0 else 0, 1]


    # create_canvas()
    # #plot_intersecting_points()
    # for p1, p2 in res_segs:
    #     plot_intersecting_points([p1, p2])
    #     plot_line(p1, p2)


    # plot_geometry(fpd.decompress(bins[0])[1], solid=False)
    # plot_geometry(fpd.decompress(bins[1])[1], solid=False)

    # plt.show()
    # print("RES", res_segs)
    return res_segs
