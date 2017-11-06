import numpy as np
import pytest

from pandas import DataFrame
from pandas.util import testing as tm
from pandas.util.testing import assert_frame_equal


class TestMergeColumnAndIndex(object):
    # GH14355

    def setup_method(self):
        # Construct test DataFrames
        self.df1 = DataFrame(dict(
            outer=[1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4],
            inner=[1, 2, 3, 1, 2, 3, 4, 1, 2, 1, 2],
            v1=np.linspace(0, 1, 11)
        ))

        self.df2 = DataFrame(dict(
            outer=[1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 3, 3],
            inner=[1, 2, 2, 3, 3, 4, 2, 3, 1, 1, 2, 3],
            v2=np.linspace(10, 11, 12)
        ))

    @pytest.fixture(params=[[], ['outer'], ['outer', 'inner']])
    def left_df(self, request):
        """ Construct left test DataFrame with specified levels
        (any of 'outer', 'inner', and 'v1')"""
        levels = request.param
        res = self.df1

        if levels:
            res = res.set_index(levels)

        return res

    @pytest.fixture(params=[[], ['outer'], ['outer', 'inner']])
    def right_df(self, request):
        """ Construct right test DataFrame with specified levels
        (any of 'outer', 'inner', and 'v2')"""
        levels = request.param
        res = self.df2

        if levels:
            res = res.set_index(levels)

        return res

    @pytest.fixture(params=['inner', 'left', 'right', 'outer'])
    def how(self, request):
        return request.param

    @staticmethod
    def compute_expected(df_left, df_right,
                         on=None, left_on=None, right_on=None, how=None):
        """
        Compute the expected merge result for the test case.

        This method computes the expected result of merging two DataFrames on
        a combination of their columns and index levels. It does so by
        explicitly dropping/resetting their named index levels, performing a
        merge on their columns, and then finally restoring the appropriate
        index in the result.

        Parameters
        ----------
        df_left : DataFrame
            The left DataFrame (may have zero or more named index levels)
        df_right : DataFrame
            The right DataFrame (may have zero or more named index levels)
        on : list of str
            The on parameter to the merge operation
        left_on : list of str
            The left_on parameter to the merge operation
        right_on : list of str
            The right_on parameter to the merge operation
        how : str
            The how parameter to the merge operation

        Returns
        -------
        DataFrame
            The expected merge result
        """

        # Handle on param if specified
        if on is not None:
            left_on, right_on = on, on

        # Compute input named index levels
        left_levels = [n for n in df_left.index.names if n is not None]
        right_levels = [n for n in df_right.index.names if n is not None]

        # Compute output named index levels
        output_levels = [i for i in left_on
                         if i in right_levels and i in left_levels]

        # Drop index levels that aren't involved in the merge
        drop_left = [n for n in left_levels if n not in left_on]
        if drop_left:
            df_left = df_left.reset_index(drop_left, drop=True)

        drop_right = [n for n in right_levels if n not in right_on]
        if drop_right:
            df_right = df_right.reset_index(drop_right, drop=True)

        # Convert remaining index levels to columns
        reset_left = [n for n in left_levels if n in left_on]
        if reset_left:
            df_left = df_left.reset_index(level=reset_left)

        reset_right = [n for n in right_levels if n in right_on]
        if reset_right:
            df_right = df_right.reset_index(level=reset_right)

        # Perform merge
        expected = df_left.merge(df_right,
                                 left_on=left_on,
                                 right_on=right_on,
                                 how=how)

        # Restore index levels
        if output_levels:
            expected = expected.set_index(output_levels)

        return expected

    @pytest.mark.parametrize('on',
                             [['outer'], ['inner'],
                              ['outer', 'inner'],
                              ['inner', 'outer']])
    def test_merge_indexes_and_columns_on(
            self, left_df, right_df, on, how):

        # Construct expected result
        expected = self.compute_expected(left_df, right_df, on=on, how=how)

        # Perform merge
        result = left_df.merge(right_df, on=on, how=how)
        assert_frame_equal(result, expected, check_like=True)

    @pytest.mark.parametrize('left_on,right_on',
                             [(['outer'], ['outer']), (['inner'], ['inner']),
                              (['outer', 'inner'], ['outer', 'inner']),
                              (['inner', 'outer'], ['inner', 'outer'])])
    def test_merge_indexes_and_columns_lefton_righton(
            self, left_df, right_df, left_on, right_on, how):

        # Construct expected result
        expected = self.compute_expected(left_df, right_df,
                                         left_on=left_on,
                                         right_on=right_on,
                                         how=how)

        # Perform merge
        result = left_df.merge(right_df,
                               left_on=left_on, right_on=right_on, how=how)
        assert_frame_equal(result, expected, check_like=True)

    def test_merge_index_column_precedence(self):

        # Construct left_df with both an index and a column named 'outer'.
        # We make this 'outer' column equal to the 'inner' column so that we
        # can verify that the correct values are used by the merge operation
        left_df = self.df1.set_index('outer')
        left_df['outer'] = left_df['inner']

        # Construct right_df with an index level named 'outer'
        right_df = self.df2.set_index('outer')

        # Construct expected result.
        # The 'outer' column from left_df is chosen and the resulting
        # frame has no index levels
        expected = (left_df.reset_index(level='outer', drop=True)
                    .merge(right_df.reset_index(), on=['outer', 'inner']))

        # Merge left_df and right_df on 'outer' and 'inner'
        #  'outer' for left_df should refer to the 'outer' column, not the
        #  'outer' index level and a FutureWarning should be raised
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            result = left_df.merge(right_df, on=['outer', 'inner'])

        # Check results
        assert_frame_equal(result, expected)

        # Perform the same using the left_on and right_on parameters
        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            result = left_df.merge(right_df,
                                   left_on=['outer', 'inner'],
                                   right_on=['outer', 'inner'])

        assert_frame_equal(result, expected)
