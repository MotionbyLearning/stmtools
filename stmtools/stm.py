import xarray as xr
from rasterio import features
import math
import numpy as np
import geopandas as gpd
import affine
from pathlib import Path
from shapely.strtree import STRtree
from shapely.geometry import Point
from collections.abc import Iterable
import dask.array as da

import logging

logger = logging.getLogger(__name__)

# Inspiration:
#   - https://docs.xarray.dev/en/stable/internals/extending-xarray.html
#   - https://corteva.github.io/rioxarray/html/_modules/rioxarray/raster_dataset.html


@xr.register_dataset_accessor("stm")
class SpaceTimeMatrix:
    """
    Space-Time Matrix
    """

    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def add_metadata(self, metadata):
        """
        Assign metadata to the STM.

        Parameters
        ----------
        metadata : str or dict
            input metadata

        Returns
        -------
        xarray.Dataset
            STM with assigned attributes.
        """
        self._obj = self._obj.assign_attrs(metadata)
        return self._obj

    def regulate_dims(self, points_label=None, time_label=None):
        """
        Regulate the dimension of a Space-Time Matrix instance. 
        An STM should have two dimensions: "points" and "time".
        """

        if (
            (points_label is None)
            and (time_label is None)
            and all([k not in self._obj.dims.keys() for k in ["points", "time"]])
        ):
            raise ValueError(
                'No "points" nor "time" dimension found. You should specify either "points_label" or ""time_label'
            )

        # Check time dimension
        for key, label in zip(["points", "time"], [points_label, time_label]):
            if key not in self._obj.dims.keys():
                if label is None:
                    ds_reg = self._obj.expand_dims({key: 1})
                elif isinstance(label, str):
                    ds_reg = self._obj.rename_dims({label: key})
                else:
                    raise ValueError(f'"{key}" dimension label should be a string.')
        ds_reg = ds_reg.transpose("points", "time")

        # Squeeze the time dimension for all point attibutes, if exists
        for var in ds_reg.data_vars.keys():
            if var.startswith("pnt_"):
                if "time" in ds_reg[var].dims:
                    ds_reg[var] = ds_reg[var].squeeze(dim="time")

        return ds_reg

    def subset(self, method: str, **kwargs):
        """
        Select a subset of the STM

        Parameters
        ----------
        method : str
            Method of subsetting. Choose from "threshold", "density" and "polygon".
            - threshold: select all points with a threshold criterion, e.g.
                data_xr.stm.subset(method="threshold", var="thres", threshold='>1')
            - density: select one point in every [dx, dy] cell, e.g.
                data_xr.stm.subset(method='density', dx=0.1, dy=0.1)
            - polygon: select all points inside a given polygon, e.g.
                data_xr.stm.subset(method='polygon', polygon=path_polygon_file)
                or
                import geopandas as gpd
                polygon = gpd.read_file(path_polygon_file)
                data_xr.stm.subset(method='polygon', polygon=polygon)

        Returns
        -------
        xarray.Dataset
            A subset of the original STM.
        """

        match method:  # Match statements available only from python 3.10 onwards
            case "threshold":
                _check_threshold_kwargs(
                    **kwargs
                )  # Check is all required kwargs are available
                if kwargs["threshold"][0] == "<":
                    str_parts = kwargs["threshold"].partition("<")
                    check_mult_relops(
                        str_parts[2]
                    )  # Check to ensure multiple relational operators are not present
                    idx = (self._obj[kwargs["var"]] < float(str_parts[2])).compute()
                    data_xr_subset = self._obj.where(idx, drop=True)
                elif kwargs["threshold"][0] == ">":
                    str_parts = kwargs["threshold"].partition(">")
                    check_mult_relops(str_parts[2])
                    idx = (self._obj[kwargs["var"]] > float(str_parts[2])).compute()
                    data_xr_subset = self._obj.where(idx, drop=True)
                else:
                    raise Exception(
                        "Suitable relational operator not found! Please check input"
                    )
            case "density":
                check_density_kwargs(**kwargs)  # Check for all require kwargs
                gdf = gpd.GeoDataFrame(
                    self._obj["points"],
                    geometry=gpd.points_from_xy(
                        self._obj[kwargs["x"]], self._obj[kwargs["y"]]
                    ),
                )
                # Make a 2D grid based on the points coverage and input density threshold
                grid_cell = ((shapes) for shapes in zip(gdf.geometry, gdf.index))
                out_x = math.ceil(
                    (max(self._obj[kwargs["x"]]) - min(self._obj[kwargs["x"]]))
                    / kwargs["dx"]
                )
                out_y = math.ceil(
                    (max(self._obj[kwargs["y"]]) - min(self._obj[kwargs["y"]]))
                    / kwargs["dy"]
                )
                # Rasterize the points
                # If multiple points in one gridcell, only the first point will be recorded
                # In this way one point is selected per gridcell
                raster = features.rasterize(
                    shapes=grid_cell,
                    out_shape=[out_x, out_y],
                    fill=np.NAN,
                    all_touched=True,
                    default_value=1,
                    transform=affine.Affine.from_gdal(
                        min(self._obj[kwargs["x"]]),
                        kwargs["dx"],
                        0.0,
                        max(self._obj[kwargs["y"]]),
                        0.0,
                        -1 * kwargs["dy"],
                    ),
                )
                # Select by rasterization results
                subset = [
                    item for item in np.unique(raster) if not (math.isnan(item)) == True
                ]
                data_xr_subset = self._obj.sel(points=subset)
            case "polygon":
                _check_polygon_kwargs(**kwargs)
                if "xlabel" not in kwargs:
                    keyx = "lon"
                else:
                    keyx = kwargs["xlabel"]
                if "ylabel" not in kwargs:
                    keyy = "lat"
                else:
                    keyy = kwargs["ylabel"]
                mask = self._obj.stm._in_polygon(
                    kwargs["polygon"], xlabel=keyx, ylabel=keyy
                )
                idx = self._obj.points.data[mask.data]
                data_xr_subset = self._obj.sel(points=idx)
            case other:
                raise NotImplementedError(
                    "Method: {} is not implemented.".format(method)
                )
        chunks = {
            "points": min(
                self._obj.chunksizes["points"][0], data_xr_subset.points.shape[0]
            ),
            "time": min(self._obj.chunksizes["time"][0], data_xr_subset.time.shape[0]),
        }

        data_xr_subset = data_xr_subset.chunk(chunks)

        return data_xr_subset

    def enrich_from_polygon(self, polygon, fields, xlabel="lon", ylabel="lat"):
        """
        Enrich the SpaceTimeMatrix from one or more attribute fields of a (multi-)polygon.

        Each attribute in fields will be assigned as a data variable to the STM.
        If a point of the STM falls into the given polygon, the value of the specified field will be added. For points outside the (multi-)polygon, the value will be None.

        Parameters
        ----------
        polygon : geopandas.GeoDataFrame, str, or pathlib.Path
            Polygon or multi-polygon with contextual information for enrichment
        fields : str or list of str
            Field name(s) in the (multi-)polygon for enrichment
        xlabel : str, optional
            Name of the x-coordinates of the STM, by default "lon"
        ylabel : str, optional
            Name of the y-coordinates of the STM, by default "lat"

        Returns
        -------
        xarray.Dataset
            Enriched STM.
        """
        _ = _validate_coords(self._obj, xlabel, ylabel)

        # Check if fields is a Iterable or a str
        if isinstance(fields, str):
            fields = [fields]
        elif not isinstance(fields, Iterable):
            raise ValueError("fields need to be a Iterable or a string")

        # Get polygon type and the first row
        if isinstance(polygon, gpd.GeoDataFrame):
            type_polygon = "GeoDataFrame"
            polygon_one_row = polygon.iloc[0:1]
        elif isinstance(polygon, Path) or isinstance(polygon, str):
            type_polygon = "File"
            polygon_one_row = gpd.read_file(polygon, rows=1)
        else:
            raise NotImplementedError("Cannot recognize the input polygon.")

        # Check if fields exists in polygon
        for field in fields:
            if field not in polygon_one_row.columns:
                raise ValueError(
                    'Field "{}" not found in the the input polygon'.format(field)
                )

        # Enrich all fields
        ds = self._obj
        chunks = (ds.chunksizes["points"][0],)  # Assign an empty fields to ds
        for field in fields:
            ds = ds.assign(
                {
                    field: (
                        ["points"],
                        da.from_array(np.full(ds.points.shape, None), chunks=chunks),
                    )
                }
            )
        ds = xr.map_blocks(
            _enrich_from_polygon_block,
            ds,
            args=(polygon, fields, xlabel, ylabel, type_polygon),
            template=ds,
        )

        return ds

    def _in_polygon(self, polygon, xlabel="lon", ylabel="lat"):
        """
        Test if points of a STM is inside a given (multi-polygon) and return result as a boolean Dask array.

        Parameters
        ----------
        polygon : geopandas.GeoDataFrame, str, or pathlib.Path
            Polygon or multi-polygon for query
        xlabel : str, optional
            Name of the x-coordinates of the STM, by default "lon"
        ylabel : str, optional
            Name of the y-coordinates of the STM, by default "lat"

        Returns
        -------
        Dask.array
            A boolean Dask array. True where points are inside the (multi-)polygon.
        """

        # Check if coords exists
        _ = _validate_coords(self._obj, xlabel, ylabel)

        # Get polygon type and the first row
        if isinstance(polygon, gpd.GeoDataFrame):
            type_polygon = "GeoDataFrame"
        elif isinstance(polygon, Path) or isinstance(polygon, str):
            type_polygon = "File"
        else:
            raise NotImplementedError("Cannot recognize the input polygon.")

        # Enrich all fields
        ds = self._obj
        chunks = (ds.chunksizes["points"][0],)  # Assign an empty fields to ds
        ds = ds.assign(
            {
                "mask": (
                    ["points"],
                    da.from_array(np.full(ds.points.shape, False), chunks=chunks),
                )
            }
        )
        mask = ds["mask"]
        mask = xr.map_blocks(
            _in_polygon_block,
            mask,
            args=(polygon, xlabel, ylabel, type_polygon),
            template=mask,
        )

        return mask


