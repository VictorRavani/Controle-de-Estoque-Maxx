import sys
sys.path.append(".")

from database import postgresDatabase

def zerar_tabela():
    print("Iniciando limpeza da tabela de produtos...")
    db = postgresDatabase()
    
    if not db.conectar():
        print("Erro: Não foi possível conectar ao banco de dados.")
        return

    # RESTART IDENTITY: Zera o contador da coluna ID de volta para 1
    # CASCADE: Limpa os registros dependentes (histórico/OPs) atrelados a esses produtos
    sucesso = db.writeRaw("TRUNCATE TABLE produtos RESTART IDENTITY CASCADE;")
    
    if sucesso:
        print("Tabela 'produtos' zerada com sucesso! O contador de IDs voltou para 1.")
    else:
        print("Falha ao zerar a tabela. Verifique os erros.")

if __name__ == '__main__':
    zerar_tabela()