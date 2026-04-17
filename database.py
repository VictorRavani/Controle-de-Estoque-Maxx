import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import io
import time
from dotenv import load_dotenv

# Garante que o .env seja lido
load_dotenv()

class postgresDatabase():
    def __init__(self, user=None, password=None, host=None, dbname=None, port=None):
        # 1. Configura as credenciais (Prioridade: .env > Padrão)
        self.user = user or os.getenv('DB_USER', 'postgres')
        self.password = password or os.getenv('DB_PASS', 'postgres')
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.dbname = dbname or os.getenv('DB_NAME', 'db_ARO')
        self.port = port or os.getenv('DB_PORT', '5432')
        
        self.lastError = None
        # Mantemos a connectionString para compatibilidade, mas o segredo está no conectar()
        self.connectionString = f"user={self.user} password={self.password} host={self.host} dbname={self.dbname} port={self.port}"

    def conectar(self):
        """A 'chave' mestra que abre o banco de dados"""
        try:
            conn = psycopg2.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                database=self.dbname,
                port=self.port
            )
            return conn
        except Exception as e:
            print(f"Erro crítico na conexão (Host: {self.host}): {e}")
            self.lastError = e
            return None

    def readRaw(self, sql, params=None, realdict=False):
        try:
            start_time = time.time()
            conn = self.conectar() # Usando a função centralizada
            if not conn: return []

            cur = conn.cursor(cursor_factory=RealDictCursor) if realdict else conn.cursor()
            
            cur.execute(sql, params) if params else cur.execute(sql)
            
            if realdict:
                data = cur.fetchall()
            else:
                data = [list(row) for row in cur.fetchall()]

            cur.close()
            conn.close()
            
            print(f"Consulta (READ) executada em: {time.time() - start_time:.2f}s")
            return data
        except Exception as e:
            self.lastError = e
            print("Erro em readRaw: ", e)
            return []

    def writeRaw(self, sql, params=None):
        try:
            start_time = time.time()
            conn = self.conectar() # Usando a função centralizada
            if not conn: return False

            cur = conn.cursor()
            cur.execute(sql, params) if params else cur.execute(sql)
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"Escrita (WRITE) executada em: {time.time() - start_time:.2f}s")
            return True
        except Exception as e:
            print('Erro em writeRaw:', e)
            self.lastError = e
            return False

    def bulkInsert(self, table, columns, data, custom_query=None):
        try:
            conn = self.conectar()
            if not conn: return False
            cur = conn.cursor()

            if custom_query:
                execute_values(cur, custom_query, data)
            else:
                placeholders = ", ".join(["%s"] * len(columns))
                sql = f"""
                    INSERT INTO {table} ({', '.join(columns)})
                    VALUES ({placeholders})
                    ON CONFLICT (codigo, nome_cliente) DO UPDATE SET
                    {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['codigo', 'nome_cliente']])};
                """
                execute_values(cur, sql, data)

            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print('Erro ao realizar bulk insert:', e)
            self.lastError = e
            return False

    def copyFrom(self, table, columns, data):
        try:
            conn = self.conectar()
            if not conn: return False
            cur = conn.cursor()

            buffer = io.StringIO()
            for row in data:
                buffer.write('\t'.join(map(str, row)) + '\n')
            buffer.seek(0)

            cur.copy_from(buffer, table, sep='\t', columns=columns)
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print('Erro ao usar COPY FROM:', e)
            self.lastError = e
            return False