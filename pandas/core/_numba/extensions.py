"""
Utility classes/functions to let numba recognize
pandas Index/Series/DataFrame

Mostly vendored from https://github.com/numba/numba/blob/main/numba/tests/pdlike_usecase.py
"""

import operator

from numba.core import (
    cgutils,
    types,
)
from numba.core.datamodel import models
from numba.core.extending import (
    NativeValue,
    box,
    lower_builtin,
    make_attribute_wrapper,
    overload,
    register_model,
    type_callable,
    typeof_impl,
    unbox,
)
from numba.core.imputils import impl_ret_borrowed

from pandas.core.frame import DataFrame
from pandas.core.indexes.base import Index
from pandas.core.series import Series


# TODO: Range index support
# (not passing an index to series constructor doesn't work)
class IndexType(types.Buffer):
    """
    The type class for Index objects.
    """

    array_priority = 1000

    def __init__(self, dtype, layout, pyclass):
        self.pyclass = pyclass
        super().__init__(dtype, 1, layout)

    @property
    def key(self):
        return self.pyclass, self.dtype, self.layout

    @property
    def as_array(self):
        return types.Array(self.dtype, 1, self.layout)

    def copy(self, dtype=None, ndim=1, layout=None):
        assert ndim == 1
        if dtype is None:
            dtype = self.dtype
        layout = layout or self.layout
        return type(self)(dtype, layout, self.pyclass)


class SeriesType(types.ArrayCompatible):
    """
    The type class for Series objects.
    """

    array_priority = 1000

    def __init__(self, dtype, index):
        assert isinstance(index, IndexType)
        self.dtype = dtype
        self.index = index
        self.values = types.Array(self.dtype, 1, "C")
        name = f"series({dtype}, {index})"
        super().__init__(name)

    @property
    def key(self):
        return self.dtype, self.index

    @property
    def as_array(self):
        return self.values

    def copy(self, dtype=None, ndim=1, layout="C"):
        assert ndim == 1
        assert layout == "C"
        if dtype is None:
            dtype = self.dtype
        return type(self)(dtype, self.index)


class DataFrameType(types.ArrayCompatible):
    """
    The type class for Series objects.
    """

    array_priority = 1000

    def __init__(self, dtype, index, layout):
        assert isinstance(index, IndexType)
        self.dtype = dtype
        self.index = index
        self.layout = layout
        # TODO: Don't hardcode fortran order?
        self.values = types.Array(self.dtype, 2, layout)
        name = f"dataframe({dtype}, {index}, {layout})"
        super().__init__(name)

    @property
    def key(self):
        return self.dtype, self.index, self.layout

    @property
    def as_array(self):
        return self.values

    def copy(self, dtype=None, ndim=1, layout="C"):
        assert ndim == 2
        # assert layout == 'C'
        if dtype is None:
            dtype = self.dtype
        return type(self)(dtype, self.index, layout)


@typeof_impl.register(Index)
def typeof_index(val, c):
    arrty = typeof_impl(val._data, c)
    assert arrty.ndim == 1
    return IndexType(arrty.dtype, arrty.layout, type(val))


@typeof_impl.register(Series)
def typeof_series(val, c):
    index = typeof_impl(val.index, c)
    arrty = typeof_impl(val.values, c)
    assert arrty.ndim == 1
    assert arrty.layout == "C"
    return SeriesType(arrty.dtype, index)


@typeof_impl.register(DataFrame)
def typeof_df(val, c):
    index = typeof_impl(val.index, c)
    arrty = typeof_impl(val.values, c)
    assert arrty.ndim == 2
    return DataFrameType(arrty.dtype, index, arrty.layout)


@type_callable("__array_wrap__")
def type_array_wrap(context):
    def typer(input_type, result):
        if isinstance(input_type, (IndexType, SeriesType)):
            return input_type.copy(
                dtype=result.dtype, ndim=result.ndim, layout=result.layout
            )

    return typer


@type_callable(Series)
def type_series_constructor(context):
    def typer(data, index):
        if isinstance(index, IndexType) and isinstance(data, types.Array):
            assert data.layout == "C"
            assert data.ndim == 1
            return SeriesType(data.dtype, index)

    return typer


@type_callable(Index)
def type_index_constructor(context):
    def typer(data):
        if isinstance(data, types.Array):
            assert data.layout == "C"
            assert data.ndim == 1
            return IndexType(data.dtype, layout=data.layout, pyclass=Index)

    return typer


@type_callable(DataFrame)
def type_frame_constructor(context):
    def typer(data, index):
        if isinstance(index, IndexType) and isinstance(data, types.Array):
            # assert data.layout == 'F'
            assert data.ndim == 2
            return DataFrameType(data.dtype, index, data.layout)

    return typer


# Backend extensions for Index and Series and Frame
@register_model(IndexType)
class IndexModel(models.StructModel):
    def __init__(self, dmm, fe_type):
        members = [("data", fe_type.as_array)]
        models.StructModel.__init__(self, dmm, fe_type, members)


@register_model(SeriesType)
class SeriesModel(models.StructModel):
    def __init__(self, dmm, fe_type):
        members = [
            ("index", fe_type.index),
            ("values", fe_type.as_array),
        ]
        models.StructModel.__init__(self, dmm, fe_type, members)


@register_model(DataFrameType)
class DataFrameModel(models.StructModel):
    def __init__(self, dmm, fe_type):
        members = [
            ("index", fe_type.index),
            ("values", fe_type.as_array),
        ]
        models.StructModel.__init__(self, dmm, fe_type, members)


make_attribute_wrapper(IndexType, "data", "_data")

