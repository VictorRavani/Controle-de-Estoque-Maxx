import sys
sys.path.append(".") # Garante que o Python ache o database.py

from database import postgresDatabase

def importar_produtos():
    print("Iniciando importação de produtos...")
    
    db = postgresDatabase()
    if not db.conectar():
        print("Erro: Não foi possível conectar ao banco de dados.")
        return

    # 🔥 A TRAVA DE SEGURANÇA: Verifica se a tabela está vazia
    contagem = db.readRaw("SELECT COUNT(id) FROM produtos;")
    
    if contagem and contagem[0][0] > 0:
        quantidade_atual = contagem[0][0]
        print(f"-> Importação cancelada: O banco já possui {quantidade_atual} produtos cadastrados.")
        return

    # Lista completa de produtos extraída do seu Excel (Nome, Codigo)
    itens = [
        ("ACELERADOR DE SECAGEM 068 SECADO - 450ml", "7891452138945"),
        ("BATI PEDRA - BATIDA DE PEDRA 900ml", "7898031540441"),
        ("BOINA LA 6 PIRULITO CORTE PESADO LISTRA VERMELHA C/INTERFACE", "SEM CODIGO"),
        ("boina de espuma agressiva colmeia 6 polegadas", "7908216807525"),
        ("BOINA DE ESPUMA LOW COST 6 POLEGADAS - ETAPA DE CORTE  - ETAPA 1 - USO PARA POLITRIZ ROTATIVA", "7908249300949"),
        ("BOINA DE ESPUMA PRETA - DISCO PARA POLIMENTO LCD WAX 14mm ou 5/8 polegadas", "SEM CODIGO"),
        ("BOINA DUPLA FACE - BRANCA - BOINA CORTE - LANAPRO - MEDIDA 7 POLEGADAS  - POLITRIZ EOTATIVA - NIVEL DE CORTE TERMOFUSÃO", "7898132322007"),
        ("CATALIZADOR/ENDURECEDOR P/ PRIME OU PRETO FOSCO VINILICO", "7891452011774"),
        ("cera triple past wax autoamerica brilho e proteção", "7898403650143"),
        ("COLA TECK BOND ADESIVO INSTANTANEO - VISCOSIDADE MEDIA - 100g", "7898472250176"),
        ("CRISTALIZADOR DE VIDROS - LINHA LIMPEZA MAIS VISION", "8999069023957"),
        ("DESENGRAXANTE 900ml", "7898031544036"),
        ("DISCO DE CORTE FINO - AÇO INOX - 115x1,0x22,23mm", "7891345535684"),
        ("DISCO DE DESBASTE AÇO INOX - 115x5,0x22,23mm", "7891345003626"),
        ("DISCO FLAP DUPLO 115x22,23mm - aço inox - GRÃO 40", "7891792888456"),
        ("ESPUMA APLICADOR DE CERA", "7898939820751"),
        ("ESPUMA LIMPADORA - LIMPEZA A SECO 370g", "78999932759260"),
        ("ESTOPA 1 KG", "751320702296"),
        ("FAST CUT - COMPOSTO POLIDOR - CORTE BRILHO - AMARELO", "7908249308471"),
        ("FAST CUT - COMPOSTO POLIDOR - CORTE BRILHO - VERMELHO", "7908249308471"),
        ("FITA DUPLA FACE - FITA FORTE 09mmx20m", "7896193236554"),
        ("FITA FINA 18mm", "7896193250727"),
        ("FITA GROSSA 48mm", "7896193248649"),
        ("FLAP POLIDOR 115x22mm", "7898547051127"),
        ("GRAXA BRANCA 3K", "SEM CODIGO"),
        ("HOOKIT 1000", "SEM CODIGO"),
        ("HOOKIT 1200", "SEM CODIGO"),
        ("HOOKIT 150", "SEM CODIGO"),
        ("HOOKIT 220", "SEM CODIGO"),
        ("HOOKIT 320", "SEM CODIGO"),
        ("HOOKIT 40", "SEM CODIGO"),
        ("HOOKIT 400", "SEM CODIGO"),
        ("HOOKIT 600", "SEM CODIGO"),
        ("HOOKIT 80", "SEM CODIGO"),
        ("HOOKIT 800", "SEM CODIGO"),
        ("KPO - MAXIVED CAPÔ 400g C/ ENDURECEDOR", "SEM CODIGO"),
        ("LIXA 1200", "SEM CODIGO"),
        ("LIXA 150", "SEM CODIGO"),
        ("LIXA 1500", "SEM CODIGO"),
        ("LIXA 2000", "SEM CODIGO"),
        ("LIXA 220", "SEM CODIGO"),
        ("LIXA 3000", "SEM CODIGO"),
        ("LIXA 320", "SEM CODIGO"),
        ("LIXA 40", "SEM CODIGO"),
        ("LIXA 400", "SEM CODIGO"),
        ("LIXA 600", "SEM CODIGO"),
        ("LIXA 80", "SEM CODIGO"),
        ("LIXA 800", "SEM CODIGO"),
        ("MACARRON", "SEM CODIGO"),
        ("MASSA DE POLIR 1KG - CORTE 10", "7898403650556"),
        ("MASSA PARA PEQUENAS CORREÇÕES 200g bisnaga", "7891452103745"),
        ("MASSA POLIESTER 750g", "7891452194965"),
        ("MASSA ULTRA LIGHT/MASSA PLASTICA", "7898031540137"),
        ("PANO ESFREGÃO BRANCO", "SEM CODIGO"),
        ("PANO MICROFIBRA-40X60 AMARELA AUTO AMERICA", "SEM CODIGO"),
        ("PANO PEGA PÓ", "7893595186005"),
        ("PENEIRA PARA PINTURA", "SEM CODIGO"),
        ("PISTOLA DE METAL PARA APLICAÇÃO DE SILICONE / APLICADOR CALAFETAR ATLAS REFORCADO REF AT177 23CM ATLAS", "SEM CODIGO"),
        ("PRIME", "7891452860068"),
        ("PRIME CATALIZADOR/ENDURECEDOR", "7891452860075"),
        ("REMOVEDOR PASTOSO 1KG", "7898031541196"),
        ("REVITALIZADOR DE PLASTICOS EXTERNOS 400G", "7898511020883"),
        ("SILICONE PU - PARA VIDRO - ADESIVO", "SEM CODIGO"),
        ("SUPORTE BASE ORBITAL PARA LIXADEIRAS DR6-006A - SUPERFICIE VELCRO / ROSCA 5/16 POLEGADAS/ DENSIDADE MACIA", "SEM CODIGO"),
        ("SUPORTE PRATO SUPORTE 5 POLEGADAS / LIXADEIRA ROTO ORBITAL ELÉTRICA 3 PARAFUSOS", "7908276606144"),
        ("TACO MANUAL 205X70MM C/ PRESILHA PURPLEX", "SEM CODIGO"),
        ("TACO LIXADOR MANUAL 130mmx70mm - 1/4 folha de lixa", "7898142360044"),
        ("THINNER LIMPEZA - LATA 18L", "7901094100290"),
        ("THINNER PARA RETOQUE - 446 - 900ml", "7891452207290"),
        ("THINNER PU - LATA 5L", "7901094100139"),
        ("TINTA AZUL BISCAY", "SEM CODIGO"),
        ("TINTA AZUL BOREAL", "7891452012870"),
        ("TINTA AZUL NEUTRAL", "SEM CODIGO"),
        ("TINTA AZUL NORWAY", "SEM CODIGO"),
        ("TINTA AZUL QUASAR", "SEM CODIGO"),
        ("TINTA AZUL SEEKER", "SEM CODIGO"),
        ("TINTA BEGE ANGORA", "SEM CODIGO"),
        ("TINTA BRANCO ARTICO", "SEM CODIGO"),
        ("TINTA BRANCO ATLAS", "SEM CODIGO"),
        ("TINTA BRANCO ARTICO pu", "7899044725108"),
        ("TINTA BRANCO BANCHISA", "7891452222934"),
        ("TINTA BRANCO BANCHISA PU", "7891452229254"),
        ("TINTA BRANCO GLACIER", "7891452485155"),
        ("TINTA BRANCO GLACIER PU", "7891452433736"),
        ("TINTA BRANCO POLAR", "7891452417811"),
        ("TINTA BRANCO POLAR PU", "SEM CODIGO"),
        ("TINTA BRANCO PURO", "7891452441120"),
        ("TINTA BRANCO SUMMIT", "7891452424888"),
        ("TINTA BRANCO SUMMIT PU", "SEM CODIGO"),
        ("TINTA CATALIZADOR / ENDURECEDOR PARA TINTA PU 061 - BRASILLIAN", "SEM CODIGO"),
        ("TINTA CATALIZADOR / ENDURECEDOR PARA TINTA PU 061 - LAZZURIL", "7891452251453"),
        ("TINTA CINZA ACIER", "7891452296157"),
        ("TINTA CINZA ARTENSE / GRIS ARTENSE", "SEM CODIGO"),
        ("TINTA CINZA CLASSIC", "SEM CODIGO"),
        ("TINTA CINZA COPENHAGEN", "7891452854678"),
        ("TINTA CINZA DRAKE", "402020296"),
        ("TINTA CINZA GRAFITE", "7891452720393"),
        ("TINTA CINZA SANTIN STEEL", "7891452773337"),
        ("TINTA CINZA SCANDIUM", "7891452250784"),
        ("TINTA CINZA Silk", "7891452936305"),
        ("TINTA CINZA SILVERSTONE", "7891452936305"),
        ("TINTA CINZA URBANO", "7899049113547"),
        ("TINTA PLATINUM WHITE", "SEM CODIGO"),
        ("TINTA PRATA BILLET", "7891452461661"),
        ("TINTA PRATA BRISK", "7891452854876"),
        ("TINTA PRATA ETOILE", "7891452293637"),
        ("TINTA PRATA ICE", "SEM CODIGO"),
        ("TINTA PRATA ONIX", "7891452250814"),
        ("TINTA PRATA POLARIS", "7891452254201"),
        ("TINTA PRATA PYRIT", "SEM CODIGO"),
        ("TINTA PRATA SAND", "7891452497684"),
        ("TINTA PRATA SHARK", "7891452240587"),
        ("TINTA PRATA SIRIUS", "7891452333395"),
        ("TINTA PRATA SARGAS", "SEM CODIGO"),
        ("TINTA PRETO CARBON", "7899044758403"),
        ("TINTA PRETO EBONY", "7891452251835"),
        ("TINTA PRETO ECLIPSE PEROL", "7891452300953"),
        ("TINTA PRETO FOSCO VINILICO", "7891452011781"),
        ("TINTA PRETO INFINITO", "7891452499121"),
        ("TINTA PRETO NINJA", "7891452274032"),
        ("TINTA PRETO NOIR NACRE", "7891452251774"),
        ("TINTA PRETO ONIX", "7891452419747"),
        ("TINTA PRETO OURO NEGRO", "7899044758120"),
        ("TINTA PRETO PEROLA", "7891452340089"),
        ("TINTA PRETO VULCANO", "7899044766385"),
        ("TINTA VERMELHO ALPINE", "7891452251828"),
        ("TINTA VERMELHO ARPOADOR", "7891452333975"),
        ("TUBO DE COLA QUENTE GROSSO", "SEM CODIGO"),
        ("VASELINA INDUSTRIAL 440G", "7898092000021"),
        ("VASELINA SOLIDA 480G", "78977771500142"),
        ("VEDACHOQUE 145G", "SEM CODIGO"),
        ("VERNIZ", "7989810509071"),
        ("CELULOIDE APLICADOR DE MASSA PLASTICA", "SEM CODIGO"),
        ("SELADORA PARA PLASTICO", "SEM CODIGO"),
        ("FITA ISOLANTE PRETA", "SEM CODIGO"),
        ("silicone em spray", "SEM CODIGO"),
        ("COPO MEDIDOR DE VERNIZ", "SEM CODIGO")
    ]

    produtos_inseridos = 0
    produtos_ignorados = 0
    seq_interno = 1

    sql = """
        INSERT INTO public.produtos (nome, codigo, saldo, ativo, estoque_minimo)
        VALUES (%s, %s, 0, true, 0)
    """

    codigos_usados = set()
    for nome, codigo in itens:
        codigo_limpo = str(codigo).strip() if codigo else ""
        if not codigo_limpo or codigo_limpo.upper() in ("SEM CODIGO", "SEM CÓDIGO", "-") or codigo_limpo in codigos_usados:
            while f"INT-{seq_interno:05d}" in codigos_usados:
                seq_interno += 1
            codigo_limpo = f"INT-{seq_interno:05d}"
            seq_interno += 1
        codigos_usados.add(codigo_limpo)

        sucesso = db.writeRaw(sql, (nome.strip(), codigo_limpo))
        if sucesso:
            produtos_inseridos += 1
        else:
            produtos_ignorados += 1
            print(f"Erro ao inserir: {nome}")

    print(f"\nResumo da Importação:")
    print(f"Produtos inseridos com sucesso: {produtos_inseridos}")
    print(f"Produtos ignorados/com erro: {produtos_ignorados}")

if __name__ == '__main__':
    importar_produtos()