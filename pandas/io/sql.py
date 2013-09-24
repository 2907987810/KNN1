"""
Collection of query wrappers / abstractions to both facilitate data
retrieval and to reduce dependency on DB-specific API.
"""
from __future__ import print_function
from datetime import datetime, date

from pandas.compat import range, lzip, map, zip, raise_with_traceback
import pandas.compat as compat
import numpy as np
import traceback

import sqlite3
import warnings

from pandas.core.datetools import format as date_format

from pandas.core.api import DataFrame, isnull
from pandas.io import sql_legacy
from pandas.core.base import PandasObject


class SQLAlchemyRequired(ImportError):
    pass


class LegacyMySQLConnection(Exception):
    pass


class DatabaseError(IOError):
    pass


def read_sql(sql, con=None, index_col=None, flavor=None, driver=None,
             username=None, password=None, host=None, port=None,
             database=None, coerce_float=True, params=None, engine=None):
    """
    Returns a DataFrame corresponding to the result set of the query
    string.

    Optionally provide an index_col parameter to use one of the
    columns as the index. Otherwise will be 0 to len(results) - 1.

    Parameters
    ----------
    sql: string
        SQL query to be executed
    con : Connection object, SQLAlchemy Engine object, a filepath string
        (sqlite only) or the string ':memory:' (sqlite only). Alternatively,
        specify a user, passwd, host, and db below.
    index_col: string, optional
        column name to use for the returned DataFrame object.
    flavor : string specifying the flavor of SQL to use
    driver : string specifying SQL driver (e.g., MySQLdb), optional
    username: username for database authentication
        only needed if a Connection, Engine, or filepath are not given
    password: password for database authentication
        only needed if a Connection, Engine, or filepath are not given
    host: host for database connection
        only needed if a Connection, Engine, or filepath are not given
    database: database name
        only needed if a Connection, Engine, or filepath are not given
    coerce_float : boolean, default True
        Attempt to convert values to non-string, non-numeric objects (like
        decimal.Decimal) to floating point, useful for SQL result sets
    params: list or tuple, optional
        List of parameters to pass to execute method.
    engine : SQLAlchemy engine, optional

    """
    if params is None:
        params = []

    # TODO make sure con is a con and not a cursor etc.

    pandas_sql = PandasSQL(con=con, engine=engine)
    return pandas_sql.read_sql(sql, index_col=index_col, params=params,
                               flavor=flavor, coerce_float=coerce_float)


def write_frame(frame, name, con=None, flavor='sqlite', if_exists='fail', engine=None, **kwargs):
    """
    Write records stored in a DataFrame to a SQL database.

    Parameters
    ----------
    frame: DataFrame
    name: name of SQL table
    con: an open SQL database connection object
    flavor: {'sqlite', 'mysql', 'oracle'}, default 'sqlite'
    if_exists: {'fail', 'replace', 'append'}, default 'fail'
        fail: If table exists, do nothing.
        replace: If table exists, drop it, recreate it, and insert data.
        append: If table exists, insert data. Create if does not exist.
    """
    pandas_sql = PandasSQL(con=con, engine=engine)
    pandas_sql.write_frame(frame, name, flavor=flavor, if_exists=if_exists, **kwargs)

# This is an awesome function
def _engine_read_table_name(table_name, engine, meta=None, index_col=None):
    '''Given a table name and SQLAlchemy engine, return a DataFrame.

    Parameters
    ----------
    table_name: name of SQL table in database
    engine: SQLAlchemy engine
    meta: SQLAlchemy meta, optional
    index_col: columns to set as index, optional

    '''
    table = PandasSQLWithEngine(engine=engine)._get_table(table_name)

    if table is not None:
        sql_select = table.select()
        return PandasSQLWithEngine(engine=engine).read_sql(sql_select, index_col=index_col)
    else:
        raise ValueError("Table %s not found with %s." % table_name, engine)

#------------------------------------------------------------------------------
# Helper connection functions