make_attribute_wrapper(SeriesType, "index", "index")
make_attribute_wrapper(SeriesType, "values", "values")

make_attribute_wrapper(DataFrameType, "index", "index")
make_attribute_wrapper(DataFrameType, "values", "values")


def make_index(context, builder, typ, **kwargs):
    return cgutils.create_struct_proxy(typ)(context, builder, **kwargs)


def make_series(context, builder, typ, **kwargs):
    return cgutils.create_struct_proxy(typ)(context, builder, **kwargs)


def make_dataframe(context, builder, typ, **kwargs):
    return cgutils.create_struct_proxy(typ)(context, builder, **kwargs)


@lower_builtin("__array__", IndexType)
def index_as_array(context, builder, sig, args):
    val = make_index(context, builder, sig.args[0], ref=args[0])
    return val._get_ptr_by_name("data")


@lower_builtin("__array__", SeriesType)
def series_as_array(context, builder, sig, args):
    val = make_series(context, builder, sig.args[0], ref=args[0])
    return val._get_ptr_by_name("values")


@lower_builtin("__array_wrap__", IndexType, types.Array)
def index_wrap_array(context, builder, sig, args):
    dest = make_index(context, builder, sig.return_type)
    dest.data = args[1]
    return impl_ret_borrowed(context, builder, sig.return_type, dest._getvalue())


@lower_builtin("__array_wrap__", SeriesType, types.Array)
def series_wrap_array(context, builder, sig, args):
    src = make_series(context, builder, sig.args[0], value=args[0])
    dest = make_series(context, builder, sig.return_type)
    dest.values = args[1]
    dest.index = src.index
    return impl_ret_borrowed(context, builder, sig.return_type, dest._getvalue())


@lower_builtin(Series, types.Array, IndexType)
def pdseries_constructor(context, builder, sig, args):
    data, index = args
    series = make_series(context, builder, sig.return_type)
    series.index = index
    series.values = data
    return impl_ret_borrowed(context, builder, sig.return_type, series._getvalue())


@lower_builtin(Index, types.Array)
def index_constructor(context, builder, sig, args):
    (data,) = args
    index = make_index(context, builder, sig.return_type)
    index.data = data
    return impl_ret_borrowed(context, builder, sig.return_type, index._getvalue())


@lower_builtin(DataFrame, types.Array, IndexType)
def pdframe_constructor(context, builder, sig, args):
    data, index = args
    df = make_dataframe(context, builder, sig.return_type)
    df.index = index
    df.values = data
    return impl_ret_borrowed(context, builder, sig.return_type, df._getvalue())


@unbox(IndexType)
def unbox_index(typ, obj, c):
    """
    Convert a Index object to a native structure.
    """
    data = c.pyapi.object_getattr_string(obj, "_data")
    index = make_index(c.context, c.builder, typ)
    index.data = c.unbox(typ.as_array, data).value

    return NativeValue(index._getvalue())


@unbox(SeriesType)
def unbox_series(typ, obj, c):
    """
    Convert a Series object to a native structure.
    """
    index = c.pyapi.object_getattr_string(obj, "index")
    values = c.pyapi.object_getattr_string(obj, "values")
    series = make_series(c.context, c.builder, typ)
    series.index = c.unbox(typ.index, index).value
    series.values = c.unbox(typ.values, values).value

    return NativeValue(series._getvalue())


@unbox(DataFrameType)
def unbox_df(typ, obj, c):
    """
    Convert a Series object to a native structure.
    """
    index = c.pyapi.object_getattr_string(obj, "index")
    values = c.pyapi.object_getattr_string(obj, "values")
    df = make_dataframe(c.context, c.builder, typ)
    df.index = c.unbox(typ.index, index).value
    df.values = c.unbox(typ.values, values).value

    return NativeValue(df._getvalue())


@box(IndexType)
def box_index(typ, val, c):
    """
    Convert a native index structure to a Index object.
    """
    # First build a Numpy array object, then wrap it in a Index
    index = make_index(c.context, c.builder, typ, value=val)
    classobj = c.pyapi.unserialize(c.pyapi.serialize_object(typ.pyclass))
    arrayobj = c.box(typ.as_array, index.data)
    indexobj = c.pyapi.call_function_objargs(classobj, (arrayobj,))
    return indexobj


@box(SeriesType)
def box_series(typ, val, c):
    """
    Convert a native series structure to a Series object.
    """
    series = make_series(c.context, c.builder, typ, value=val)
    classobj = c.pyapi.unserialize(c.pyapi.serialize_object(Series))
    indexobj = c.box(typ.index, series.index)
    arrayobj = c.box(typ.as_array, series.values)
    seriesobj = c.pyapi.call_function_objargs(classobj, (arrayobj, indexobj))
    return seriesobj


@box(DataFrameType)
def box_df(typ, val, c):
    """
    Convert a native series structure to a DataFrame object.
    """
    df = make_dataframe(c.context, c.builder, typ, value=val)
    classobj = c.pyapi.unserialize(c.pyapi.serialize_object(DataFrame))
    indexobj = c.box(typ.index, df.index)
    arrayobj = c.box(typ.as_array, df.values)
    dfobj = c.pyapi.call_function_objargs(classobj, (arrayobj, indexobj))
    return dfobj


@overload(operator.getitem)
def series_getitem(series, idx):
    if isinstance(series, SeriesType):
        return lambda series, idx: series.values[idx]


@overload(len)
def series_len(series):
    """
    len(Series)
    """
    if isinstance(series, SeriesType):

        def len_impl(series):
            return len(series.values)

        return len_impl
