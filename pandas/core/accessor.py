# -*- coding: utf-8 -*-
"""

accessor.py contains base classes for implementing accessor properties
that can be mixed into or pinned onto other pandas classes.

"""
import traceback
import warnings

from pandas.core.common import AbstractMethodError
from pandas.compat import PY2
from pandas.errors import AccessorRegistrationWarning


class DirNamesMixin(object):
    _accessors = frozenset([])
    _deprecations = frozenset(['asobject'])

    def _dir_deletions(self):
        """ delete unwanted __dir__ for this object """
        return self._accessors | self._deprecations

    def _dir_additions(self):
        """ add addtional __dir__ for this object """
        rv = set()
        for accessor in self._accessors:
            try:
                getattr(self, accessor)
                rv.add(accessor)
            except AttributeError:
                pass
        return rv

    def __dir__(self):
        """
        Provide method name lookup and completion
        Only provide 'public' methods
        """
        rv = set(dir(type(self)))
        rv = (rv - self._dir_deletions()) | self._dir_additions()
        return sorted(rv)


class AccessorProperty(object):
    """Descriptor for implementing accessor properties like Series.str
    """

    def __init__(self, accessor_cls, construct_accessor=None):
        self.accessor_cls = accessor_cls
        self.construct_accessor = (construct_accessor or
                                   accessor_cls._make_accessor)
        self.__doc__ = accessor_cls.__doc__

    def __get__(self, instance, owner=None):
        if instance is None:
            # this ensures that Series.str.<method> is well defined
            return self.accessor_cls
        return self.construct_accessor(instance)

    def __set__(self, instance, value):
        raise AttributeError("can't set attribute")

    def __delete__(self, instance):
        raise AttributeError("can't delete attribute")


class PandasDelegate(object):
    """ an abstract base class for delegating methods/properties """

    @classmethod
    def _make_accessor(cls, data):
        raise AbstractMethodError("_make_accessor should be implemented"
                                  "by subclass and return an instance"
                                  "of `cls`.")

    def _delegate_property_get(self, name, *args, **kwargs):
        raise TypeError("You cannot access the "
                        "property {name}".format(name=name))

    def _delegate_property_set(self, name, value, *args, **kwargs):
        raise TypeError("The property {name} cannot be set".format(name=name))

    def _delegate_method(self, name, *args, **kwargs):
        raise TypeError("You cannot call method {name}".format(name=name))

    @classmethod
    def _add_delegate_accessors(cls, delegate, accessors, typ,
                                overwrite=False):
        """
        add accessors to cls from the delegate class

        Parameters
        ----------
        cls : the class to add the methods/properties to
        delegate : the class to get methods/properties & doc-strings
        acccessors : string list of accessors to add
        typ : 'property' or 'method'
        overwrite : boolean, default False
           overwrite the method/property in the target class if it exists
        """

        def _create_delegator_property(name):

            def _getter(self):
                return self._delegate_property_get(name)

            def _setter(self, new_values):
                return self._delegate_property_set(name, new_values)

            _getter.__name__ = name
            _setter.__name__ = name

            return property(fget=_getter, fset=_setter,
                            doc=getattr(delegate, name).__doc__)

        def _create_delegator_method(name):

            def f(self, *args, **kwargs):
                return self._delegate_method(name, *args, **kwargs)

            f.__name__ = name
            f.__doc__ = getattr(delegate, name).__doc__

            return f

        for name in accessors:

            if typ == 'property':
                f = _create_delegator_property(name)
            else:
                f = _create_delegator_method(name)

            # don't overwrite existing methods/properties
            if overwrite or not hasattr(cls, name):
                setattr(cls, name, f)


# Ported with modifications from xarray
# https://github.com/pydata/xarray/blob/master/xarray/core/extensions.py


class _CachedAccessor(object):
    """Custom property-like object (descriptor) for caching accessors."""
    def __init__(self, name, accessor):
        self._name = name
        self._accessor = accessor

    def __get__(self, obj, cls):
        if obj is None:
            # we're accessing the attribute of the class, i.e., Dataset.geo
            return self._accessor
        try:
            accessor_obj = self._accessor(obj)
        except AttributeError:
            # TODO
            # __getattr__ on data object will swallow any AttributeErrors
            # raised when initializing the accessor, so we need to raise
            # as something else (GH933):
            msg = 'error initializing %r accessor.' % self._name
            if PY2:
                msg += ' Full traceback:\n' + traceback.format_exc()
            raise RuntimeError(msg)
        # Replace the property with the accessor object. Inspired by:
        # http://www.pydanny.com/cached-property.html
        # We need to use object.__setattr__ because we overwrite __setattr__ on
        # AttrAccessMixin.
        object.__setattr__(obj, self._name, accessor_obj)
        return accessor_obj


def _register_accessor(name, cls):
    def decorator(accessor):
        if hasattr(cls, name):
            warnings.warn(
                'registration of accessor {!r} under name {!r} for type '
                '{!r} is overriding a preexisting attribute with the same '
                'name.'.format(accessor, name, cls),
                AccessorRegistrationWarning,
                stacklevel=2)
        setattr(cls, name, _CachedAccessor(name, accessor))
        return accessor
    return decorator


def register_dataframe_accessor(name):
    """Register a custom accessor on pandas.DataFrame objects.

    Parameters
    ----------
    name : str
        Name under which the accessor should be registered. A warning is issued
        if this name conflicts with a preexisting attribute.

    Examples
    --------

    In your library code::

        import pandas as pd

        @pd.extensions.register_dataframe_accessor("geo")
        class GeoAccessor(object):
            def __init__(self, pandas_obj):
                self._obj = pandas_obj

            @property
            def center(self):
                # return the geographic center point of this DataFarme
                lon = self._obj.latitude
                lat = self._obj.longitude
                return (float(lon.mean()), float(lat.mean()))

            def plot(self):
                # plot this array's data on a map, e.g., using Cartopy
                pass

    Back in an interactive IPython session:
        >>> ds = pd.DataFrame({'longitude': np.linspace(0, 10),
        ...                    'latitude': np.linspace(0, 20)})
        >>> ds.geo.center
        (5.0, 10.0)
        >>> ds.geo.plot()
        # plots data on a map

    See also
    --------
    register_index_accessor
    register_series_accessor
    """
    from pandas import DataFrame
    return _register_accessor(name, DataFrame)


def register_series_accessor(name):
    """Register a custom accessor on pandas.Series objects.

    Parameters
    ----------
    name : str
        Name under which the accessor should be registered. A warning is issued
        if this name conflicts with a preexisting attribute.

    See Also
    --------
    register_dataframe_accessor
    register_index_accessor
    """
    from pandas import Series
    return _register_accessor(name, Series)


def register_index_accessor(name):
    """Register a custom accessor on pandas.Index objects.

    Parameters
    ----------
    name : str
        Name under which the accessor should be registered. A warning is issued
        if this name conflicts with a preexisting attribute.

    See Also
    --------
    register_index_accessor
    register_series_accessor
    """
    from pandas import Index
    return _register_accessor(name, Index)
