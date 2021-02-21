from __future__ import annotations

import abc
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Hashable,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

import numpy as np

from pandas._config import option_context

from pandas._libs import lib
from pandas._typing import (
    AggFuncType,
    AggFuncTypeBase,
    AggFuncTypeDict,
    AggObjType,
    Axis,
    FrameOrSeriesUnion,
)
from pandas.util._decorators import cache_readonly

from pandas.core.dtypes.cast import is_nested_object
from pandas.core.dtypes.common import (
    is_dict_like,
    is_extension_array_dtype,
    is_list_like,
    is_sequence,
)
from pandas.core.dtypes.generic import (
    ABCDataFrame,
    ABCNDFrame,
    ABCSeries,
)

from pandas.core.algorithms import safe_sort
from pandas.core.base import (
    DataError,
    SpecificationError,
)
import pandas.core.common as com
from pandas.core.construction import (
    array as pd_array,
    create_series_with_explicit_dtype,
)

if TYPE_CHECKING:
    from pandas import (
        DataFrame,
        Index,
        Series,
    )
    from pandas.core.groupby import (
        DataFrameGroupBy,
        SeriesGroupBy,
    )
    from pandas.core.resample import Resampler
    from pandas.core.window.rolling import BaseWindow

ResType = Dict[int, Any]


def frame_apply(
    obj: DataFrame,
    func: AggFuncType,
    axis: Axis = 0,
    raw: bool = False,
    result_type: Optional[str] = None,
    args=None,
    kwargs=None,
) -> FrameApply:
    """ construct and return a row or column based frame apply object """
    axis = obj._get_axis_number(axis)
    klass: Type[FrameApply]
    if axis == 0:
        klass = FrameRowApply
    elif axis == 1:
        klass = FrameColumnApply

    return klass(
        obj,
        func,
        raw=raw,
        result_type=result_type,
        args=args,
        kwargs=kwargs,
    )


def series_apply(
    obj: Series,
    func: AggFuncType,
    convert_dtype: bool = True,
    args=None,
    kwargs=None,
) -> SeriesApply:
    return SeriesApply(
        obj,
        func,
        convert_dtype,
        args,
        kwargs,
    )


