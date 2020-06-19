from io import BytesIO

import pytest

import pandas.util._test_decorators as td

from pandas import read_csv
import pandas._testing as tm

from pandas.io.common import is_s3_url


class TestS3URL:
    def test_is_s3_url(self):
        assert is_s3_url("s3://pandas/somethingelse.com")
        assert not is_s3_url("s4://pandas/somethingelse.com")


def test_streaming_s3_objects():
    # GH17135
    # botocore gained iteration support in 1.10.47, can now be used in read_*
    pytest.importorskip("botocore", minversion="1.10.47")
    from botocore.response import StreamingBody

    data = [b"foo,bar,baz\n1,2,3\n4,5,6\n", b"just,the,header\n"]
    for el in data:
        body = StreamingBody(BytesIO(el), content_length=len(el))
        read_csv(body)


@tm.network
@td.skip_if_no("s3fs")
def test_read_without_creds_from_pub_bucket():
    # GH 34626
    # Use Amazon Open Data Registry - https://registry.opendata.aws/gdelt
    result = read_csv("s3://gdelt-open-data/events/1981.csv", nrows=3)
    assert len(result) == 3
