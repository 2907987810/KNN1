import io

import pytest

# the "as" is just so I won't have to change this in many places later.
import validate_string_concatenation as validate_unwanted_patterns


class TestBarePytestRaises:
    @pytest.mark.parametrize(
        "fd, expected",
        [
            (
                io.StringIO(
                    """
with pytest.raises(ValueError, match="foo"):
    pass
""".strip()
                ),
                [],
            ),
            (
                io.StringIO(
                    """
# with pytest.raises(ValueError, match="foo"):
#    pass
""".strip()
                ),
                [],
            ),
            (
                io.StringIO(
                    """
# with pytest.raises(ValueError):
#    pass
""".strip()
                ),
                [],
            ),
        ],
    )
    def test_good_pytest_raises(self, fd, expected):
        result = list(validate_unwanted_patterns.bare_pytest_raises(fd))
        assert result == expected

    @pytest.mark.parametrize(
        "fd, expected",
        [
            (
                io.StringIO(
                    """
    with pytest.raises(ValueError):
        pass
    """.strip()
                ),
                [
                    (
                        1,
                        (
                            "Bare pytests raise have been found. "
                            "Please pass in the argument 'match' "
                            "as well the exception."
                        ),
                    ),
                ],
            ),
            (
                io.StringIO(
                    """
    with pytest.raises(ValueError, match="foo"):
        with pytest.raises(ValueError):
            pass
        pass
    """.strip()
                ),
                [
                    (
                        2,
                        (
                            "Bare pytests raise have been found. "
                            "Please pass in the argument 'match' "
                            "as well the exception."
                        ),
                    ),
                ],
            ),
            (
                io.StringIO(
                    """
    with pytest.raises(ValueError):
        with pytest.raises(ValueError, match="foo"):
            pass
        pass
    """.strip()
                ),
                [
                    (
                        1,
                        (
                            "Bare pytests raise have been found. "
                            "Please pass in the argument 'match' "
                            "as well the exception."
                        ),
                    ),
                ],
            ),
        ],
    )
    def test_bad_pytest_raises(self, fd, expected):
        result = list(validate_unwanted_patterns.bare_pytest_raises(fd))
        assert result == expected


class TestStringsToConcatenate:
    @pytest.mark.parametrize(
        "fd, expected",
        [
            (
                io.StringIO('msg = ("bar " "baz")'),
                [
                    (
                        1,
                        (
                            "String unnecessarily split in two by black. "
                            "Please merge them manually."
                        ),
                    )
                ],
            ),
            (
                io.StringIO('msg = ("foo " "bar " "baz")'),
                [
                    (
                        1,
                        (
                            "String unnecessarily split in two by black. "
                            "Please merge them manually."
                        ),
                    ),
                    (
                        1,
                        (
                            "String unnecessarily split in two by black. "
                            "Please merge them manually."
                        ),
                    ),
                ],
            ),
        ],
    )
    def test_strings_to_concatenate(self, fd, expected):
        result = list(validate_unwanted_patterns.strings_to_concatenate(fd))
        assert result == expected


class TestStringsWithWrongPlacedWhitespace:
    @pytest.mark.parametrize(
        "fd, expected",
        [
            (
                io.StringIO(
                    """
msg = (
    "foo"
    " bar"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    )
                ],
            ),
            (
                io.StringIO(
                    """
msg = (
    f"foo"
    " bar"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    )
                ],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    f" bar"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    )
                ],
            ),
            (
                io.StringIO(
                    """
msg = (
    f"foo"
    f" bar"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    )
                ],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    rf" bar"
    " baz"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    ),
                    (
                        4,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    ),
                ],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    " bar"
    rf" baz"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    ),
                    (
                        4,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    ),
                ],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    rf" bar"
    rf" baz"
)
""".strip()
                ),
                [
                    (
                        3,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    ),
                    (
                        4,
                        (
                            "String has a space at the beginning instead "
                            "of the end of the previous string."
                        ),
                    ),
                ],
            ),
        ],
    )
    def test_strings_with_wrong_placed_whitespace(self, fd, expected):
        result = list(
            validate_unwanted_patterns.strings_with_wrong_placed_whitespace(fd)
        )
        assert result == expected

    @pytest.mark.parametrize(
        "fd, expected",
        [
            (
                io.StringIO(
                    """
msg = (
    "foo\n"
    " bar"
)
""".strip()
                ),
                [],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    "  bar"
    "baz"
)
""".strip()
                ),
                [],
            ),
            (
                io.StringIO(
                    """
msg = (
    f"foo"
    "  bar"
)
""".strip()
                ),
                [],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    f"  bar"
)
""".strip()
                ),
                [],
            ),
            (
                io.StringIO(
                    """
msg = (
    "foo"
    rf"  bar"
)
""".strip()
                ),
                [],
            ),
        ],
    )
    def test_excluded_strings_with_wrong_placed_whitespace(self, fd, expected):
        result = list(
            validate_unwanted_patterns.strings_with_wrong_placed_whitespace(fd)
        )
        assert result == expected
