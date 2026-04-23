import Configuracores
from threading import Lock
from psycopg2 import pool, extras

class PostgresPool:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(PostgresPool, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            try:
                self.pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=Configuracores.maxPoolSize,
                    host=Configuracores.MariaDB_Host,
                    user=Configuracores.MariaDB_User,
                    password=Configuracores.MariaDB_Password,
                    database=Configuracores.MariaDB_Database,
                    port=5432 # Porta padrão Postgres
                )
                self._initialized = True
            except Exception as e:
                raise Exception(f"Erro ao criar pool de conexões Postgres: {e}")

    def _get_conn_cursor(self):
        conn = self.pool.getconn()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        return conn, cursor

    def _put_conn(self, conn, cursor):
        """Método interno para devolver a conexão ao pool com segurança"""
        if cursor:
            cursor.close()
        if conn:
            self.pool.putconn(conn)

    def select(self, query, params=None):
        conn, cursor = self._get_conn_cursor()
        try:
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            return result
        finally:
            self._put_conn(conn, cursor)

    def insert(self, query, params):
        conn, cursor = self._get_conn_cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            try:
                return cursor.fetchone() # Caso use RETURNING
            except:
                return cursor.rowcount
        finally:
            self._put_conn(conn, cursor)

    def update(self, query, params):
        conn, cursor = self._get_conn_cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        finally:
            self._put_conn(conn, cursor)

    def delete(self, query, params):
        conn, cursor = self._get_conn_cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        finally:
            self._put_conn(conn, cursor)

    def call_procedure(self, proc_name, params=None):
        conn, cursor = self._get_conn_cursor()
        try:
            cursor.callproc(proc_name, params or ())
            return cursor.fetchall()
        finally:
            self._put_conn(conn, cursor)
    
    def begin_transaction(self):
        conn = self.pool.get_conn()
        conn.autocommit = False
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        return conn, cursor

    def insert_tx(self, cursor, query, params):
        cursor.execute(query, params)
        return cursor.rowcount
    
    def update_tx(self, cursor, query, params):
        cursor.execute(query, params)
        return cursor.rowcount
    
    def delete_tx(self, cursor, query, params):
        cursor.execute(query, params)
        return cursor.rowcount

    def commit(self, conn, cursor):
        conn.commit()
        self._put_conn(conn, cursor)

    def rollback(self, conn, cursor):
        conn.rollback()
        self._put_conn(conn, cursor)
        