import sys
sys.path.append("..") # Avisa o Python para procurar módulos na pasta anterior

import bcrypt
from database import postgresDatabase

db = postgresDatabase() 

usuario = "admin"
senha = "admin123"

senha_hash = bcrypt.hashpw(
    senha.encode(),
    bcrypt.gensalt()
).decode()

# remove admin antigo se existir
db.writeRaw(
    "DELETE FROM usuarios WHERE usuario = %s",
    (usuario,)
)

# cria admin novo
sql = """
INSERT INTO usuarios (usuario, senha, privilegio)
VALUES (%s, %s, %s)
"""

if db.writeRaw(sql, (usuario, senha_hash, 3)):
    print("Usuário admin resetado com sucesso!")
else:
    print("Falha ao resetar admin. Verifique os erros acima.")
