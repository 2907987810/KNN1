import os
import sys

import numpy as np
import pytest

import pandas.util._test_decorators as td


class GoodDocStrings(object):
    """
    Collection of good doc strings.

    This class contains a lot of docstrings that should pass the validation
    script without any errors.
    """

    def plot(self, kind, color='blue', **kwargs):
        """
        Generate a plot.

        Render the data in the Series as a matplotlib plot of the
        specified kind.

        Parameters
        ----------
        kind : str
            Kind of matplotlib plot.
        color : str, default 'blue'
            Color name or rgb code.
        **kwargs
            These parameters will be passed to the matplotlib plotting
            function.
        """
        pass

    def sample(self):
        """
        Generate and return a random number.

        The value is sampled from a continuous uniform distribution between
        0 and 1.

        Returns
        -------
        float
            Random number generated.
        """
        return random.random()  # noqa: F821

    def random_letters(self):
        """
        Generate and return a sequence of random letters.

        The length of the returned string is also random, and is also
        returned.

        Returns
        -------
        length : int
            Length of the returned string.
        letters : str
            String of random letters.
        """
        length = random.randint(1, 10)  # noqa: F821
        letters = ''.join(random.choice(string.ascii_lowercase)  # noqa: F821
                          for i in range(length))
        return length, letters

    def sample_values(self):
        """
        Generate an infinite sequence of random numbers.

        The values are sampled from a continuous uniform distribution between
        0 and 1.

        Yields
        ------
        float
            Random number generated.
        """
        while True:
            yield random.random()  # noqa: F821

    def head(self):
        """
        Return the first 5 elements of the Series.

        This function is mainly useful to preview the values of the
        Series without displaying the whole of it.

        Returns
        -------
        Series
            Subset of the original series with the 5 first values.

        See Also
        --------
        Series.tail : Return the last 5 elements of the Series.
        Series.iloc : Return a slice of the elements in the Series,
            which can also be used to return the first or last n.
        """
        return self.iloc[:5]

    def head1(self, n=5):
        """
        Return the first elements of the Series.

        This function is mainly useful to preview the values of the
        Series without displaying the whole of it.

        Parameters
        ----------
        n : int
            Number of values to return.

        Returns
        -------
        Series
            Subset of the original series with the n first values.

        See Also
        --------
        tail : Return the last n elements of the Series.

        Examples
        --------
        >>> s = pd.Series(['Ant', 'Bear', 'Cow', 'Dog', 'Falcon'])
        >>> s.head()
        0   Ant
        1   Bear
        2   Cow
        3   Dog
        4   Falcon
        dtype: object

        With the `n` parameter, we can change the number of returned rows:

        >>> s.head(n=3)
        0   Ant
        1   Bear
        2   Cow
        dtype: object
        """
        return self.iloc[:n]

    def contains(self, pat, case=True, na=np.nan):
        """
        Return whether each value contains `pat`.

        In this case, we are illustrating how to use sections, even
        if the example is simple enough and does not require them.

        Parameters
        ----------
        pat : str
            Pattern to check for within each element.
        case : bool, default True
            Whether check should be done with case sensitivity.
        na : object, default np.nan
            Fill value for missing data.

        Examples
        --------
        >>> s = pd.Series(['Antelope', 'Lion', 'Zebra', np.nan])
        >>> s.str.contains(pat='a')
        0    False
        1    False
        2     True
        3      NaN
        dtype: object

        **Case sensitivity**

        With `case_sensitive` set to `False` we can match `a` with both
        `a` and `A`:

        >>> s.str.contains(pat='a', case=False)
        0     True
        1    False
        2     True
        3      NaN
        dtype: object

        **Missing values**

        We can fill missing values in the output using the `na` parameter:

        >>> s.str.contains(pat='a', na=False)
        0    False
        1    False
        2     True
        3    False
        dtype: bool
        """
        pass


