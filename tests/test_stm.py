import xarray as xr
import dask.array as da
import numpy as np
from stmtools import stm
import pytest
import geopandas as gpd
from shapely import geometry


@pytest.fixture
def stmat():
    npoints = 10
    ntime = 5
    return xr.Dataset(
        data_vars=dict(
            amplitude=(
                ["points", "time"],
                da.arange(npoints * ntime).reshape((npoints, ntime)),
            ),
            phase=(
                ["points", "time"],
                da.arange(npoints * ntime).reshape((npoints, ntime)),
            ),
        ),
        coords=dict(
            lon=(["points"], da.arange(npoints)),
            lat=(["points"], da.arange(npoints)),
            time=(["time"], np.arange(ntime)),
        ),
    ).unify_chunks()


@pytest.fixture
def stmat_rd():
    # A STM with rd coordinates
    npoints = 10
    ntime = 5
    return xr.Dataset(
        data_vars=dict(
            amplitude=(
                ["points", "time"],
                da.arange(npoints * ntime).reshape((npoints, ntime)),
            ),
            phase=(
                ["points", "time"],
                da.arange(npoints * ntime).reshape((npoints, ntime)),
            ),
        ),
        coords=dict(
            rdx=(["points"], da.arange(npoints)),
            rdy=(["points"], da.arange(npoints)),
            time=(["time"], np.arange(ntime)),
        ),
    ).unify_chunks()


@pytest.fixture
def stmat_only_point():
    npoints = 10
    return xr.Dataset(
        data_vars=dict(
            amplitude=(["points"], da.arange(npoints)),
            phase=(["points"], da.arange(npoints)),
            pnt_height=(["points"], da.arange(npoints))
        ),
        coords=dict(
            lon=(["points"], da.arange(npoints)), lat=(["points"], da.arange(npoints))
        ),
    ).unify_chunks()


@pytest.fixture
def polygon():
    p1 = geometry.Point(1, 1)
    p2 = geometry.Point(1, 2)
    p3 = geometry.Point(3, 3)
    p4 = geometry.Point(2, 1)
    pointList = [p1, p2, p3, p4, p1]

    data = {
        "ID": ["001"],
        "temperature": [15.24],
        "geometry": [geometry.Polygon(pointList)],
    }

    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.fixture
def multi_polygon():
    # Two ploygons

    # Polygon 1
    p1 = geometry.Point(1, 1)
    p2 = geometry.Point(1, 2)
    p3 = geometry.Point(3, 3)
    p4 = geometry.Point(2, 1)
    pointList1 = [p1, p2, p3, p4, p1]

    # Polygon 2
    p1 = geometry.Point(5, 5)
    p2 = geometry.Point(5, 6)
    p3 = geometry.Point(7, 7)
    p4 = geometry.Point(6, 5)
    pointList2 = [p1, p2, p3, p4, p1]

    data = {
        "ID": ["001", "002"],
        "temperature": [15.24, 14.12],
        "geometry": [geometry.Polygon(pointList1), geometry.Polygon(pointList2)],
    }

    return gpd.GeoDataFrame(data, crs="EPSG:4326")

class TestRegulateDims:
    def test_time_dim_exists(self, stmat_only_point):
        stm_reg = stmat_only_point.stm.regulate_dims()
        assert "time" in stm_reg.dims.keys()
    
    def test_time_dim_size_one(self, stmat_only_point):
        stm_reg = stmat_only_point.stm.regulate_dims()
        assert stm_reg.dims["time"]==1
    
    def test_pnt_time_dim_nonexists(self, stmat_only_point):
        """
        For data variable with name pattern "pnt_*", there should be no time dimension. 
        """
        stm_reg = stmat_only_point.stm.regulate_dims()
        assert "time" not in stm_reg['pnt_height'].dims

    def test_subset_works_after_regulate_dims(self, stmat_only_point):
        stm_reg = stmat_only_point.stm.regulate_dims()
        stm_reg_subset = stm_reg.stm.subset(method="threshold", var="pnt_height", threshold=">5")
        assert stm_reg_subset.dims["points"] == 4

class TestAttributes:
    def test_numpoints(self, stmat):
        assert stmat.stm.numPoints == 10

    def test_numepochss(self, stmat):
        assert stmat.stm.numEpochs == 5


class TestSubset:
    def test_check_missing_dimension(self, stmat_only_point):
        with pytest.raises(KeyError):
            stmat_only_point.stm.subset(method="threshold", var="pnt_height", threshold=">5")

    def test_method_not_implemented(self, stmat):
        with pytest.raises(NotImplementedError):
            stmat.stm.subset(method="something_else")

    def test_subset_with_threshold(self, stmat):
        # dummy threshold, first three are 2, others 1
        # test selecting first 3
        v_thres = np.ones(
            stmat.points.shape,
        )
        v_thres[0:3] = 2
        stmat = stmat.assign(
            {
                "thres": (
                    ["points"],
                    da.from_array(v_thres),
                )
            }
        )
        stmat_subset = stmat.stm.subset(method="threshold", var="thres", threshold=">1")
        assert stmat_subset.equals(stmat.sel(points=[0, 1, 2]))

    def test_subset_with_polygons(self, stmat, polygon):
        stmat_subset = stmat.stm.subset(method="polygon", polygon=polygon)
        assert stmat_subset.equals(stmat.sel(points=[2]))

    def test_subset_with_polygons_rd(self, stmat_rd, polygon):
        stmat_subset = stmat_rd.stm.subset(
            method="polygon", polygon=polygon, xlabel="rdx", ylabel="rdy"
        )
        assert stmat_subset.equals(stmat_rd.sel(points=[2]))

    def test_subset_with_multi_polygons(self, stmat, multi_polygon):
        stmat_subset = stmat.stm.subset(method="polygon", polygon=multi_polygon)
        assert stmat_subset.equals(stmat.sel(points=[2, 6]))

class TestEnrichment:
    def test_enrich_one_field_one_polygon(self, stmat, polygon):
        field = polygon.columns[0]
        stmat = stmat.stm.enrich_from_polygon(polygon, field)
        assert field in stmat.data_vars

        results = stmat[field].data.compute()
        results = results[results != None]
        assert np.all(results == np.array(polygon[field]))

    def test_enrich_multi_fields_one_polygon(self, stmat, polygon):
        # fields = polygon.columns[0:2]
        fields = ["ID", "temperature"]
        stmat = stmat.stm.enrich_from_polygon(polygon, fields)
        for field in fields:
            assert field in stmat.data_vars

            results = stmat[field].data.compute()
            results = results[results != None]
            assert np.all(results == np.array(polygon[field]))

    def test_enrich_one_field_multi_polygon(self, stmat, multi_polygon):
        field = multi_polygon.columns[0]
        stmat = stmat.stm.enrich_from_polygon(multi_polygon, field)
        assert field in stmat.data_vars

        results = stmat[field].data.compute()
        results = results[results != None]
        assert np.all(results == np.array(multi_polygon[field]))

    def test_enrich_multi_fields_multi_polygon(self, stmat, multi_polygon):
        fields = multi_polygon.columns[0:2]
        stmat = stmat.stm.enrich_from_polygon(multi_polygon, fields)
        for field in fields:
            assert field in stmat.data_vars

            results = stmat[field].data.compute()
            results = results[results != None]
            assert np.all(results == np.array(multi_polygon[field]))