# TODO improve this API
def get_connection(con, dialect, driver, username, password,
                   host, port, database):
    if isinstance(con, basestring):
        try:
            import sqlalchemy
            return _alchemy_connect_sqlite(con)
        except:
            return sqlite3.connect(con)
    if isinstance(con, sqlite3.Connection):
        return con
    try:
        import MySQLdb
    except ImportError:
        # If we don't have MySQLdb, this can't be a MySQLdb connection.
        pass
    else:
        if isinstance(con, MySQLdb.connection):
            raise LegacyMySQLConnection
    # If we reach here, SQLAlchemy will be needed.
    try:
        import sqlalchemy
    except ImportError:
        raise SQLAlchemyRequired
    if isinstance(con, sqlalchemy.engine.Engine):
        return con.connect()
    if isinstance(con, sqlalchemy.engine.Connection):
        return con
    if con is None:
        url_params = (dialect, driver, username,
                      password, host, port, database)
        url = _build_engine_url(*url_params)
        engine = sqlalchemy.create_engine(url)
        return engine.connect()
    if hasattr(con, 'cursor') and callable(con.cursor):
        # This looks like some Connection object from a driver module.
        raise NotImplementedError(
            """To ensure robust support of varied SQL dialects, pandas
           only support database connections from SQLAlchemy. See
           documentation.""")
    else:
        raise ValueError(
            """con must be a string, a Connection to a sqlite Database,
           or a SQLAlchemy Connection or Engine object.""")


def _alchemy_connect_sqlite(path):
    if path == ':memory:':
        return create_engine('sqlite://').connect()
    else:
        return create_engine('sqlite:///%s' % path).connect()


# I don't think this is used...
def sequence2dict(seq):
    """Helper function for cx_Oracle.

    For each element in the sequence, creates a dictionary item equal
    to the element and keyed by the position of the item in the list.
    >>> sequence2dict(("Matt", 1))
    {'1': 'Matt', '2': 1}

    Source:
    http://www.gingerandjohn.com/archives/2004/02/26/cx_oracle-executemany-example/
    """
    d = {}
    for k, v in zip(range(1, 1 + len(seq)), seq):
        d[str(k)] = v
    return d

# # legacy names
# get_schema = PandasSQL._create_schema
frame_query = read_sql
read_frame = read_sql

import abc

