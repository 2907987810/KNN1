import numpy as np

from pandas.compat import reduce, string_types

import pandas as pd


# A token value Python's tokenizer probably will never use.
_BACKTICK_QUOTED_STRING = 100


def _ensure_decoded(s):
    """ if we have bytes, decode them to unicode """
    if isinstance(s, (np.bytes_, bytes)):
        s = s.decode(pd.get_option('display.encoding'))
    return s


def _result_type_many(*arrays_and_dtypes):
    """ wrapper around numpy.result_type which overcomes the NPY_MAXARGS (32)
    argument limit """
    try:
        return np.result_type(*arrays_and_dtypes)
    except ValueError:
        # we have > NPY_MAXARGS terms in our expression
        return reduce(np.result_type, arrays_and_dtypes)


def clean_column_name_with_spaces(name):
    """Check if name contains any spaces, if it contains any spaces
    the spaces will be removed and an underscore suffix is added."""
    if not isinstance(name, string_types) or " " not in name:
        return name
    return "_BACKTICK_QUOTED_STRING_" + name.replace(" ", "_")


class NameResolutionError(NameError):
    pass
