import time
import datetime
import decimal
import sys
import asyncio
import pyhdbcli

if sys.version_info >= (3,):
    long = int
    buffer = memoryview
    unicode = str

#
# globals
#
apilevel = '2.0'
threadsafety = 1
paramstyle = ('qmark', 'named')
_dbapi_async_mode = False

Connection = pyhdbcli.Connection
LOB = pyhdbcli.LOB
ResultRow = pyhdbcli.ResultRow
connect = Connection
Cursor = pyhdbcli.Cursor

class AsyncLob(pyhdbcli.LOB):
    def __init__(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], pyhdbcli.LOB):
            # Wrap an existing LOB
            self._lob = args[0]
        else:
            # Create self as a new LOB
            super().__init__(*args, **kwargs)
            self._lob = None

    async def close(self, *args, **kwargs):
        def call_close():
            if self._lob == None:
                return super(AsyncLob, self).close(*args, **kwargs)
            return self._lob.close(*args, **kwargs)
        loop = asyncio.get_running_loop()
        #return await loop.run_in_executor(None, super().close, *args, **kwargs)
        return await loop.run_in_executor(None, call_close)

    async def find(self, *args, **kwargs):
        def call_find():
            if self._lob == None:
                return super(AsyncLob, self).find(*args, **kwargs)
            return self._lob.find(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_find)

    async def read(self, *args, **kwargs):
        def call_read():
            if self._lob == None:
                return super(AsyncLob, self).read(*args, **kwargs)
            return self._lob.read(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_read)

    async def write(self, *args, **kwargs):
        def call_write():
            if self._lob == None:
                return super(AsyncLob, self).write(*args, **kwargs)
            return self._lob.write(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_write)

    def __getattr__(self, name):
        if self._lob is None:
            return super(AsyncLob, self).__getattr__(name)
        return getattr(self._lob, name)

class AsyncCursor(pyhdbcli.Cursor):
    async def callproc(self, *args, **kwargs):
        def call_callproc():
            return super(AsyncCursor, self).callproc(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_callproc)

    async def close(self, *args, **kwargs):
        def call_close():
            return super(AsyncCursor, self).close(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_close)

    async def execute(self, *args, **kwargs):
        def call_execute():
            return super(AsyncCursor, self).execute(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_execute)

    async def executemany(self, *args, **kwargs):
        def call_executemany():
            return super(AsyncCursor, self).executemany(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_executemany)

    async def executemanyprepared(self, *args, **kwargs):
        def call_executemanyprepared():
            return super(AsyncCursor, self).executemanyprepared(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_executemanyprepared)

    async def executeprepared(self, *args, **kwargs):
        def call_executeprepared():
            return super(AsyncCursor, self).executeprepared(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_executeprepared)

    async def fetchall(self, *args, **kwargs):
        def call_fetchall():
            return super(AsyncCursor, self).fetchall(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_fetchall)

    async def fetchmany(self, *args, **kwargs):
        def call_fetchmany():
            return super(AsyncCursor, self).fetchmany(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_fetchmany)

    async def fetchone(self, *args, **kwargs):
        def call_fetchone():
            return super(AsyncCursor, self).fetchone(*args, **kwargs)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, call_fetchone)
        uselob = False
        if 'uselob' in kwargs:
            uselob = kwargs['uselob']
        elif len(args) > 0:
            uselob = bool(args[0])
        if uselob and result is not None:
            result = tuple(
                AsyncLob(val) if isinstance(val, pyhdbcli.LOB) else val
                for val in result
            )
        return result

    async def nextset(self, *args, **kwargs):
        def call_nextset():
            return super(AsyncCursor, self).nextset(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_nextset)

    async def prepare(self, *args, **kwargs):
        def call_prepare():
            return super(AsyncCursor, self).prepare(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_prepare)

    async def scroll(self, *args, **kwargs):
        def call_scroll():
            return super(AsyncCursor, self).scroll(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_scroll)

    async def __aenter__(self):
        return super(AsyncCursor, self).__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        def call_exit():
            return super(AsyncCursor, self).__exit__(exc_type, exc_val, exc_tb)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_exit)