@add_metaclass(abc.ABCMeta)
class BackendBase(object):
    # NEED TO DEFINE:
    # schema_format (format string)
    # table_query_format (format string)
    # sqltypes (dict)
    # _cur_write(frame, table, names, cur)
    # flavor

    @abc.abstractmethod
    def _cur_write(frame, table, names, cur):
        "cursor write method"
        pass

    @abc.abstractproperty
    def flavor(self):
        "name of backend"
        return 'generic'

    @abc.abstractproperty
    def sqltype(self):
        "dict of types to convert"
        raise NotImplementedError("No sqltype mapping for flavor %s."
                                  % self.flavor)
    @abc.abstractproperty
    def schema_format(self):
        "template for create table schema"
        # better than attribute error.
        raise ValueError("Don't have a template for flavor %s." % self.flavor)

    @abc.abstractproperty
    def table_query_format(self):
        "format string for table info query"
        raise NotImplementedError("No table query for flavor %s."
                                  % self.flavor)

    def execute(self, sql, retry=False, params=None):
        try:
            # don't need to check for params here, execute should do it
            # instead.
            self.cur.execute(sql, params)
        except Exception as e:
            msg = "Execution failed with sql: %s\nError: %s" % (sql, e)
            if retry:
                warnings.warn(msg, DatabaseError)
                self.cur.execute(sql, params)
            else:
                raise_with_traceback(DatabaseError(msg))
        return self.cur

    def tquery(self, sql, retry=True, params=None, con=None):
        if params is None:
            params = []

        cur = self.execute(sql, retry=retry, params=params)
        result = self._safe_fetch(self.cur)

        #### I believe this part is unnecessary
        # try:
        #     # TODO: Why would this raise????
        #     cur.close()
        # except Exception as e:
        #     excName = e.__class__.__name__
        #     if excName == 'OperationalError':  # pragma: no cover
        #         raise_with_traceback(ex)
        #     else:
        #         warnings.warn("Error: %s. Retrying..." % e, UserWarning)
        #         if retry:
        #             return self.tquery(sql, retry=False, params=params,
        #                                cur=cur)
        #         else:
        #             raise

        # This makes into tuples?
        if result and len(result[0]) == 1:
            # python 3 compat
            result = list(next(zip(*result)))
        # whaa?
        elif result is None:  # pragma: no cover
            result = []
        return result

    def _has_table(self, name):
        query = self.table_query_format % name
        return len(self.tquery(query)) > 0

    def uquery(self, sql, retry=True, params=None, con=None):
        """
        Does the same thing as tquery, but instead of returning results, it
        returns the number of rows affected.  Good for update queries.

        Needs to be wrapped in some kind of catch errors call.
        """
        if params is None:
            params = []

        cur = self.execute(sql, retry=retry, params=params)
        return cur.row_count

    def _create_table(self, frame, name, flavor, keys=None):
        # Elements that are always going to be the same between tables

        # Replace spaces in DataFrame column names with _.
        safe_columns = [s.replace( ' ', '_').strip()
                        for s in frame.dtypes.index]
        sqltypes = frame.dtypes.apply(self._get_sqltype)

        if len(sqltypes) != safe_columns:
            raise AssertionError("Columns and dtypes should be equal lengths")

        column_types = lzip(safe_columns, sqltypes)
        schema_format = self.schema_format
        columns = ',\n '.join(schema_format % x for x in column_types)
        self._generate_table_sql(keys, columns, name)

    def _generate_table_sql(self, keys, columns, name):
        # might make more sense to just incorporate this
        # into _create_table
        keystr = ''
        if keys is not None:
            if isinstance(keys, compat.string_types):
                keys = (keys,)
            keystr = ', PRIMARY KEY (%s)' % ','.join(keys)
        template = """CREATE TABLE %(name)s (
                      %(columns)s
                      %(keystr)s
                      );"""
        create_sql = template % {'name': name, 'columns': columns,
                                       'keystr': keystr}
        self.execute(create_sql)

    def _write(self, frame, name):
        # cur = con.cursor()
        # Replace spaces in DataFrame column names with _.
        safe_names = [s.replace(' ', '_').strip() for s in frame.columns]
        # individual function for each frame
        self._cur_write(frame, name, safe_names, self.cur)
        # TODO: put this close separately...
        self.cur.close()

    @classmethod
    def _create_schema(cls, frame, name, keys=None):
        "Return a CREATE TABLE statement to suit the contents of a DataFrame."

    @classmethod
    def _get_sqltype(cls, pytype, flavor):
        # have to do it in reverse order...that way maintains same thing
        if issubclass(pytype, np.bool_):
            return cls.sqltype['bool']
        elif pytype is datetime.date:
            return cls.sqltype['date']
        elif issubclass(pytype, np.datetime64) or pytype is datetime:
            # Caution: np.datetime64 is also a subclass of np.number.
            return cls.sqltype['datetime']
        elif issubclass(pytype, np.integer):
            return cls.sqltype['integer']
        elif issubclass(pytype, np.floating):
            return cls.sqltype['float']
        else:
            return cls.sqltype['default']

    @classmethod
    def _safe_fetch(cls, cur):
        '''ensures result of fetchall is a list'''
        try:
            result = cur.fetchall()
            if not isinstance(result, list):
                result = list(result)
            return result
        except Exception as e:  # pragma: no cover
            excName = e.__class__.__name__
            if excName == 'OperationalError':
                return []
            raise

    def read_sql(self, sql, index_col=None, coerce_float=True, params=None):
        # Note coerce_float ignored here...not sure why
        if params is None:
            params = []
        data, columns = self._get_data_and_columns(
            sql=sql, params=params, flavor=flavor)
        df = DataFrame.from_records(data, columns=columns)
        if index_col is not None:
            df.set_index(index_col, inplace=True)
        return df

    def write_frame(self, frame, name, con=None, flavor='sqlite',
                    if_exists='fail', engine=None, **kwargs):
        """
        Write records stored in a DataFrame to a SQL database.

        Parameters
        ----------
        frame: DataFrame
        name: name of SQL table
        con: an open SQL database connection object
        flavor: {'sqlite', 'mysql', 'oracle'}, default 'sqlite'
        if_exists: {'fail', 'replace', 'append'}, default 'fail'
            fail: If table exists, do nothing.
            replace: If table exists, drop it, recreate it, and insert data.
            append: If table exists, insert data. Create if does not exist.
        """
        kwargs = self._pop_dep_append_kwarg(kwargs)

        exists = self._has_table(name)
        if exists:
            if if_exists == 'fail':
                raise ValueError("Table '%s' already exists." % name)
            elif if_exists == 'replace':
                self._drop_table(name)
                # do I have to create too?
        else:
            self._create_table(
                frame, name, flavor)  # flavor is ignored with engine

        self._write(frame, name, flavor)

    # TODO: Remove this
    @classmethod
    def _pop_dep_append_kwarg(cls, kwargs):
        if 'append' in kwargs:
            from warnings import warn
            warn("append is deprecated, use if_exists='append'", FutureWarning)
            if kwargs.pop('append'):
                # should this be setdefault?
                kwargs['if_exists'] = 'append'
            else:
                # should this be setdefault?
                kwargs['if_exists'] = 'fail'
            return kwargs

    def write_frame(self, frame, name,
                    if_exists='fail', **kwargs):
        """
        Write records stored in a DataFrame to a SQL database.

        Parameters
        ----------
        frame: DataFrame
        name: name of SQL table
        con: an open SQL database connection object
        flavor: {'sqlite', 'mysql', 'oracle'}, default 'sqlite'
        if_exists: {'fail', 'replace', 'append'}, default 'fail'
            fail: If table exists, do nothing.
            replace: If table exists, drop it, recreate it, and insert data.
            append: If table exists, insert data. Create if does not exist.
        """
        kwargs['if_exists'] = if_exists
        kwargs = self._pop_dep_append_kwarg(kwargs)
        if_exists = kwargs['if_exists']
        exists = self._has_table(name)

        if exists:
            if if_exists == 'fail':
                raise ValueError("Table '%s' already exists." % name)
            elif if_exists == 'replace':
                # drop table and create a new one
                self._drop_table(name)
                exists = False
            elif if_exists == 'append':
                # just let it go - going to append at end anyways
                pass
            else:
                raise ValueError("Invalid `if_exists` option: %s" % if_exists)

        if not exists:
            self._create_table(frame, name)

        self._write(frame, name, flavor)