class Apply(metaclass=abc.ABCMeta):
    axis: int

    def __init__(
        self,
        obj: AggObjType,
        func,
        raw: bool,
        result_type: Optional[str],
        args,
        kwargs,
    ):
        self.obj = obj
        self.raw = raw
        self.args = args or ()
        self.kwargs = kwargs or {}

        if result_type not in [None, "reduce", "broadcast", "expand"]:
            raise ValueError(
                "invalid value for result_type, must be one "
                "of {None, 'reduce', 'broadcast', 'expand'}"
            )

        self.result_type = result_type

        # curry if needed
        if (
            (kwargs or args)
            and not isinstance(func, (np.ufunc, str))
            and not is_list_like(func)
        ):

            def f(x):
                return func(x, *args, **kwargs)

        else:
            f = func

        self.orig_f: AggFuncType = func
        self.f: AggFuncType = f

    @property
    def index(self) -> Index:
        return self.obj.index

    @property
    def agg_axis(self) -> Index:
        return self.obj._get_agg_axis(self.axis)

    @abc.abstractmethod
    def apply(self) -> FrameOrSeriesUnion:
        pass

    def agg(self) -> Optional[FrameOrSeriesUnion]:
        """
        Provide an implementation for the aggregators.

        Returns
        -------
        Result of aggregation, or None if agg cannot be performed by
        this method.
        """
        obj = self.obj
        arg = self.f
        args = self.args
        kwargs = self.kwargs

        _axis = kwargs.pop("_axis", None)
        if _axis is None:
            _axis = getattr(obj, "axis", 0)

        result = self.maybe_apply_str()
        if result is not None:
            return result

        if is_dict_like(arg):
            return self.agg_dict_like(_axis)
        elif is_list_like(arg):
            # we require a list, but not a 'str'
            return self.agg_list_like(_axis=_axis)

        if callable(arg):
            f = obj._get_cython_func(arg)
            if f and not args and not kwargs:
                return getattr(obj, f)()

        # caller can react
        return None

    def transform(self) -> FrameOrSeriesUnion:
        """
        Transform a DataFrame or Series.

        Returns
        -------
        DataFrame or Series
            Result of applying ``func`` along the given axis of the
            Series or DataFrame.

        Raises
        ------
        ValueError
            If the transform function fails or does not transform.
        """
        obj = self.obj
        func = self.orig_f
        axis = self.axis
        args = self.args
        kwargs = self.kwargs

        is_series = obj.ndim == 1

        if obj._get_axis_number(axis) == 1:
            assert not is_series
            return obj.T.transform(func, 0, *args, **kwargs).T

        if is_list_like(func) and not is_dict_like(func):
            func = cast(List[AggFuncTypeBase], func)
            # Convert func equivalent dict
            if is_series:
                func = {com.get_callable_name(v) or v: v for v in func}
            else:
                func = {col: func for col in obj}

        if is_dict_like(func):
            func = cast(AggFuncTypeDict, func)
            return self.transform_dict_like(func)

        # func is either str or callable
        func = cast(AggFuncTypeBase, func)
        try:
            result = self.transform_str_or_callable(func)
        except Exception:
            raise ValueError("Transform function failed")

        # Functions that transform may return empty Series/DataFrame
        # when the dtype is not appropriate
        if (
            isinstance(result, (ABCSeries, ABCDataFrame))
            and result.empty
            and not obj.empty
        ):
            raise ValueError("Transform function failed")
        if not isinstance(result, (ABCSeries, ABCDataFrame)) or not result.index.equals(
            obj.index
        ):
            raise ValueError("Function did not transform")

        return result

    def transform_dict_like(self, func):
        """
        Compute transform in the case of a dict-like func
        """
        from pandas.core.reshape.concat import concat

        obj = self.obj
        args = self.args
        kwargs = self.kwargs

        if len(func) == 0:
            raise ValueError("No transform functions were provided")

        if obj.ndim != 1:
            # Check for missing columns on a frame
            cols = set(func.keys()) - set(obj.columns)
            if len(cols) > 0:
                cols_sorted = list(safe_sort(list(cols)))
                raise SpecificationError(f"Column(s) {cols_sorted} do not exist")

        # Can't use func.values(); wouldn't work for a Series
        if any(is_dict_like(v) for _, v in func.items()):
            # GH 15931 - deprecation of renaming keys
            raise SpecificationError("nested renamer is not supported")

        results: Dict[Hashable, FrameOrSeriesUnion] = {}
        for name, how in func.items():
            colg = obj._gotitem(name, ndim=1)
            try:
                results[name] = colg.transform(how, 0, *args, **kwargs)
            except Exception as err:
                if str(err) in {
                    "Function did not transform",
                    "No transform functions were provided",
                }:
                    raise err

        # combine results
        if not results:
            raise ValueError("Transform function failed")
        return concat(results, axis=1)

    def transform_str_or_callable(self, func) -> FrameOrSeriesUnion:
        """
        Compute transform in the case of a string or callable func
        """
        obj = self.obj
        args = self.args
        kwargs = self.kwargs

        if isinstance(func, str):
            return obj._try_aggregate_string_function(func, *args, **kwargs)

        if not args and not kwargs:
            f = obj._get_cython_func(func)
            if f:
                return getattr(obj, f)()

        # Two possible ways to use a UDF - apply or call directly
        try:
            return obj.apply(func, args=args, **kwargs)
        except Exception:
            return func(obj, *args, **kwargs)

    def agg_list_like(self, _axis: int) -> FrameOrSeriesUnion:
        """
        Compute aggregation in the case of a list-like argument.

        Parameters
        ----------
        _axis : int, 0 or 1
            Axis to compute aggregation on.

        Returns
        -------
        Result of aggregation.
        """
        from pandas.core.reshape.concat import concat

        obj = self.obj
        arg = cast(List[AggFuncTypeBase], self.f)

        if _axis != 0:
            raise NotImplementedError("axis other than 0 is not supported")

        if obj._selected_obj.ndim == 1:
            selected_obj = obj._selected_obj
        else:
            selected_obj = obj._obj_with_exclusions

        results = []
        keys = []

        # degenerate case
        if selected_obj.ndim == 1:
            for a in arg:
                colg = obj._gotitem(selected_obj.name, ndim=1, subset=selected_obj)
                try:
                    new_res = colg.aggregate(a)

                except TypeError:
                    pass
                else:
                    results.append(new_res)

                    # make sure we find a good name
                    name = com.get_callable_name(a) or a
                    keys.append(name)

        # multiples
        else:
            for index, col in enumerate(selected_obj):
                colg = obj._gotitem(col, ndim=1, subset=selected_obj.iloc[:, index])
                try:
                    new_res = colg.aggregate(arg)
                except (TypeError, DataError):
                    pass
                except ValueError as err:
                    # cannot aggregate
                    if "Must produce aggregated value" in str(err):
                        # raised directly in _aggregate_named
                        pass
                    elif "no results" in str(err):
                        # raised directly in _aggregate_multiple_funcs
                        pass
                    else:
                        raise
                else:
                    results.append(new_res)
                    keys.append(col)

        # if we are empty
        if not len(results):
            raise ValueError("no results")

        try:
            return concat(results, keys=keys, axis=1, sort=False)
        except TypeError as err:

            # we are concatting non-NDFrame objects,
            # e.g. a list of scalars

            from pandas import Series

            result = Series(results, index=keys, name=obj.name)
            if is_nested_object(result):
                raise ValueError(
                    "cannot combine transform and aggregation operations"
                ) from err
            return result

    def agg_dict_like(self, _axis: int) -> FrameOrSeriesUnion:
        """
        Compute aggregation in the case of a dict-like argument.

        Parameters
        ----------
        _axis : int, 0 or 1
            Axis to compute aggregation on.

        Returns
        -------
        Result of aggregation.
        """
        obj = self.obj
        arg = cast(AggFuncTypeDict, self.f)

        is_aggregator = lambda x: isinstance(x, (list, tuple, dict))

        if _axis != 0:  # pragma: no cover
            raise ValueError("Can only pass dict with axis=0")

        selected_obj = obj._selected_obj

        # if we have a dict of any non-scalars
        # eg. {'A' : ['mean']}, normalize all to
        # be list-likes
        # Cannot use arg.values() because arg may be a Series
        if any(is_aggregator(x) for _, x in arg.items()):
            new_arg: AggFuncTypeDict = {}
            for k, v in arg.items():
                if not isinstance(v, (tuple, list, dict)):
                    new_arg[k] = [v]
                else:
                    new_arg[k] = v

                # the keys must be in the columns
                # for ndim=2, or renamers for ndim=1

                # ok for now, but deprecated
                # {'A': { 'ra': 'mean' }}
                # {'A': { 'ra': ['mean'] }}
                # {'ra': ['mean']}

                # not ok
                # {'ra' : { 'A' : 'mean' }}
                if isinstance(v, dict):
                    raise SpecificationError("nested renamer is not supported")
                elif isinstance(selected_obj, ABCSeries):
                    raise SpecificationError("nested renamer is not supported")
                elif (
                    isinstance(selected_obj, ABCDataFrame)
                    and k not in selected_obj.columns
                ):
                    raise KeyError(f"Column '{k}' does not exist!")

            arg = new_arg

        else:
            # deprecation of renaming keys
            # GH 15931
            keys = list(arg.keys())
            if isinstance(selected_obj, ABCDataFrame) and len(
                selected_obj.columns.intersection(keys)
            ) != len(keys):
                cols = list(
                    safe_sort(
                        list(set(keys) - set(selected_obj.columns.intersection(keys))),
                    )
                )
                raise SpecificationError(f"Column(s) {cols} do not exist")

        from pandas.core.reshape.concat import concat

        if selected_obj.ndim == 1:
            # key only used for output
            colg = obj._gotitem(obj._selection, ndim=1)
            results = {key: colg.agg(how) for key, how in arg.items()}
        else:
            # key used for column selection and output
            results = {
                key: obj._gotitem(key, ndim=1).agg(how) for key, how in arg.items()
            }

        # set the final keys
        keys = list(arg.keys())

        # Avoid making two isinstance calls in all and any below
        is_ndframe = [isinstance(r, ABCNDFrame) for r in results.values()]

        # combine results
        if all(is_ndframe):
            keys_to_use = [k for k in keys if not results[k].empty]
            # Have to check, if at least one DataFrame is not empty.
            keys_to_use = keys_to_use if keys_to_use != [] else keys
            axis = 0 if isinstance(obj, ABCSeries) else 1
            result = concat({k: results[k] for k in keys_to_use}, axis=axis)
        elif any(is_ndframe):
            # There is a mix of NDFrames and scalars
            raise ValueError(
                "cannot perform both aggregation "
                "and transformation operations "
                "simultaneously"
            )
        else:
            from pandas import Series

            # we have a dict of scalars
            # GH 36212 use name only if obj is a series
            if obj.ndim == 1:
                obj = cast("Series", obj)
                name = obj.name
            else:
                name = None

            result = Series(results, name=name)

        return result

    def maybe_apply_str(self) -> Optional[FrameOrSeriesUnion]:
        """
        Compute apply in case of a string.

        Returns
        -------
        result: Series, DataFrame, or None
            Result when self.f is a string, None otherwise.
        """
        f = self.f
        if not isinstance(f, str):
            return None

        obj = self.obj

        if f == "size" and isinstance(obj, ABCDataFrame):
            # Special-cased because DataFrame.size returns a single scalar
            value = obj.shape[self.axis]
            return obj._constructor_sliced(value, index=self.agg_axis, name="size")

        # Support for `frame.transform('method')`
        # Some methods (shift, etc.) require the axis argument, others
        # don't, so inspect and insert if necessary.
        func = getattr(obj, f, None)
        if callable(func):
            sig = inspect.getfullargspec(func)
            if "axis" in sig.args:
                self.kwargs["axis"] = self.axis
            elif self.axis != 0:
                raise ValueError(f"Operation {f} does not support axis=1")
        return obj._try_aggregate_string_function(f, *self.args, **self.kwargs)

    def maybe_apply_multiple(self) -> Optional[FrameOrSeriesUnion]:
        """
        Compute apply in case of a list-like or dict-like.

        Returns
        -------
        result: Series, DataFrame, or None
            Result when self.f is a list-like or dict-like, None otherwise.
        """
        # Note: dict-likes are list-like
        if not is_list_like(self.f):
            return None
        return self.obj.aggregate(self.f, self.axis, *self.args, **self.kwargs)


