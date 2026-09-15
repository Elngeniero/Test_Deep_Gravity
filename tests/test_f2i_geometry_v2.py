"""Geometric conservation and preprocessing leakage regressions for F2-I."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import f2i_finalize as f
from shapely.geometry import box, LineString, Point, Polygon
import numpy as np
import osmium


class GeometryTests(unittest.TestCase):
    def test_overlapping_polygons_cover_once(self):
        area,removed=f.union_measure(box(0,0,10,10),[box(0,0,8,10),box(2,0,10,10)])
        self.assertAlmostEqual(area,100)
        self.assertAlmostEqual(removed,60)

    def test_polygon_holes_and_cross_boundary_are_preserved(self):
        polygon=Polygon([(0,0),(10,0),(10,10),(0,10)],holes=[[(4,4),(6,4),(6,6),(4,6)]])
        left,_=f.union_measure(box(0,0,5,10),[polygon])
        right,_=f.union_measure(box(5,0,10,10),[polygon])
        self.assertAlmostEqual(left+right,96)

    def test_duplicates_and_shared_line_boundary(self):
        left,right=box(0,0,5,10),box(5,0,10,10)
        line=LineString([(5,0),(5,10)])
        a,removed=f.union_measure(left,[line,line],'length')
        b,_=f.union_measure(right,[line],'length',left.boundary)
        self.assertAlmostEqual(a+b,10)
        self.assertAlmostEqual(removed,10)

    def test_point_boundary_does_not_get_arbitrary_owner(self):
        index=f.base.UnitIndex({'a':box(0,0,5,10),'b':box(5,0,10,10)})
        self.assertIsNone(f.assign_point(index,Point(5,4)))
        self.assertEqual(f.assign_point(index,Point(4,4)),'a')

    def test_other_is_closed_and_negative_tags_are_excluded(self):
        self.assertFalse(f.classify({'amenity':'invented_unknown'})[3])
        self.assertTrue(f.classify({'amenity':'police'})[3])
        self.assertIsNone(f.classify({'healthcare':'no','shop':'no'})[1])
        self.assertEqual(f.classify({'building':'school'})[1],'education')

    def test_rates_and_areas_are_not_added_and_population_present(self):
        raw={'unit_area_km2':2,'population_census_2024':200}
        for name in dict.fromkeys(f.PAPER19+f.MACRO20):
            if name.endswith('_share'): raw[name[:-6]+'_area_km2']=.5
            elif name.endswith('_poi_per_km2'): raw[name[:-12]+'_poi_count']=4
            elif name.endswith('_km_per_km2'): raw[name[:-8]]=6
        values=f.raw_to_features(raw)
        self.assertEqual(values[f.POP],100)
        self.assertEqual(values['transport_poi_per_km2'],2)
        self.assertEqual(values['transport_area_share'],.25)
        self.assertEqual(values['road_main_km_per_km2'],3)
        self.assertEqual(len(f.PAPER19),19)
        self.assertEqual(len(f.MACRO20),20)
        self.assertIn(f.POP,f.MACRO20)

    def test_train_only_fit_ignores_validation_outlier(self):
        columns=(f.POP,'landuse_residential_share')
        rows={'a':dict(zip(columns,[10,.2])),'b':dict(zip(columns,[30,.4])),
              'validation':dict(zip(columns,[1e9,1]))}
        scaled,params=f.fit_preprocessing(rows,columns,['a','b'])
        self.assertAlmostEqual(params['mean'][1],.3)
        self.assertAlmostEqual((scaled['a'][columns[0]]+scaled['b'][columns[0]])/2,0)
        rows['validation'][f.POP]=1e20
        _,repeat=f.fit_preprocessing(rows,columns,['a','b'])
        self.assertEqual(params,repeat)

    def test_native_filter_preserves_untagged_area_nodes(self):
        xml='''<osm version="0.6"><node id="1" lat="0" lon="0"/><node id="2" lat="0" lon="1"/><node id="3" lat="1" lon="1"/><node id="4" lat="1" lon="0"/><way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="building" v="school"/></way></osm>'''
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.osm'
            path.write_text(xml,encoding='utf-8')
            processor=osmium.FileProcessor(str(path)).with_locations().with_areas().with_filter(osmium.filter.KeyFilter('building'))
            areas=[obj.id for obj in processor if obj.is_area()]
        self.assertEqual(areas,[20])


if __name__=='__main__': unittest.main()
