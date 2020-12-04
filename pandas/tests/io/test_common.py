"""
Tests for the pandas.io.common functionalities
"""
import gzip
import http.server
from io import BytesIO, StringIO
import mmap
import os
from pathlib import Path
import threading

import pytest

from pandas.compat import is_platform_windows
import pandas.util._test_decorators as td

import pandas as pd
import pandas._testing as tm

import pandas.io.common as icom


class CustomFSPath:
    """For testing fspath on unknown objects"""

    def __init__(self, path):
        self.path = path

    def __fspath__(self):
        return self.path


# Functions that consume a string path and return a string or path-like object
path_types = [str, CustomFSPath, Path]

try:
    from py.path import local as LocalPath

    path_types.append(LocalPath)
except ImportError:
    pass

HERE = os.path.abspath(os.path.dirname(__file__))


# https://github.com/cython/cython/issues/1720
@pytest.mark.filterwarnings("ignore:can't resolve package:ImportWarning")
class TestCommonIOCapabilities:
    data1 = """index,A,B,C,D
foo,2,3,4,5
bar,7,8,9,10
baz,12,13,14,15
qux,12,13,14,15
foo2,12,13,14,15
bar2,12,13,14,15
"""

    def test_expand_user(self):
        filename = "~/sometest"
        expanded_name = icom._expand_user(filename)

        assert expanded_name != filename
        assert os.path.isabs(expanded_name)
        assert os.path.expanduser(filename) == expanded_name

    def test_expand_user_normal_path(self):
        filename = "/somefolder/sometest"
        expanded_name = icom._expand_user(filename)

        assert expanded_name == filename
        assert os.path.expanduser(filename) == expanded_name

    def test_stringify_path_pathlib(self):
        rel_path = icom.stringify_path(Path("."))
        assert rel_path == "."
        redundant_path = icom.stringify_path(Path("foo//bar"))
        assert redundant_path == os.path.join("foo", "bar")

    @td.skip_if_no("py.path")
    def test_stringify_path_localpath(self):
        path = os.path.join("foo", "bar")
        abs_path = os.path.abspath(path)
        lpath = LocalPath(path)
        assert icom.stringify_path(lpath) == abs_path

    def test_stringify_path_fspath(self):
        p = CustomFSPath("foo/bar.csv")
        result = icom.stringify_path(p)
        assert result == "foo/bar.csv"

    @pytest.mark.parametrize(
        "extension,expected",
        [
            ("", None),
            (".gz", "gzip"),
            (".bz2", "bz2"),
            (".zip", "zip"),
            (".xz", "xz"),
            (".GZ", "gzip"),
            (".BZ2", "bz2"),
            (".ZIP", "zip"),
            (".XZ", "xz"),
        ],
    )
    @pytest.mark.parametrize("path_type", path_types)
    def test_infer_compression_from_path(self, extension, expected, path_type):
        path = path_type("foo/bar.csv" + extension)
        compression = icom.infer_compression(path, compression="infer")
        assert compression == expected

    @pytest.mark.parametrize("path_type", [str, CustomFSPath, Path])
    def test_get_handle_with_path(self, path_type):
        # ignore LocalPath: it creates strange paths: /absolute/~/sometest
        filename = path_type("~/sometest")
        with icom.get_handle(filename, "w") as handles:
            assert os.path.isabs(handles.handle.name)
            assert os.path.expanduser(filename) == handles.handle.name

    def test_get_handle_with_buffer(self):
        input_buffer = StringIO()
        with icom.get_handle(input_buffer, "r") as handles:
            assert handles.handle == input_buffer
        assert not input_buffer.closed
        input_buffer.close()

    def test_iterator(self):
        reader = pd.read_csv(StringIO(self.data1), chunksize=1)
        result = pd.concat(reader, ignore_index=True)
        expected = pd.read_csv(StringIO(self.data1))
        tm.assert_frame_equal(result, expected)

        # GH12153
        it = pd.read_csv(StringIO(self.data1), chunksize=1)
        first = next(it)
        tm.assert_frame_equal(first, expected.iloc[[0]])
        tm.assert_frame_equal(pd.concat(it), expected.iloc[1:])

    @pytest.mark.parametrize(
        "reader, module, error_class, fn_ext",
        [
            (pd.read_csv, "os", FileNotFoundError, "csv"),
            (pd.read_fwf, "os", FileNotFoundError, "txt"),
            (pd.read_excel, "xlrd", FileNotFoundError, "xlsx"),
            (pd.read_feather, "pyarrow", IOError, "feather"),
            (pd.read_hdf, "tables", FileNotFoundError, "h5"),
            (pd.read_stata, "os", FileNotFoundError, "dta"),
            (pd.read_sas, "os", FileNotFoundError, "sas7bdat"),
            (pd.read_json, "os", ValueError, "json"),
            (pd.read_pickle, "os", FileNotFoundError, "pickle"),
        ],
    )
    def test_read_non_existent(self, reader, module, error_class, fn_ext):
        pytest.importorskip(module)

        path = os.path.join(HERE, "data", "does_not_exist." + fn_ext)
        msg1 = fr"File (b')?.+does_not_exist\.{fn_ext}'? does not exist"
        msg2 = fr"\[Errno 2\] No such file or directory: '.+does_not_exist\.{fn_ext}'"
        msg3 = "Expected object or value"
        msg4 = "path_or_buf needs to be a string file path or file-like"
        msg5 = (
            fr"\[Errno 2\] File .+does_not_exist\.{fn_ext} does not exist: "
            fr"'.+does_not_exist\.{fn_ext}'"
        )
        msg6 = fr"\[Errno 2\] 没有那个文件或目录: '.+does_not_exist\.{fn_ext}'"
        msg7 = (
            fr"\[Errno 2\] File o directory non esistente: '.+does_not_exist\.{fn_ext}'"
        )
        msg8 = fr"Failed to open local file.+does_not_exist\.{fn_ext}"

        with pytest.raises(
            error_class,
            match=fr"({msg1}|{msg2}|{msg3}|{msg4}|{msg5}|{msg6}|{msg7}|{msg8})",
        ):
            reader(path)

    @pytest.mark.parametrize(
        "reader, module, error_class, fn_ext",
        [
            (pd.read_csv, "os", FileNotFoundError, "csv"),
            (pd.read_table, "os", FileNotFoundError, "csv"),
            (pd.read_fwf, "os", FileNotFoundError, "txt"),
            (pd.read_excel, "xlrd", FileNotFoundError, "xlsx"),
            (pd.read_feather, "pyarrow", IOError, "feather"),
            (pd.read_hdf, "tables", FileNotFoundError, "h5"),
            (pd.read_stata, "os", FileNotFoundError, "dta"),
            (pd.read_sas, "os", FileNotFoundError, "sas7bdat"),
            (pd.read_json, "os", ValueError, "json"),
            (pd.read_pickle, "os", FileNotFoundError, "pickle"),
        ],
    )
    def test_read_expands_user_home_dir(
        self, reader, module, error_class, fn_ext, monkeypatch
    ):
        pytest.importorskip(module)

        path = os.path.join("~", "does_not_exist." + fn_ext)
        monkeypatch.setattr(icom, "_expand_user", lambda x: os.path.join("foo", x))

        msg1 = fr"File (b')?.+does_not_exist\.{fn_ext}'? does not exist"
        msg2 = fr"\[Errno 2\] No such file or directory: '.+does_not_exist\.{fn_ext}'"
        msg3 = "Unexpected character found when decoding 'false'"
        msg4 = "path_or_buf needs to be a string file path or file-like"
        msg5 = (
            fr"\[Errno 2\] File .+does_not_exist\.{fn_ext} does not exist: "
            fr"'.+does_not_exist\.{fn_ext}'"
        )
        msg6 = fr"\[Errno 2\] 没有那个文件或目录: '.+does_not_exist\.{fn_ext}'"
        msg7 = (
            fr"\[Errno 2\] File o directory non esistente: '.+does_not_exist\.{fn_ext}'"
        )
        msg8 = fr"Failed to open local file.+does_not_exist\.{fn_ext}"

        with pytest.raises(
            error_class,
            match=fr"({msg1}|{msg2}|{msg3}|{msg4}|{msg5}|{msg6}|{msg7}|{msg8})",
        ):
            reader(path)

    @pytest.mark.parametrize(
        "reader, module, path",
        [
            (pd.read_csv, "os", ("io", "data", "csv", "iris.csv")),
            (pd.read_table, "os", ("io", "data", "csv", "iris.csv")),
            (
                pd.read_fwf,
                "os",
                ("io", "data", "fixed_width", "fixed_width_format.txt"),
            ),
            (pd.read_excel, "xlrd", ("io", "data", "excel", "test1.xlsx")),
            (
                pd.read_feather,
                "pyarrow",
                ("io", "data", "feather", "feather-0_3_1.feather"),
            ),
            (
                pd.read_hdf,
                "tables",
                ("io", "data", "legacy_hdf", "datetimetz_object.h5"),
            ),
            (pd.read_stata, "os", ("io", "data", "stata", "stata10_115.dta")),
            (pd.read_sas, "os", ("io", "sas", "data", "test1.sas7bdat")),
            (pd.read_json, "os", ("io", "json", "data", "tsframe_v012.json")),
            (
                pd.read_pickle,
                "os",
                ("io", "data", "pickle", "categorical.0.25.0.pickle"),
            ),
        ],
    )
    def test_read_fspath_all(self, reader, module, path, datapath):
        pytest.importorskip(module)
        path = datapath(*path)

        mypath = CustomFSPath(path)
        result = reader(mypath)
        expected = reader(path)

        if path.endswith(".pickle"):
            # categorical
            tm.assert_categorical_equal(result, expected)
        else:
            tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "writer_name, writer_kwargs, module",
        [
            ("to_csv", {}, "os"),
            ("to_excel", {"engine": "xlwt"}, "xlwt"),
            ("to_feather", {}, "pyarrow"),
            ("to_html", {}, "os"),
            ("to_json", {}, "os"),
            ("to_latex", {}, "os"),
            ("to_pickle", {}, "os"),
            ("to_stata", {"time_stamp": pd.to_datetime("2019-01-01 00:00")}, "os"),
        ],
    )
    def test_write_fspath_all(self, writer_name, writer_kwargs, module):
        p1 = tm.ensure_clean("string")
        p2 = tm.ensure_clean("fspath")
        df = pd.DataFrame({"A": [1, 2]})

        with p1 as string, p2 as fspath:
            pytest.importorskip(module)
            mypath = CustomFSPath(fspath)
            writer = getattr(df, writer_name)

            writer(string, **writer_kwargs)
            with open(string, "rb") as f:
                expected = f.read()

            writer(mypath, **writer_kwargs)
            with open(fspath, "rb") as f:
                result = f.read()

            assert result == expected

    def test_write_fspath_hdf5(self):
        # Same test as write_fspath_all, except HDF5 files aren't
        # necessarily byte-for-byte identical for a given dataframe, so we'll
        # have to read and compare equality
        pytest.importorskip("tables")

        df = pd.DataFrame({"A": [1, 2]})
        p1 = tm.ensure_clean("string")
        p2 = tm.ensure_clean("fspath")

        with p1 as string, p2 as fspath:
            mypath = CustomFSPath(fspath)
            df.to_hdf(mypath, key="bar")
            df.to_hdf(string, key="bar")

            result = pd.read_hdf(fspath, key="bar")
            expected = pd.read_hdf(string, key="bar")

        tm.assert_frame_equal(result, expected)