class FrameApply(Apply):
    obj: DataFrame

    # ---------------------------------------------------------------
    # Abstract Methods

    @property
    @abc.abstractmethod
    def result_index(self) -> Index:
        pass

    @property
    @abc.abstractmethod
    def result_columns(self) -> Index:
        pass

    @property
    @abc.abstractmethod
    def series_generator(self) -> Iterator[Series]:
        pass

    @abc.abstractmethod
    def wrap_results_for_axis(
        self, results: ResType, res_index: Index
    ) -> FrameOrSeriesUnion:
        pass

    # ---------------------------------------------------------------

    @property
    def res_columns(self) -> Index:
        return self.result_columns

    @property
    def columns(self) -> Index:
        return self.obj.columns

    @cache_readonly
    def values(self):
        return self.obj.values

    @cache_readonly
    def dtypes(self) -> Series:
        return self.obj.dtypes

    def apply(self) -> FrameOrSeriesUnion:
        """ compute the results """
        # dispatch to agg
        result = self.maybe_apply_multiple()
        if result is not None:
            return result

        # all empty
        if len(self.columns) == 0 and len(self.index) == 0:
            return self.apply_empty_result()

        # string dispatch
        result = self.maybe_apply_str()
        if result is not None:
            return result

        # ufunc
        elif isinstance(self.f, np.ufunc):
            with np.errstate(all="ignore"):
                results = self.obj._mgr.apply("apply", func=self.f)
            # _constructor will retain self.index and self.columns
            return self.obj._constructor(data=results)

        # broadcasting
        if self.result_type == "broadcast":
            return self.apply_broadcast(self.obj)

        # one axis empty
        elif not all(self.obj.shape):
            return self.apply_empty_result()

        # raw
        elif self.raw:
            return self.apply_raw()

        return self.apply_standard()

    def agg(self):
        obj = self.obj
        axis = self.axis

        # TODO: Avoid having to change state
        self.obj = self.obj if self.axis == 0 else self.obj.T
        self.axis = 0

        result = None
        try:
            result = super().agg()
        except TypeError as err:
            exc = TypeError(
                "DataFrame constructor called with "
                f"incompatible data and dtype: {err}"
            )
            raise exc from err
        finally:
            self.obj = obj
            self.axis = axis

        if axis == 1:
            result = result.T if result is not None else result

        if result is None:
            result = self.obj.apply(self.orig_f, axis, args=self.args, **self.kwargs)

        return result

    def apply_empty_result(self):
        """
        we have an empty result; at least 1 axis is 0

        we will try to apply the function to an empty
        series in order to see if this is a reduction function
        """
        assert callable(self.f)

        # we are not asked to reduce or infer reduction
        # so just return a copy of the existing object
        if self.result_type not in ["reduce", None]:
            return self.obj.copy()

        # we may need to infer
        should_reduce = self.result_type == "reduce"

        from pandas import Series

        if not should_reduce:
            try:
                r = self.f(Series([], dtype=np.float64))
            except Exception:
                pass
            else:
                should_reduce = not isinstance(r, Series)

        if should_reduce:
            if len(self.agg_axis):
                r = self.f(Series([], dtype=np.float64))
            else:
                r = np.nan

            return self.obj._constructor_sliced(r, index=self.agg_axis)
        else:
            return self.obj.copy()

    def apply_raw(self):
        """ apply to the values as a numpy array """

        def wrap_function(func):
            """
            Wrap user supplied function to work around numpy issue.

            see https://github.com/numpy/numpy/issues/8352
            """

            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                if isinstance(result, str):
                    result = np.array(result, dtype=object)
                return result

            return wrapper

        result = np.apply_along_axis(wrap_function(self.f), self.axis, self.values)

        # TODO: mixed type case
        if result.ndim == 2:
            return self.obj._constructor(result, index=self.index, columns=self.columns)
        else:
            return self.obj._constructor_sliced(result, index=self.agg_axis)

    def apply_broadcast(self, target: DataFrame) -> DataFrame:
        assert callable(self.f)

        result_values = np.empty_like(target.values)

        # axis which we want to compare compliance
        result_compare = target.shape[0]

        for i, col in enumerate(target.columns):
            res = self.f(target[col])
            ares = np.asarray(res).ndim

            # must be a scalar or 1d
            if ares > 1:
                raise ValueError("too many dims to broadcast")
            elif ares == 1:

                # must match return dim
                if result_compare != len(res):
                    raise ValueError("cannot broadcast result")

            result_values[:, i] = res

        # we *always* preserve the original index / columns
        result = self.obj._constructor(
            result_values, index=target.index, columns=target.columns
        )
        return result

    def apply_standard(self):
        results, res_index = self.apply_series_generator()

        # wrap results
        return self.wrap_results(results, res_index)

    def apply_series_generator(self) -> Tuple[ResType, Index]:
        assert callable(self.f)

        series_gen = self.series_generator
        res_index = self.result_index

        results = {}

        with option_context("mode.chained_assignment", None):
            for i, v in enumerate(series_gen):
                # ignore SettingWithCopy here in case the user mutates
                results[i] = self.f(v)
                if isinstance(results[i], ABCSeries):
                    # If we have a view on v, we need to make a copy because
                    #  series_generator will swap out the underlying data
                    results[i] = results[i].copy(deep=False)

        return results, res_index

    def wrap_results(self, results: ResType, res_index: Index) -> FrameOrSeriesUnion:
        from pandas import Series

        # see if we can infer the results
        if len(results) > 0 and 0 in results and is_sequence(results[0]):
            return self.wrap_results_for_axis(results, res_index)

        # dict of scalars

        # the default dtype of an empty Series will be `object`, but this
        # code can be hit by df.mean() where the result should have dtype
        # float64 even if it's an empty Series.
        constructor_sliced = self.obj._constructor_sliced
        if constructor_sliced is Series:
            result = create_series_with_explicit_dtype(
                results, dtype_if_empty=np.float64
            )
        else:
            result = constructor_sliced(results)
        result.index = res_index

        return result