class BadDocStrings(object):

    def func(self):

        """Some function.

        With several mistakes in the docstring.

        It has a blank like after the signature `def func():`.

        The text 'Some function' should go in the line after the
        opening quotes of the docstring, not in the same line.

        There is a blank line between the docstring and the first line
        of code `foo = 1`.

        The closing quotes should be in the next line, not in this one."""

        foo = 1
        bar = 2
        return foo + bar

    def astype(self, dtype):
        """
        Casts Series type.

        Verb in third-person of the present simple, should be infinitive.
        """
        pass

    def astype1(self, dtype):
        """
        Method to cast Series type.

        Does not start with verb.
        """
        pass

    def astype2(self, dtype):
        """
        Cast Series type

        Missing dot at the end.
        """
        pass

    def astype3(self, dtype):
        """
        Cast Series type from its current type to the new type defined in
        the parameter dtype.

        Summary is too verbose and doesn't fit in a single line.
        """
        pass

    def plot(self, kind, **kwargs):
        """
        Generate a plot.

        Render the data in the Series as a matplotlib plot of the
        specified kind.

        Note the blank line between the parameters title and the first
        parameter. Also, note that after the name of the parameter `kind`
        and before the colon, a space is missing.

        Also, note that the parameter descriptions do not start with a
        capital letter, and do not finish with a dot.

        Finally, the `**kwargs` parameter is missing.

        Parameters
        ----------

        kind: str
            kind of matplotlib plot
        """
        pass

    def method(self, foo=None, bar=None):
        """
        A sample DataFrame method.

        Do not import numpy and pandas.

        Try to use meaningful data, when it makes the example easier
        to understand.

        Try to avoid positional arguments like in `df.method(1)`. They
        can be alright if previously defined with a meaningful name,
        like in `present_value(interest_rate)`, but avoid them otherwise.

        When presenting the behavior with different parameters, do not place
        all the calls one next to the other. Instead, add a short sentence
        explaining what the example shows.

        Examples
        --------
        >>> import numpy as np
        >>> import pandas as pd
        >>> df = pd.DataFrame(np.ones((3, 3)),
        ...                   columns=('a', 'b', 'c'))
        >>> df.all(1)
        0    True
        1    True
        2    True
        dtype: bool
        >>> df.all(bool_only=True)
        Series([], dtype: bool)
        """
        pass


@td.skip_if_no('sphinx')
class TestValidator(object):

    @pytest.fixture(autouse=True, scope="class")
    def import_scripts(self):
        """
        Because the scripts directory is above the top level pandas package
        we need to hack sys.path to know where to find that directory for
        import. The below traverses up the file system to find the scripts
        directory, adds to location to sys.path and imports the required
        module into the global namespace before as part of class setup,
        reverting those changes on teardown.
        """
        up = os.path.dirname
        file_dir = up(os.path.abspath(__file__))
        script_dir = os.path.join(up(up(up(file_dir))), 'scripts')
        sys.path.append(script_dir)
        from validate_docstrings import validate_one
        globals()['validate_one'] = validate_one
        yield
        sys.path.pop()
        del globals()['validate_one']

    def _import_path(self, klass=None, func=None):
        """
        Build the required import path for tests in this module.

        Parameters
        ----------
        klass : str
            Class name of object in module.
        func : str
            Function name of object in module.

        Returns
        -------
        str
            Import path of specified object in this module
        """
        base_path = 'pandas.tests.scripts.test_validate_docstrings'
        if klass:
            base_path = '.'.join([base_path, klass])
        if func:
            base_path = '.'.join([base_path, func])

        return base_path

    def test_good_class(self):
        assert validate_one(self._import_path(klass='GoodDocStrings')) == 0

    @pytest.mark.parametrize("func", [
        'plot', 'sample', 'random_letters', 'sample_values', 'head', 'head1',
        'contains'])
    def test_good_functions(self, func):
        assert validate_one(self._import_path(klass='GoodDocStrings',
                                              func=func)) == 0

    @pytest.mark.parametrize("func", [
        'func', 'astype', 'astype1', 'astype2', 'astype3', 'plot', 'method'])
    def test_bad_functions(self, func):
        assert validate_one(self._import_path(klass='BadDocStrings',
                                              func=func)) > 0