@pytest.fixture
def mmap_file(datapath):
    return datapath("io", "data", "csv", "test_mmap.csv")


class TestMMapWrapper:
    def test_constructor_bad_file(self, mmap_file):
        non_file = StringIO("I am not a file")
        non_file.fileno = lambda: -1

        # the error raised is different on Windows
        if is_platform_windows():
            msg = "The parameter is incorrect"
            err = OSError
        else:
            msg = "[Errno 22]"
            err = mmap.error

        with pytest.raises(err, match=msg):
            icom._MMapWrapper(non_file)

        target = open(mmap_file)
        target.close()

        msg = "I/O operation on closed file"
        with pytest.raises(ValueError, match=msg):
            icom._MMapWrapper(target)

    def test_get_attr(self, mmap_file):
        with open(mmap_file) as target:
            wrapper = icom._MMapWrapper(target)

        attrs = dir(wrapper.mmap)
        attrs = [attr for attr in attrs if not attr.startswith("__")]
        attrs.append("__next__")

        for attr in attrs:
            assert hasattr(wrapper, attr)

        assert not hasattr(wrapper, "foo")

    def test_next(self, mmap_file):
        with open(mmap_file) as target:
            wrapper = icom._MMapWrapper(target)
            lines = target.readlines()

        for line in lines:
            next_line = next(wrapper)
            assert next_line.strip() == line.strip()

        with pytest.raises(StopIteration, match=r"^$"):
            next(wrapper)

    def test_unknown_engine(self):
        with tm.ensure_clean() as path:
            df = tm.makeDataFrame()
            df.to_csv(path)
            with pytest.raises(ValueError, match="Unknown engine"):
                pd.read_csv(path, engine="pyt")

    def test_binary_mode(self):
        """
        'encoding' shouldn't be passed to 'open' in binary mode.

        GH 35058
        """
        with tm.ensure_clean() as path:
            df = tm.makeDataFrame()
            df.to_csv(path, mode="w+b")
            tm.assert_frame_equal(df, pd.read_csv(path, index_col=0))

    @pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
    @pytest.mark.parametrize("compression_", ["bz2", "xz"])
    def test_warning_missing_utf_bom(self, encoding, compression_):
        """
        bz2 and xz do not write the byte order mark (BOM) for utf-16/32.

        https://stackoverflow.com/questions/55171439

        GH 35681
        """
        df = tm.makeDataFrame()
        with tm.ensure_clean() as path:
            with tm.assert_produces_warning(UnicodeWarning):
                df.to_csv(path, compression=compression_, encoding=encoding)

            # reading should fail (otherwise we wouldn't need the warning)
            with pytest.raises(Exception):
                pd.read_csv(path, compression=compression_, encoding=encoding)