class SqliteBackend(BackendBase):
    table_query_format = ("SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='%s';")
    sqltype = {'default': 'VARCHAR (63)',
               'float': 'REAL',
               'integer': 'INTEGER',
               'datetime': 'TIMESTAMP',
               'date': 'TIMESTAMP',
               'bool': 'INTEGER',
               }
    flavor = 'sqlite'
    schema_format = '[%s] %s'

    def _cur_write(self, frame, table, names, cur):
        bracketed_names = ['[' + column + ']' for column in names]
        col_names = ','.join(bracketed_names)
        wildcards = ','.join(['?'] * len(names))
        insert_query = 'INSERT INTO %s (%s) VALUES (%s)' % (
            table, col_names, wildcards)
        # pandas types are badly handled if there is only 1 column ( Issue
        # #3628 )
        if len(frame.columns) != 1:
            data = [tuple(x) for x in frame.values]
        else:
            data = [tuple(x) for x in frame.values.tolist()]
        cur.executemany(insert_query, data)

class MySQLBackend(BackendBase):
    table_query_format = "SHOW TABLES LIKE '%s'"
    sqltype = {'default': 'VARCHAR(63)',
               'float': 'FLOAT',
               'integer': 'BIGINT',
               'datetime': 'DATETIME',
               'date': 'DATE',
               # slight change from previous - aliased to TINYINT in general,
               # there's a BIT dtype too, not sure what to do with that.
               'bool': 'BOOL'}
    flavor = 'mysql'
    schema_format = '`%s` %s'

    def _cur_write(frame, table, names, cur):
        bracketed_names = ['`' + column + '`' for column in names]
        col_names = ','.join(bracketed_names)
        wildcards = ','.join([r'%s'] * len(names))
        insert_query = "INSERT INTO %s (%s) VALUES (%s)" % (
            table, col_names, wildcards)
        # pandas types are badly handled if there is only 1 column ( Issue
        # #3628 )
        if len(frame.columns) != 1:
            data = [tuple(x) for x in frame.values]
        else:
            data = [tuple(x) for x in frame.values.tolist()]
        cur.executemany(insert_query, data)

class PostgresBackend(BackendBase):
    sqltype = {'postgres': 'text',
               'date': 'date',
               'bool': 'boolean',
               'datetime': 'timestamp',
               'integer': 'integer',
               'float': 'real'
               }
    flavor = 'postgres'
    schema_format = '%s %s'
    # TODO: Add
    # * _cur_write
    # * table_query_format
