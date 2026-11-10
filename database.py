import os
import psycopg2
from psycopg2 import sql as pg_sql
from psycopg2.extras import RealDictCursor, execute_values
import io
import time
from dotenv import load_dotenv

# Garante que o .env seja lido
load_dotenv()

class postgresDatabase():
    def __init__(self, user=None, password=None, host=None, dbname=None, port=None):
        # 1. Configura as credenciais (Prioridade: .env DB_* > .env POSTGRES_* > Padrão)
        self.user = user or os.getenv('DB_USER') or os.getenv('POSTGRES_USER', 'postgres')
        self.password = password or os.getenv('DB_PASS') or os.getenv('POSTGRES_PASSWORD', 'postgres')
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.dbname = dbname or os.getenv('DB_NAME') or os.getenv('POSTGRES_DB', 'db_ARO')
        self.port = port or os.getenv('DB_PORT', '5432')
        
        self.lastError = None
        # Mantemos a connectionString sem expor senha em logs
        self.connectionString = f"user={self.user} host={self.host} dbname={self.dbname} port={self.port}"

    def conectar(self):
        """A 'chave' mestra que abre o banco de dados"""
        try:
            conn = psycopg2.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                database=self.dbname,
                port=self.port,
                connect_timeout=5
            )
            return conn
        except Exception as e:
            print(f"Erro crítico na conexão (Host: {self.host}): {e}")
            self.lastError = e
            return None

    def readRaw(self, sql, params=None, realdict=False):
        conn = None
        cur = None
        try:
            start_time = time.time()
            conn = self.conectar() # Usando a função centralizada
            if not conn:
                return []

            cur = conn.cursor(cursor_factory=RealDictCursor) if realdict else conn.cursor()
            
            if params is not None:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            
            if realdict:
                data = cur.fetchall()
            else:
                data = [list(row) for row in cur.fetchall()]

            print(f"Consulta (READ) executada em: {time.time() - start_time:.2f}s")
            return data
        except Exception as e:
            self.lastError = e
            print("Erro em readRaw: ", e)
            return []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def writeRaw(self, sql, params=None):
        conn = None
        cur = None
        try:
            start_time = time.time()
            conn = self.conectar() # Usando a função centralizada
            if not conn:
                return False

            cur = conn.cursor()
            if params is not None:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            
            conn.commit()
            print(f"Escrita (WRITE) executada em: {time.time() - start_time:.2f}s")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            print('Erro em writeRaw:', e)
            self.lastError = e
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def bulkInsert(self, table, columns, data, custom_query=None):
        conn = None
        cur = None
        try:
            conn = self.conectar()
            if not conn:
                return False
            cur = conn.cursor()

            if custom_query:
                execute_values(cur, custom_query, data)
            else:
                # Uso de pg_sql.Identifier para prevenir SQL Injection em identificadores
                cols_ident = pg_sql.SQL(', ').join(pg_sql.Identifier(c) for c in columns)
                update_cols = [c for c in columns if c not in ('codigo', 'nome_cliente')]
                update_assign = pg_sql.SQL(', ').join(
                    pg_sql.SQL("{} = EXCLUDED.{}").format(pg_sql.Identifier(c), pg_sql.Identifier(c))
                    for c in update_cols
                )
                query = pg_sql.SQL(
                    "INSERT INTO {} ({}) VALUES %s ON CONFLICT (codigo, nome_cliente) DO UPDATE SET {};"
                ).format(pg_sql.Identifier(table), cols_ident, update_assign)
                execute_values(cur, query.as_string(cur), data)

            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            print('Erro ao realizar bulk insert:', e)
            self.lastError = e
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def copyFrom(self, table, columns, data):
        conn = None
        cur = None
        try:
            conn = self.conectar()
            if not conn:
                return False
            cur = conn.cursor()

            buffer = io.StringIO()
            for row in data:
                sanitized = [str(cell).replace('\t', ' ').replace('\n', ' ').replace('\r', '') for cell in row]
                buffer.write('\t'.join(sanitized) + '\n')
            buffer.seek(0)

            cur.copy_from(buffer, table, sep='\t', columns=columns)
            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            print('Erro ao usar COPY FROM:', e)
            self.lastError = e
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