class FrameRowApply(FrameApply):
    axis = 0

    def apply_broadcast(self, target: DataFrame) -> DataFrame:
        return super().apply_broadcast(target)

    @property
    def series_generator(self):
        return (self.obj._ixs(i, axis=1) for i in range(len(self.columns)))

    @property
    def result_index(self) -> Index:
        return self.columns

    @property
    def result_columns(self) -> Index:
        return self.index

    def wrap_results_for_axis(
        self, results: ResType, res_index: Index
    ) -> FrameOrSeriesUnion:
        """ return the results for the rows """

        if self.result_type == "reduce":
            # e.g. test_apply_dict GH#8735
            res = self.obj._constructor_sliced(results)
            res.index = res_index
            return res

        elif self.result_type is None and all(
            isinstance(x, dict) for x in results.values()
        ):
            # Our operation was a to_dict op e.g.
            #  test_apply_dict GH#8735, test_apply_reduce_to_dict GH#25196 #37544
            res = self.obj._constructor_sliced(results)
            res.index = res_index
            return res

        try:
            result = self.obj._constructor(data=results)
        except ValueError as err:
            if "All arrays must be of the same length" in str(err):
                # e.g. result = [[2, 3], [1.5], ['foo', 'bar']]
                #  see test_agg_listlike_result GH#29587
                res = self.obj._constructor_sliced(results)
                res.index = res_index
                return res
            else:
                raise

        if not isinstance(results[0], ABCSeries):
            if len(result.index) == len(self.res_columns):
                result.index = self.res_columns

        if len(result.columns) == len(res_index):
            result.columns = res_index

        return result