def _in_polygon_block(mask, polygon, xlabel, ylabel, type_polygon):
    """
    Block-wise function for "_in_polygon".
    """
    match_list, _ = _ml_str_query(mask[xlabel], mask[ylabel], polygon, type_polygon)
    intmid = np.unique(match_list[:, 1])  # incase overlapping polygons
    mask.data[intmid] = True

    return mask


def _enrich_from_polygon_block(ds, polygon, fields, xlabel, ylabel, type_polygon):
    """
    Block-wise function for "enrich_from_polygon".
    """

    # Get the match list
    match_list, polygon = _ml_str_query(ds[xlabel], ds[ylabel], polygon, type_polygon)

    _ds = ds.copy(deep=True)

    if match_list.ndim == 2:
        intuids = np.unique(match_list[:, 0])
        for intuid in intuids:
            intm = np.where(match_list[:, 0] == intuid)[0]
            intmid = match_list[intm, 1]
            for field in fields:
                _ds[field].data[intmid] = polygon.iloc[intuid][field]

    return _ds


def _ml_str_query(xx, yy, polygon, type_polygon):
    """
    Test if a set of points is inside a (multi-)polygon using Sort-Tile-Recursive (STR) query, Get the match list.

    Parameters
    ----------
    xx : array_like
        Vector array of the x coordinates of the points
    yy : array_like
        Vector array of the y coordinates of the points
    polygon : geopandas.GeoDataFrame, str, or pathlib.Path
        Polygon or multi-polygon for query
    type_polygon : str
        Choose from "GeoDataFrame" or "File"

    Returns
    -------
    array_like
        An array with two columns. The first column is the positional index into the list of polygons being used to query the tree. The second column is the positional index into the list of points for which the tree was constructed.
    """

    # Crop the polygon to the bounding box of the block
    xmin, ymin, xmax, ymax = [
        xx.data.min(),
        yy.data.min(),
        xx.data.max(),
        yy.data.max(),
    ]
    match type_polygon:
        case "GeoDataFrame":
            polygon = polygon.cx[xmin:xmax, ymin:ymax]
        case "File":
            polygon = gpd.read_file(polygon, bbox=(xmin, ymin, xmax, ymax))

    # Build STR tree for points
    pnttree = STRtree(gpd.GeoSeries(map(Point, zip(xx.data, yy.data))))

    match_list = pnttree.query(polygon.geometry, predicate="contains").T

    return match_list, polygon