def test_is_fsspec_url():
    assert icom.is_fsspec_url("gcs://pandas/somethingelse.com")
    assert icom.is_fsspec_url("gs://pandas/somethingelse.com")
    # the following is the only remote URL that is handled without fsspec
    assert not icom.is_fsspec_url("http://pandas/somethingelse.com")
    assert not icom.is_fsspec_url("random:pandas/somethingelse.com")
    assert not icom.is_fsspec_url("/local/path")
    assert not icom.is_fsspec_url("relative/local/path")


class BaseUserAgentResponder(http.server.BaseHTTPRequestHandler):
    """
    Base class for setting up a server that can be set up to respond
    with a particular file format with accompanying content-type headers
    """

    def start_processing_headers(self):
        """
        shared logic at the start of a GET request
        """
        self.send_response(200)
        self.requested_from_user_agent = self.headers["User-Agent"]
        response_df = pd.DataFrame(
            {
                "header": [self.requested_from_user_agent],
            }
        )
        return response_df

    def gzip_bytes(self, response_bytes):
        """
        some web servers will send back gzipped files to save bandwidth
        """
        bio = BytesIO()
        zipper = gzip.GzipFile(fileobj=bio, mode="w")
        zipper.write(response_bytes)
        zipper.close()
        response_bytes = bio.getvalue()
        return response_bytes

    def write_back_bytes(self, response_bytes):
        """
        shared logic at the end of a GET request
        """
        self.wfile.write(response_bytes)


class CSVUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()

        self.send_header("Content-Type", "text/csv")
        self.end_headers()

        response_bytes = response_df.to_csv(index=False).encode("utf-8")
        self.write_back_bytes(response_bytes)


class GzippedCSVUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Encoding", "gzip")
        self.end_headers()

        response_bytes = response_df.to_csv(index=False).encode("utf-8")
        response_bytes = self.gzip_bytes(response_bytes)

        self.write_back_bytes(response_bytes)


class JSONUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response_bytes = response_df.to_json().encode("utf-8")

        self.write_back_bytes(response_bytes)


class GzippedJSONUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Encoding", "gzip")
        self.end_headers()

        response_bytes = response_df.to_json().encode("utf-8")
        response_bytes = self.gzip_bytes(response_bytes)

        self.write_back_bytes(response_bytes)


class ParquetPyArrowUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()

        response_bytes = response_df.to_parquet(index=False, engine="pyarrow")

        self.write_back_bytes(response_bytes)


class ParquetFastParquetUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()

        # the fastparquet engine doesn't like to write to a buffer
        # it can do it via the open_with function being set appropriately
        # however it automatically calls the close method and wipes the buffer
        # so just overwrite that attribute on this instance to not do that
        def dummy_close():
            pass

        bio = BytesIO()
        bio.close = dummy_close
        response_df.to_parquet(
            "none", index=False, engine="fastparquet", open_with=lambda x, y: bio
        )
        response_bytes = bio.getvalue()

        self.write_back_bytes(response_bytes)


class PickleUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()

        bio = BytesIO()
        response_df.to_pickle(bio)
        response_bytes = bio.getvalue()

        self.write_back_bytes(response_bytes)


class StataUserAgentResponder(BaseUserAgentResponder):
    def do_GET(self):
        response_df = self.start_processing_headers()
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()

        bio = BytesIO()
        response_df.to_stata(bio, write_index=False)
        response_bytes = bio.getvalue()

        self.write_back_bytes(response_bytes)


class AllHeaderCSVResponder(http.server.BaseHTTPRequestHandler):
    """
    Send all request headers back for checking round trip
    """

    def do_GET(self):
        response_df = pd.DataFrame(self.headers.items())
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.end_headers()
        response_bytes = response_df.to_csv(index=False).encode("utf-8")
        self.wfile.write(response_bytes)


