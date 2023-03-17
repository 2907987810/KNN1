# PDEP-6: Ban upcasting in setitem-like operations

- Created: 23 December 2022
- Status: Under discussion
- Discussion: [#50402](https://github.com/pandas-dev/pandas/pull/50402)
- Author: [Marco Gorelli](https://github.com/MarcoGorelli) ([original issue](https://github.com/pandas-dev/pandas/issues/39584) by [Joris Van den Bossche](https://github.com/jorisvandenbossche))
- Revision: 1

## Abstract

The suggestion is that setitem-like operations would
not change a ``Series``' dtype.

Current behaviour:
```python
In [1]: ser = pd.Series([1, 2, 3], dtype='int64')

In [2]: ser[2] = 'potage'

In [3]: ser  # dtype changed to 'object'!
Out[3]:
0         1
1         2
2    potage
dtype: object
```

Suggested behaviour:

```python
In [1]: ser = pd.Series([1, 2, 3])

In [2]: ser[2] = 'potage'  # raises!
---------------------------------------------------------------------------
TypeError: Invalid value 'potage' for dtype int64
```

## Motivation and Scope

Currently, pandas is extremely flexible in handling different dtypes.
However, this can potentially hide bugs, break user expectations, and copy data
in what looks like it should be an inplace operation.

An example of it hiding a bug is:
```python
In[9]: ser = pd.Series(pd.date_range("2000", periods=3))

In[10]: ser[2] = "2000-01-04"  # works, is converted to datetime64

In[11]: ser[2] = "2000-01-04x"  # typo - but pandas doesn't error, it upcasts to object
```

The scope of this PDEP is limited to setitem-like operations on Series.
For example, starting with
```python
df = DataFrame({"a": [1, 2, np.nan], "b": [4, 5, 6]})
ser = df["a"].copy()
```
then the following would all raise:
- ``ser[0] = 'foo'``;
- ``ser.fillna('foo', inplace=True)``;
- ``ser.where(ser.isna(), 'foo', inplace=True)``
- ``ser.fillna('foo', inplace=False)``;
- ``ser.where(ser.isna(), 'foo', inplace=False)``
- ``ser.iloc[0] = 'foo'``
- ``ser.loc[0] = 'foo'``
- ``df.loc[indexer, 'a'] = 'foo'``
- ``ser[indexer] = 'foo'``;

Examples of operations which would not raise are:
- ``ser.diff()``;
- ``pd.concat([ser, ser.astype(object)])``;
- ``ser.mean()``;
- ``ser[0] = 3.``;
- ``ser[0] = 3``.

## Detailed description

Concretely, the suggestion is:
- if a ``Series`` is of a given dtype, then a ``setitem``-like operation should not change its dtype;
- if a ``setitem``-like operation would previously have changed a ``Series``' dtype, it would now raise.

For a start, this would involve:

1. changing ``Block.setitem`` such that it doesn't have an ``except`` block in

  ```python
  value = extract_array(value, extract_numpy=True)
  try:
      casted = np_can_hold_element(values.dtype, value)
  except LossySetitemError:
      # current dtype cannot store value, coerce to common dtype
      nb = self.coerce_to_target_dtype(value)
      return nb.setitem(indexer, value)
  else:
  ```

2. making a similar change in:
   - ``Block.where``;
   - ``Block.putmask``;
   - ``EABackedBlock.setitem``;
   - ``EABackedBlock.where``;
   - ``EABackedBlock.putmask``;
   - ``_iLocIndexer._setitem_single_column``;

The above would already require several hundreds of tests to be adjusted.

### Ban upcasting altogether, or just upcasting to ``object``?

The trickiest part of this proposal concerns what to do when setting a float in an integer column:

```python
In[1]: ser = pd.Series([1, 2, 3])

In[2]: ser[0] = 1.5
```

This isn't necessarily a sign of a bug, because the user might just be thinking of their ``Series`` as being
numeric (without much regard for ``int`` vs ``float``) - ``'int64'`` is just what pandas happened to infer.

Possible options could be:
1. just raise, forcing users to be explicit;
2. convert the float value to ``int`` before setting it;
3. limit "banning upcasting" to when the upcasted dtype is ``object``.

Let us compare with what other libraries do:
- ``numpy``: option 2
- ``cudf``: option 2
- ``polars``: option 2
- ``R data.frame``: just upcasts (like pandas does now for non-nullable dtypes);
- ``pandas`` (nullable dtypes): option 1
- ``datatable``: option 1
- ``DataFrames.jl``: option 1

Option ``2`` would be a breaking behaviour change in pandas. Further,
if the objective of this PDEP is to prevent bugs, then this is also not desirable:
someone might set ``1.5`` and later be surprised to learn that they actually set ``1``.

There are several downsides to option ``3``:
- it would be inconsistent with the nullable dtypes' behaviour;
- it would also add complexity to the codebase and to tests;
- it would be hard to teach, as instead of being able to teach a simple rule,
  there would be a rule with exceptions;
- there would be a risk of loss of precision;
- it opens the door to other exceptions, such as not upcasting ``'int8'`` to ``'int16'``.

Option ``1`` is the maximally safe one in terms of protecting users from bugs, being
consistent with the current behaviour of nullable dtypes, and in being simple to teach.

## Usage and Impact

This would make pandas stricter, so there should not be any risk of introducing bugs. If anything, this would help prevent bugs.

Unfortunately, it would also risk annoy users who might have been intentionally upcasting.

Given that users can get around this as simply as with a ``.astype({'my_column': float})`` call,
I think it would be more beneficial to the community at large to err on the side of strictness.

## Out of scope

Enlargement. For example:
```python
ser = pd.Series([1, 2, 3])
ser[len(ser)] = 4.5
```
There is arguably a larger conversation to be had about whether that should be allowed
at all. To keep this proposal focused, it is intentionally excluded from the scope.

## Timeline

Deprecate sometime in the 2.x releases (after 2.0.0 has already been released), and enforce in 3.0.0.

### PDEP History

- 23 December 2022: Initial draft