class AsyncConnection(pyhdbcli.Connection):
    @classmethod
    async def create(cls, *args, **kwargs):
        def call_cls():
            return cls(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_cls)

    async def cancel(self, *args, **kwargs):
        def call_cancel():
            return super(AsyncConnection, self).cancel(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_cancel)

    async def close(self, *args, **kwargs):
        def call_close():
            return super(AsyncConnection, self).close(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_close)

    async def commit(self, *args, **kwargs):
        def call_commit():
            return super(AsyncConnection, self).commit(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_commit)

    async def rollback(self, *args, **kwargs):
        def call_rollback():
            return super(AsyncConnection, self).rollback(*args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, call_rollback)

    def cursor(self):
        return AsyncCursor(self)

async def async_connect(*args, **kwargs):
    """
    Asynchronously create and return an AsyncConnection instance.
    Usage: conn = await async_connect(...)
    """
    if sys.version_info < (3, 7):
        raise RuntimeError("async_connect requires Python 3.7 or newer.")
    return await AsyncConnection.create(*args, **kwargs)

def _get_connection_class():
    return AsyncConnection if _dbapi_async_mode else pyhdbcli.Connection

def _get_cursor_class():
    return AsyncCursor if _dbapi_async_mode else pyhdbcli.Cursor

def _get_lob_class():
    return AsyncLob if _dbapi_async_mode else pyhdbcli.LOB

def set_async_mode(enabled=True):
    global _dbapi_async_mode
    global Connection
    global LOB
    global connect
    global Cursor
    _dbapi_async_mode = bool(enabled)
    Connection = _get_connection_class()
    LOB = _get_lob_class()
    connect = async_connect if _dbapi_async_mode else pyhdbcli.Connection
    Cursor = _get_cursor_class()


#
# exceptions
#
from pyhdbcli import Warning
from pyhdbcli import Error
def __errorinit(self, *args):
    super(Error, self).__init__(*args)
    argc = len(args)
    if argc == 1:
        if isinstance(args[0], Error):
            self.errorcode = args[0].errorcode
            self.errortext = args[0].errortext
        elif isinstance(args[0], (str, unicode)):
            self.errorcode = 0
            self.errortext = args[0]
    elif argc >= 2 and isinstance(args[0], (int, long)) and isinstance(args[1], (str, unicode)):
        self.errorcode = args[0]
        self.errortext = args[1]
Error.__init__ = __errorinit
from pyhdbcli import DatabaseError
from pyhdbcli import OperationalError
from pyhdbcli import ProgrammingError
from pyhdbcli import IntegrityError
from pyhdbcli import InterfaceError
from pyhdbcli import InternalError
from pyhdbcli import DataError
from pyhdbcli import NotSupportedError
from pyhdbcli import ExecuteManyError
from pyhdbcli import ExecuteManyErrorEntry

#
# input conversions
#

def Date(year, month, day):
    return datetime.date(year, month, day)

def Time(hour, minute, second, millisecond = 0):
    return datetime.time(hour, minute, second, millisecond * 1000)

def Timestamp(year, month, day, hour, minute, second, millisecond = 0):
    return datetime.datetime(year, month, day, hour, minute, second, millisecond * 1000)

def DateFromTicks(ticks):
    localtime = time.localtime(ticks)
    year = localtime[0]
    month = localtime[1]
    day = localtime[2]
    return Date(year, month, day)

def TimeFromTicks(ticks):
    localtime = time.localtime(ticks)
    hour = localtime[3]
    minute = localtime[4]
    second = localtime[5]
    return Time(hour, minute, second)

def TimestampFromTicks(ticks):
    localtime = time.localtime(ticks)
    year = localtime[0]
    month = localtime[1]
    day = localtime[2]
    hour = localtime[3]
    minute = localtime[4]
    second = localtime[5]
    return Timestamp(year, month, day, hour, minute, second)

def Binary(data):
    return buffer(data)

#
# Decimal
#
Decimal = decimal.Decimal

#
# type objects
#
class _AbstractType:
    def __init__(self, name, typeobjects):
        self.name = name
        self.typeobjects = typeobjects

    def __str__(self):
        return self.name

    def __cmp__(self, other):
        if other in self.typeobjects:
            return 0
        else:
            return -1

    def __eq__(self, other):
        return (other in self.typeobjects)

    def __hash__(self):
        return hash(self.name)

NUMBER = _AbstractType('NUMBER', (int, long, float, complex))
DATETIME = _AbstractType('DATETIME', (type(datetime.time(0)), type(datetime.date(1,1,1)), type(datetime.datetime(1,1,1))))
STRING = str
BINARY = buffer
ROWID = int