def check_mult_relops(string):
    relops = ["<", ">"]
    for i in relops:
        if i in string:
            raise Exception("Multiple relational operators found! Please check input")


def _check_threshold_kwargs(**kwargs):
    req_kwargs = ["var", "threshold"]
    for i in req_kwargs:
        if i not in kwargs:
            raise Exception("Missing expected keyword argument: %s" % i)


def _check_polygon_kwargs(**kwargs):
    req_kwargs = ["polygon"]
    for i in req_kwargs:
        if i not in kwargs:
            raise Exception("Missing expected keyword argument: %s" % i)


def check_density_kwargs(**kwargs):
    req_kwargs = ["x", "y", "dx", "dy"]
    for i in req_kwargs:
        if i not in kwargs:
            raise Exception("Missing expected keyword argument: %s" % i)
        if i in ["dx", "dy"]:
            if not isinstance(kwargs[i], float):
                raise Exception(
                    "Keyword argument %s should be an floating point number" % i
                )


def _validate_coords(ds, xlabel, ylabel):
    """
    Check if dataset has coordinates xlabel and ylabel

    Parameters
    ----------
    ds : xarray.dataset
        dataset to query
    xlabel : str
        Name of x coordinates
    ylabel : str
        Name of y coordinates

    Returns
    -------
    int
        If xlabel and ylabel are in the coordinates of ds, return 1. If the they are in the data variables, return 2 and raise a warning

    Raises
    ------
    ValueError
        If xlabel or ylabel neither exists in coordinates, raise ValueError
    """

    for clabel in [xlabel, ylabel]:
        if clabel not in ds.coords.keys():
            if clabel in ds.data_vars.keys():
                logger.warning(
                    '"{}"was not found in coordinates, but in data variables. '
                    "We will proceed with the data variable. "
                    'Please consider registering "{}" in the coordinates using '
                    '"xarray.Dataset.assign".'.format(clabel, clabel)
                )
                return 2
            else:
                raise ValueError('Coordinate label "{}" was not found.'.format(clabel))
    return 1