class FrameColumnApply(FrameApply):
    axis = 1

    def apply_broadcast(self, target: DataFrame) -> DataFrame:
        result = super().apply_broadcast(target.T)
        return result.T

    @property
    def series_generator(self):
        values = self.values
        assert len(values) > 0

        # We create one Series object, and will swap out the data inside
        #  of it.  Kids: don't do this at home.
        ser = self.obj._ixs(0, axis=0)
        mgr = ser._mgr
        blk = mgr.blocks[0]

        if is_extension_array_dtype(blk.dtype):
            # values will be incorrect for this block
            # TODO(EA2D): special case would be unnecessary with 2D EAs
            obj = self.obj
            for i in range(len(obj)):
                yield obj._ixs(i, axis=0)

        else:
            for (arr, name) in zip(values, self.index):
                # GH#35462 re-pin mgr in case setitem changed it
                ser._mgr = mgr
                blk.values = arr
                ser.name = name
                yield ser

    @property
    def result_index(self) -> Index:
        return self.index

    @property
    def result_columns(self) -> Index:
        return self.columns

    def wrap_results_for_axis(
        self, results: ResType, res_index: Index
    ) -> FrameOrSeriesUnion:
        """ return the results for the columns """
        result: FrameOrSeriesUnion

        # we have requested to expand
        if self.result_type == "expand":
            result = self.infer_to_same_shape(results, res_index)

        # we have a non-series and don't want inference
        elif not isinstance(results[0], ABCSeries):
            result = self.obj._constructor_sliced(results)
            result.index = res_index

        # we may want to infer results
        else:
            result = self.infer_to_same_shape(results, res_index)

        return result

    def infer_to_same_shape(self, results: ResType, res_index: Index) -> DataFrame:
        """ infer the results to the same shape as the input object """
        result = self.obj._constructor(data=results)
        result = result.T

        # set the index
        result.index = res_index

        # infer dtypes
        result = result.infer_objects()

        return result