@pytest.mark.parametrize(
    "responder, read_method, port, parquet_engine",
    [
        (CSVUserAgentResponder, pd.read_csv, 34259, None),
        (JSONUserAgentResponder, pd.read_json, 34260, None),
        (ParquetPyArrowUserAgentResponder, pd.read_parquet, 34268, "pyarrow"),
        (ParquetFastParquetUserAgentResponder, pd.read_parquet, 34273, "fastparquet"),
        (PickleUserAgentResponder, pd.read_pickle, 34271, None),
        (StataUserAgentResponder, pd.read_stata, 34272, None),
        (GzippedCSVUserAgentResponder, pd.read_csv, 34261, None),
        (GzippedJSONUserAgentResponder, pd.read_json, 34262, None),
    ],
)
def test_server_and_default_headers(responder, read_method, port, parquet_engine):
    if read_method is pd.read_parquet:
        pytest.importorskip(parquet_engine)
    server = http.server.HTTPServer(("localhost", port), responder)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    try:
        if parquet_engine is None:
            df_http = read_method(f"http://localhost:{port}")
        else:
            df_http = read_method(f"http://localhost:{port}", engine=parquet_engine)
        server.shutdown()
    except Exception:
        df_http = pd.DataFrame({"header": []})
        server.shutdown()
    server.server_close()
    server_thread.join()
    assert not df_http.empty


@pytest.mark.parametrize(
    "responder, read_method, port, parquet_engine",
    [
        (CSVUserAgentResponder, pd.read_csv, 34263, None),
        (JSONUserAgentResponder, pd.read_json, 34264, None),
        (ParquetPyArrowUserAgentResponder, pd.read_parquet, 34270, "pyarrow"),
        (ParquetFastParquetUserAgentResponder, pd.read_parquet, 34275, "fastparquet"),
        (PickleUserAgentResponder, pd.read_pickle, 34273, None),
        (StataUserAgentResponder, pd.read_stata, 34274, None),
        (GzippedCSVUserAgentResponder, pd.read_csv, 34265, None),
        (GzippedJSONUserAgentResponder, pd.read_json, 34266, None),
    ],
)
def test_server_and_custom_headers(responder, read_method, port, parquet_engine):
    if read_method is pd.read_parquet:
        pytest.importorskip(parquet_engine)

    custom_user_agent = "Super Cool One"
    df_true = pd.DataFrame({"header": [custom_user_agent]})
    server = http.server.HTTPServer(("localhost", port), responder)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    try:
        if parquet_engine is None:
            df_http = read_method(
                f"http://localhost:{port}",
                storage_options={"User-Agent": custom_user_agent},
            )
        else:
            df_http = read_method(
                f"http://localhost:{port}",
                storage_options={"User-Agent": custom_user_agent},
                engine=parquet_engine,
            )
        server.shutdown()
    except Exception:
        df_http = pd.DataFrame({"header": []})
        server.shutdown()
    server.server_close()
    server_thread.join()

    tm.assert_frame_equal(df_true, df_http)


@pytest.mark.parametrize(
    "responder, read_method, port",
    [
        (AllHeaderCSVResponder, pd.read_csv, 34267),
    ],
)
def test_server_and_all_custom_headers(responder, read_method, port):
    custom_user_agent = "Super Cool One"
    custom_auth_token = "Super Secret One"
    storage_options = {
        "User-Agent": custom_user_agent,
        "Auth": custom_auth_token,
    }
    server = http.server.HTTPServer(("localhost", port), responder)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    try:
        df_http = read_method(
            f"http://localhost:{port}",
            storage_options=storage_options,
        )
        server.shutdown()
    except Exception:
        df_http = pd.DataFrame({"0": [], "1": []})
        server.shutdown()
    server.server_close()
    server_thread.join()
    df_http = df_http[df_http["0"].isin(storage_options.keys())]
    df_http = df_http.sort_values(["0"]).reset_index()
    df_http = df_http[["0", "1"]]
    keys = list(storage_options.keys())
    df_true = pd.DataFrame({"0": keys, "1": [storage_options[k] for k in keys]})
    df_true = df_true.sort_values(["0"])
    df_true = df_true.reset_index().drop(["index"], axis=1)
    tm.assert_frame_equal(df_true, df_http)


@pytest.mark.parametrize(
    "engine",
    [
        "pyarrow",
        "fastparquet",
    ],
)
def test_to_parquet_to_disk_with_storage_options(engine):
    headers = {
        "User-Agent": "custom",
        "Auth": "other_custom",
    }

    pytest.importorskip(engine)

    true_df = pd.DataFrame({"column_name": ["column_value"]})
    with pytest.raises(ValueError):
        true_df.to_parquet("/tmp/junk.parquet", storage_options=headers, engine=engine)
