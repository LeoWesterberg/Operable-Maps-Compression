import json
import os
import shutil
from algos.base import CompressionAlgorithm
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
import shapely.wkt
import shapely
import linecache
import gzip
import time
import numpy as np
import bisect
import zlib


class WkbComp(CompressionAlgorithm):

    def compress(self, geometry):
        #Convert the geometry category names to numbers for smaller space (COMMENTED OUT FOR NOW) <- REF 1
        
        # type_comp = pd.factorize(file_df['geometry.type'])
        # self.num_to_type = dict({(idx, type_name) for idx, type_name in enumerate(type_comp[1])})
        # self.num_to_type.update({(type_name, idx) for idx, type_name in enumerate(type_comp[1])})

        #Create pre computed values to store as metadata
        s = time.perf_counter()
        
        #Write the compressed geometry
        content = gzip.compress(shapely.to_wkb(geometry))
        t = time.perf_counter()
        return t - s, content
    

    def decompress(self, bin):
        s = time.perf_counter()
        decomp_geom = gzip.decompress(bin) # Decompressing data
        geometry = shapely.wkb.loads(decomp_geom)
        t = time.perf_counter()
        return t - s, geometry     


# ---- UNARY ---- #

    def vertices(self, bin):
        s = time.perf_counter()
        _, geometry = self.decompress(bin)
        coords = shapely.get_coordinates(geometry)
        t = time.perf_counter()
        return t - s, coords

    def type(self, bin): 
        s = time.perf_counter()
        _, geometry = self.decompress(bin)
        type = geometry.geom_type
        t = time.perf_counter()
        return t - s, type
    
    def bounding_box(self, bin):
        s = time.perf_counter()
        _, geometry = self.decompress(bin)
        bounds = shapely.bounds(geometry)
        t = time.perf_counter()
        return t - s, bounds
    
    def add_vertex(self, args):
        bin, insert_idx, pos = args
        s = time.perf_counter()

        _, geometry = self.decompress(bin)
        ragged = shapely.to_ragged_array([geometry])
        points = ragged[1]
        is_linestring = shapely.get_type_id(geometry) == shapely.GeometryType.LINESTRING

        # Use binary search O(log n) to find the index of the first element greater than insert_idx
        end_idx = min(len(ragged[2][0]) - 1, bisect.bisect_right(ragged[2][0], insert_idx))

        # Is the first coordinate in the ring?
        if ragged[2][0][end_idx - 1] == insert_idx and not is_linestring:
                points = np.delete(points, ragged[2][0][end_idx] - 1, axis=0)
        else:
            for i in range(end_idx, len(ragged[2][0])):
                    ragged[2][0][i] += 1
                    
        points = np.insert(points, insert_idx, pos, axis=0)        
 
        geometry = shapely.from_ragged_array(geometry_type=shapely.get_type_id(geometry), coords=points, offsets=ragged[2])[0]
        _, bin = self.compress(geometry)

        t = time.perf_counter()
        return t - s, bin
    
    def is_intersecting(self, args):
        l_bin, r_bin = args
        s = time.perf_counter()
        _, l_geo = self.decompress(l_bin)
        _, r_geo = self.decompress(r_bin)
        res = shapely.intersects(l_geo, r_geo)
        t = time.perf_counter()
        return t - s, res

    def intersection(self, args):
        l_bin, r_bin = args
        s = time.perf_counter()
        _, l_geo = self.decompress(l_bin)
        _, r_geo = self.decompress(r_bin)
        res = shapely.intersection(l_geo, r_geo)
        t = time.perf_counter()
        return t - s, res


def main():
    x = SetAsideCompression()
    geom = shapely.wkt.loads("POLYGON ((13.1635138 55.7053599, 13.1637569 55.7053536, 13.1635571 55.705336, 13.1635158 55.7053284, 13.1635184 55.7053437, 13.1635138 55.7053599), (13.1667021 55.7046362, 13.1667117 55.7046498, 13.1667021 55.7046362))")
    t, bin = x.compress(geom)
    x.add_vertex((bin, [0,1], (24.5, 12.3)))
    print(geom)


if __name__ == "__main__":
    main()