class SeriesApply(Apply):
    obj: Series
    axis = 0

    def __init__(
        self,
        obj: Series,
        func: AggFuncType,
        convert_dtype: bool,
        args,
        kwargs,
    ):
        self.convert_dtype = convert_dtype

        super().__init__(
            obj,
            func,
            raw=False,
            result_type=None,
            args=args,
            kwargs=kwargs,
        )

    def apply(self) -> FrameOrSeriesUnion:
        obj = self.obj

        if len(obj) == 0:
            return self.apply_empty_result()

        # dispatch to agg
        result = self.maybe_apply_multiple()
        if result is not None:
            return result

        # if we are a string, try to dispatch
        result = self.maybe_apply_str()
        if result is not None:
            return result

        return self.apply_standard()

    def agg(self):
        result = super().agg()
        if result is None:
            f = self.f
            args = self.args
            kwargs = self.kwargs

            # string, list-like, and dict-like are entirely handled in super
            assert callable(f)

            # we can be called from an inner function which
            # passes this meta-data
            kwargs.pop("_axis", None)
            kwargs.pop("_level", None)

            # try a regular apply, this evaluates lambdas
            # row-by-row; however if the lambda is expected a Series
            # expression, e.g.: lambda x: x-x.quantile(0.25)
            # this will fail, so we can try a vectorized evaluation

            # we cannot FIRST try the vectorized evaluation, because
            # then .agg and .apply would have different semantics if the
            # operation is actually defined on the Series, e.g. str
            try:
                result = self.obj.apply(f, *args, **kwargs)
            except (ValueError, AttributeError, TypeError):
                result = f(self.obj, *args, **kwargs)

        return result

    def apply_empty_result(self) -> Series:
        obj = self.obj
        return obj._constructor(dtype=obj.dtype, index=obj.index).__finalize__(
            obj, method="apply"
        )

    def apply_standard(self) -> FrameOrSeriesUnion:
        f = self.f
        obj = self.obj

        with np.errstate(all="ignore"):
            if isinstance(f, np.ufunc):
                return f(obj)

            # row-wise access
            if is_extension_array_dtype(obj.dtype) and hasattr(obj._values, "map"):
                # GH#23179 some EAs do not have `map`
                mapped = obj._values.map(f)
            else:
                values = obj.astype(object)._values
                mapped = lib.map_infer(values, f, convert=self.convert_dtype)

        if len(mapped) and isinstance(mapped[0], ABCSeries):
            # GH 25959 use pd.array instead of tolist
            # so extension arrays can be used
            return obj._constructor_expanddim(pd_array(mapped), index=obj.index)
        else:
            return obj._constructor(mapped, index=obj.index).__finalize__(
                obj, method="apply"
            )


class GroupByApply(Apply):
    obj: Union[SeriesGroupBy, DataFrameGroupBy]

    def __init__(
        self,
        obj: Union[SeriesGroupBy, DataFrameGroupBy],
        func: AggFuncType,
        args,
        kwargs,
    ):
        kwargs = kwargs.copy()
        self.axis = obj.obj._get_axis_number(kwargs.get("axis", 0))
        super().__init__(
            obj,
            func,
            raw=False,
            result_type=None,
            args=args,
            kwargs=kwargs,
        )

    def apply(self):
        raise NotImplementedError

    def transform(self):
        raise NotImplementedError


class ResamplerWindowApply(Apply):
    axis = 0
    obj: Union[Resampler, BaseWindow]

    def __init__(
        self,
        obj: Union[Resampler, BaseWindow],
        func: AggFuncType,
        args,
        kwargs,
    ):
        super().__init__(
            obj,
            func,
            raw=False,
            result_type=None,
            args=args,
            kwargs=kwargs,
        )

    def apply(self):
        raise NotImplementedError

    def transform(self):
        raise NotImplementedError
