import os
import sys
sys.path.append("..") # Avisa o Python para procurar módulos na pasta anterior
sys.path.append(".")

import bcrypt
from database import postgresDatabase

def garantir_admin_padrao(forcar_reset=False):
    db = postgresDatabase()
    if not db.conectar():
        print("Banco de dados indisponível no momento.")
        return False

    # Garante que a coluna de controle de primeiro acesso exista na tabela usuarios
    db.writeRaw("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precisa_trocar_senha BOOLEAN DEFAULT FALSE;")
    db.writeRaw("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS visibilidade BOOLEAN DEFAULT TRUE;")

    usuario = "admin"
    senha_padrao = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")

    existente = db.readRaw(
        "SELECT id, senha, precisa_trocar_senha FROM usuarios WHERE usuario = %s LIMIT 1;",
        (usuario,),
        realdict=True
    )

    if existente and not forcar_reset:
        # Se o admin já existe e ainda está usando a senha padrão, garante que a flag de troca esteja ativa
        try:
            if bcrypt.checkpw(senha_padrao.encode(), existente[0]['senha'].encode()):
                db.writeRaw(
                    "UPDATE usuarios SET precisa_trocar_senha = true, visibilidade = true, privilegio = 3 WHERE id = %s;",
                    (existente[0]['id'],)
                )
        except Exception:
            pass
        print("Usuário 'admin' já existe no banco de dados (preservado).")
        return True

    senha_hash = bcrypt.hashpw(
        senha_padrao.encode(),
        bcrypt.gensalt()
    ).decode()

    if existente and forcar_reset:
        sucesso = db.writeRaw(
            """
            UPDATE usuarios
            SET senha = %s, privilegio = 3, visibilidade = true, precisa_trocar_senha = true
            WHERE id = %s
            """,
            (senha_hash, existente[0]['id'])
        )
        print("Usuário 'admin' resetado com troca de senha obrigatória no próximo login!")
        return sucesso

    sql = """
    INSERT INTO usuarios (usuario, senha, privilegio, visibilidade, precisa_trocar_senha)
    VALUES (%s, %s, %s, true, true)
    """

    if db.writeRaw(sql, (usuario, senha_hash, 3)):
        print("Usuário 'admin' padrão criado com sucesso (troca de senha obrigatória no 1º login)!")
        return True
    else:
        print("Falha ao criar 'admin'. Verifique os erros acima.")
        return False

if __name__ == "__main__":
    reset = "--force-reset" in sys.argv
    garantir_admin_padrao(forcar_reset=reset)
