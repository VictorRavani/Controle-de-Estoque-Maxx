# ==============================================================================
# 1. Bibliotecas Nativas (Built-ins)
# Já vêm no Python, não precisam ser instaladas. Leves e rápidas.
# ==============================================================================
import os                           # Permite que o Python interaja com o Sistema Operacional para ler variáveis de ambiente
import io                           # Para manipular arquivos na memória RAM (ex: gerar relatórios sem HD)
import csv                          # Para ler ou exportar dados em formato de planilha/texto
from datetime import datetime       # Para pegar a data atual e fazer cálculos simples
from functools import wraps         # Para criar "decoradores" (ex: checar se é Administrador)
from dotenv import load_dotenv      # Para carregar o arquivo .env

# ==============================================================================
# 2. Bibliotecas Externas (Third-party)
# Foram instaladas via requirements.txt (o motor do seu sistema)
# ==============================================================================
import bcrypt       # Criptografia pesada militar para guardar as senhas com segurança

# O esqueleto da aplicação Web e da API
from flask import (
    Flask,           # A classe principal que cria e inicializa o servidor web
    request,         # Para pegar dados que o frontend envia (ex: form, json)
    jsonify,         # Para enviar respostas formatadas em JSON para o frontend
    abort,           # Interrompe a execução da rota imediatamente e envia um código de erro HTTP para o navegador.
    make_response,   # É o "empacotador" de respostas. Normalmente, o Flask já faz isso sozinho, mas o make_response te dá controle total.
    redirect,        # Para redirecionar o usuário para outra tela (ex: após login)
    url_for,         # Para gerar URLs automáticas baseadas no nome da função
    render_template, # Para renderizar as suas páginas HTML na tela do navegador
    flash,            # Para enviar mensagens rápidas de aviso na tela (ex: "Senha incorreta")
    Response
)

# Ferramentas de segurança de acesso
from flask_login import (
    current_user,    # Para saber quem é o usuário logado agora (ex: current_user.nome)
    UserMixin,       # Fornece os métodos padrões exigidos pelo login (is_authenticated, etc)
    LoginManager,    # O gerente que administra o início e fim da sessão de login
    login_required,  # A trava de segurança para as rotas
    login_user,      # É o comando que efetivamente entrega o crachá ao usuário.
    logout_user      # Ele destrói o cookie de sessão e limpa os rastros de login do navegador.
)

# ==============================================================================
# 3. Módulos Locais
# Arquivos de código criados por você mesmo
# ==============================================================================
import database    # O seu arquivo database.py que guarda a lógica de conexão com o banco e as funções de leitura/escrita

# Carrega as configurações do arquivo .env para a memória
load_dotenv()

######################################################## INIT ########################################################
class User(UserMixin):
    pass

# Flask configuration
versao = '1.0.0'
app = Flask(__name__)

# Puxa a chave secreta do arquivo .env. 
# Se não achar (ex: no seu PC local), usa uma chave padrão para desenvolvimento.
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'chave-padrao-super-secreta-dev-123')

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)

# Database configuration
# Puxa o host do arquivo .env. Se não achar, usa 'localhost' para você testar no Windows.
db_host = os.getenv('DB_HOST', 'localhost')
databaseOBJ = database.postgresDatabase(host=db_host)

################################################## AUTHENTICATION ####################################################

@app.context_processor
def inject_now():
    """Injeta a data/hora atual em todos os templates HTML automaticamente"""
    return {'now': datetime.now()}

#Create class that extends default flask_login User Class
class User(UserMixin):
    def __init__(self):
        super(User, self).__init__()
        self.name = ''
        self.privileges = 1

@login_manager.user_loader
def load_user(userid):

    try:
        userid = int(userid)
    except:
        return None

    credentials = databaseOBJ.readRaw(
        """
        SELECT id, usuario, privilegio, setor
        FROM usuarios
        WHERE id = %s
        """,
        params=(userid,),
        realdict=True
    )

    if credentials:

        user = User()
        user.id = credentials[0]['id']
        user.usuario = credentials[0]['usuario']
        user.privileges = credentials[0]['privilegio']
        user.setor = credentials[0]['setor']

        return user

#Callback to manage unauthorized acess
@login_manager.unauthorized_handler
def unauth_handler():
    #Redirect to index when user try to access protected resources without an authentication
    return redirect(url_for('autenticacao'))

@app.route('/login', methods=['POST'])
def login():

    user = request.form.get('user')
    password = request.form.get('password')

    if not user or not password:
        return abort(400)

    credentials = databaseOBJ.readRaw(
        """
        SELECT id, usuario, privilegio, senha, setor
        FROM usuarios
        WHERE usuario = %s
        """,
        params=(user,),
        realdict=False
    )

    if credentials:

        senha_hash = credentials[0][3]

        if bcrypt.checkpw(password.encode(), senha_hash.encode()):

            usuario_logado = User()
            usuario_logado.id = credentials[0][0]
            usuario_logado.usuario = credentials[0][1]
            usuario_logado.privileges = credentials[0][2]
            usuario_logado.setor = credentials[0][4]

            login_user(usuario_logado)

            return jsonify({'Login': True})

    return make_response({'Login': False})

@app.route('/logout', methods=['GET'])
def logout():
    #Logout current user
    logout_user()
    return jsonify({'Login': True})

def privilege_required(level):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if not current_user.is_authenticated:
                return redirect(url_for('login'))

            if current_user.privileges < level:
                flash("Você não tem permissão para acessar esta página.")
                return redirect(url_for('monitoramento_OP'))

            return f(*args, **kwargs)

        return decorated_function
    return decorator
######################################################## CRUD RESOURCES ####################################################

@app.route('/usuarios', methods=['GET', 'DELETE', 'PUT', 'POST'])
@login_required
@privilege_required(3)
def usuarios():

    form = request.form

    # ==========================
    # GET - LISTAR USUÁRIOS
    # ==========================
    if request.method == 'GET':

        users = databaseOBJ.readRaw(
            """
            SELECT 
                usuarios.id,
                usuarios.usuario,
                usuarios.setor,
                usuarios.privilegio
            FROM usuarios
            WHERE usuarios.visibilidade = true
            ORDER BY usuarios.id DESC;
            """,
            realdict=True
        )

        return jsonify({'users': users})

    # ==========================
    # DELETE - EXCLUIR USUÁRIO (Soft Delete)
    # ==========================
    elif request.method == 'DELETE':

        userid = request.form.get('id')

        if not userid:
            abort(400)

        # trava para impedir auto exclusão
        if int(userid) == current_user.id:
            return jsonify({"deleted": False, "error": "auto_delete"})

        # Alterado de DELETE para UPDATE da coluna visibilidade
        databaseOBJ.writeRaw(
            "UPDATE usuarios SET visibilidade = false WHERE id = %s;",
            params=(userid,)
        )

        # Mantido o mesmo retorno para não quebrar a lógica do frontend
        return jsonify({"deleted": True})

    # ==========================
    # PUT - ATUALIZAR USUÁRIO
    # ==========================
    elif request.method == 'PUT':

        userid = form.get('id')
        userlogin = form.get('usuario')
        usersector = form.get('setor')
        userprivileges = form.get('privilegios')
        novaSenha = form.get('novaSenha')

        if not (userid and userlogin and userprivileges):
            return jsonify({
                "success": False,
                "error": "Dados obrigatórios não informados."
            })

        userprivileges = int(userprivileges)

        if userprivileges == 1 and not usersector:
            return jsonify({
                "success": False,
                "error": "Selecione um setor para o usuário."
            })

        if userprivileges != 1:
            usersector = None


        # 🔎 verifica se já existe outro usuário com o mesmo login
        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM usuarios
            WHERE usuario = %s
            AND id <> %s
        """, (userlogin, userid), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Já existe um usuário com este login."
            })


        try:

            # Se veio nova senha
            if novaSenha and novaSenha.strip() != '':

                # valida tamanho da senha
                if len(novaSenha) < 6:
                    return jsonify({
                        'success': False,
                        'error': 'Senha deve ter pelo menos 6 caracteres'
                    })

                senha_hash = bcrypt.hashpw(
                    novaSenha.encode(),
                    bcrypt.gensalt()
                ).decode()

                databaseOBJ.writeRaw(
                    """
                    UPDATE usuarios
                    SET usuario = %s,
                        setor = %s,
                        privilegio = %s,
                        senha = %s
                    WHERE id = %s
                    """,
                    params=(userlogin, usersector, userprivileges, senha_hash, userid)
                )

            else:

                databaseOBJ.writeRaw(
                    """
                    UPDATE usuarios
                    SET usuario = %s,
                        setor = %s,
                        privilegio = %s
                    WHERE id = %s
                    """,
                    params=(userlogin, usersector, userprivileges, userid)
                )

            return jsonify({
                "success": True
            })

        except Exception as e:

            print("Erro ao atualizar usuário:", e)

            return jsonify({
                "success": False,
                "error": "Erro ao atualizar usuário."
            })

    # ==========================
    # POST - CRIAR USUÁRIO
    # ==========================
    elif request.method == 'POST':

        userlogin = form.get('usuario')
        usersector = form.get('setor')
        userprivileges = form.get('privilegios')

        if not (userlogin and usersector and userprivileges):
            abort(400)

        if userprivileges == '1' and not usersector:
            abort(400)
        
        if userprivileges != '1':
            usersector = None

        senha_hash = bcrypt.hashpw(
            userlogin.lower().encode(),
            bcrypt.gensalt()
        ).decode()

        databaseOBJ.writeRaw(
            """
            INSERT INTO usuarios (usuario, setor, senha, privilegio)
            VALUES (%s, %s, %s, %s)
            """,
            params=(userlogin, usersector, senha_hash, userprivileges)
        )

        return make_response({'created': 1})

    else:
        abort(405)

@app.route('/buscar_ordens_finalizar')
@login_required
def buscar_ordens_finalizar():

    privilegio = current_user.privileges
    setor_usuario = current_user.setor

    MAPA_PROCESSOS = {
        "materia_prima": 1,
        "estamparia": 2,
        "solda": 3,
        "retifica": 4,
        "envio_terceiros": 5,
        "recebimento_terceiros": 6,
        "inspecao_final": 7,
        "expedicao": 8
    }

    sql = """
        SELECT o.numero_op
        FROM ordem_de_producao o
        WHERE o.status_id = 2
    """

    params = []

    # operador só vê o setor dele
    if privilegio == 1:

        id_processo = MAPA_PROCESSOS.get(setor_usuario.lower().strip())

        if not id_processo:
            return jsonify([])

        sql += """
            AND EXISTS (
                SELECT 1
                FROM producao p
                WHERE p.id_ordem_de_producao = o.id
                AND p.id_processo = %s
            )
        """

        params.append(id_processo)

    sql += " ORDER BY o.numero_op DESC "

    ordens = databaseOBJ.readRaw(sql, tuple(params), realdict=True)

    return jsonify(ordens)

@app.route('/usuariodisponivel', methods=['GET'])
@login_required
def usuariodisponivel():
    # Não precisa de 'global databaseOBJ' se ele já foi definido no escopo global
    
    userlogin = request.args.get('usuario', '').strip()

    # Agora testamos a variável de verdade, não o texto 'userlogin'
    if userlogin: 
        # Usamos %s e passamos o parâmetro como uma tupla para evitar SQL Injection
        sql = "SELECT usuario FROM usuarios WHERE usuario = %s;"
        query = databaseOBJ.readRaw(sql, (userlogin,))
        
        # available: True se não achou ninguém (lista vazia)
        return jsonify({'available': len(query) == 0})
    else:
        # Se o campo veio vazio, retornamos um erro 400. 
        # NOTA: Garanta que 'abort' esteja no seu 'from flask import ...'
        return abort(400)

@app.route('/mudarsenha', methods=['GET','PUT'])
@login_required
def mudarsenha():
    global databaseOBJ
    form = request.form
    userid = current_user.get_id()
    currentPassword = form['currentPassword']
    newPassword = form['newPassword']

    if request.method == 'GET' or request.method == 'PUT':
        if currentPassword != None and newPassword != None:
            #Check if user typed right password
            password_query = databaseOBJ.readRaw("SELECT senha FROM usuarios WHERE id = %s;", (userid,))
            password = password_query[0][0]
            if bcrypt.checkpw(currentPassword.encode(), password.encode()):
                #Update user password
                newPassword = bcrypt.hashpw(newPassword.encode(), bcrypt.gensalt())
                print("Updating password from userid: " + userid)
                databaseOBJ.writeRaw(
                    "UPDATE usuarios SET senha = %s WHERE id = %s;", 
                    (newPassword.decode(), userid)
                )
                return make_response({'changeUserPassword': True})
            else:
                return make_response({'changeUserPassword': False})
        else:
            abort(400)
    else:
        abort(405)

###########################################################################################

@app.route('/adm/produtos')
@login_required
@privilege_required(2)
def adm_produtos():
    return render_template('adm_produtos.html')

@app.route('/produtos', methods=['GET', 'POST', 'PUT', 'DELETE'])
def produtos():

    # 🔎 LISTAR
    if request.method == 'GET':

        produtos = databaseOBJ.readRaw("""
            SELECT id, nome, codigo, saldo, estoque_minimo, ativo
            FROM produtos
            WHERE ativo = true
            ORDER BY nome
        """, realdict=True)

        return jsonify({"produtos": produtos})


    # ➕ ADICIONAR
    if request.method == 'POST':

        nome = request.values.get('nome')
        codigo = request.values.get('codigo')
        saldo = request.values.get('saldo')
        estoque_minimo = request.values.get('estoque_minimo')

        # Limpeza para evitar espaços acidentais antes ou depois
        nome = str(nome).strip()
        codigo = str(codigo).strip()

        # 🔥 REGRA: Verifica se já existe QUALQUER produto com esse mesmo código
        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM produtos
            WHERE ativo = true
            AND codigo = %s
            LIMIT 1
        """,(codigo,), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": f"Operação bloqueada! O código '{codigo}' já está em uso por outro produto."
            })

        # Se o código estiver livre, salva no banco com os campos novos!
        databaseOBJ.writeRaw("""
            INSERT INTO produtos (nome, codigo, saldo, estoque_minimo)
            VALUES (%s, %s, %s, %s)
        """, (nome, codigo, saldo, estoque_minimo))

        return jsonify({"success": True})


    # ✏️ EDITAR
    if request.method == 'PUT':

        id_produto = request.values.get('id')
        nome = request.values.get('nome')
        codigo = request.values.get('codigo')
        saldo = request.values.get('saldo')
        estoque_minimo = request.values.get('estoque_minimo')

        try:
            id_produto = int(id_produto)
            nome = str(nome).strip()
            codigo = str(codigo).strip()
        except Exception:
            return jsonify({"success": False, "error": "ID de produto inválido."})

        # 👇 MUDANÇA AQUI: Busca APENAS por código (removeu a checagem de nome)
        existe = databaseOBJ.readRaw("""
            SELECT nome, codigo
            FROM produtos
            WHERE ativo = true
            AND codigo = %s
            AND id <> %s
            LIMIT 1
        """,(codigo, id_produto), realdict=True)

        if existe:
            conflito = existe[0]
            # Ajustei a mensagem para focar no código
            mensagem_erro = f"Conflito! O código '{conflito['codigo']}' já está sendo usado pelo produto: {conflito['nome']}."
            
            return jsonify({
                "success": False,
                "error": mensagem_erro
            })

        # Se passou, atualiza normalmente
        databaseOBJ.writeRaw("""
            UPDATE produtos
            SET nome = %s,
                codigo = %s,
                saldo = %s,
                estoque_minimo = %s
            WHERE id = %s
        """, (nome, codigo, saldo, estoque_minimo, id_produto))

        return jsonify({"success": True})


    # 🗑 EXCLUIR (Agora atuando como Soft Delete / Inativar)
    if request.method == 'DELETE':

        id_produto = request.values.get('id')

        # Em vez de apagar do banco (DELETE FROM), nós apenas mudamos o status.
        # Assim o histórico na tabela de movimentações fica protegido!
        databaseOBJ.writeRaw("""
            UPDATE produtos 
            SET ativo = FALSE
            WHERE id = %s
        """, (id_produto,))

        return jsonify({"success": True})

@app.route('/registrar_movimentacao', methods=['POST'])
@login_required
def registrar_movimentacao():

    id_produto = request.form.get('id_produto')
    quantidade = request.form.get('quantidade')
    operacao = request.form.get('operacao') # 1 para saída, 0 para entrada

    # Certificando que são números para podermos fazer a conta
    try:
        qtd_solicitada = float(quantidade)
    except:
        return jsonify({"success": False, "error": "Quantidade inválida."})

    # 🔥 A TRAVA DE SEGURANÇA: Só fazemos isso se for uma SAÍDA (operacao 1)
    if operacao == '1' or operacao == 1:
        
        # 1. Consulta quanto de saldo o produto tem agora neste exato segundo
        produto = databaseOBJ.readRaw("""
            SELECT saldo, nome FROM produtos WHERE ativo = true AND id = %s
        """, (id_produto,), realdict=True)

        if not produto:
            return jsonify({"success": False, "error": "Produto não encontrado."})

        saldo_atual = float(produto[0]['saldo'])

        # 2. Se a pessoa pediu mais do que tem, nós bloqueamos a operação!
        if qtd_solicitada > saldo_atual:
            # Criamos uma variável só para a tela, convertendo para número Inteiro
            saldo_tela = int(saldo_atual)

            return jsonify({
                "success": False, 
                "error": f"Saldo insuficiente! O produto possui {saldo_tela} unidades no estoque."
            })

    # 1️⃣ Pega o ID do usuário logado (padrão do flask_login)
    id_usuario = current_user.id 

    # Validação básica de tipos
    try:
        id_produto = int(id_produto)
        quantidade = float(quantidade)
        operacao = int(operacao)
    except (TypeError, ValueError):
        return jsonify({
            "success": False, 
            "error": "Dados inválidos enviados pelo formulário."
        }), 400

    # 🔥 2️⃣ UPDATE e INSERT protegidos pelo seu databaseOBJ
    try:
        # Passo A: Inserir a movimentação no histórico
        databaseOBJ.writeRaw("""
            INSERT INTO movimentacoes_estoque (id_produto, operacao, quantidade, id_usuario)
            VALUES (%s, %s, %s, %s)
        """, (
            id_produto,
            operacao,
            quantidade,
            id_usuario
        ))

        # Passo B: Atualizar o saldo do produto de acordo com a operação
        if operacao == 1:
            # Operação 1 = SAÍDA (Subtrai do saldo)
            databaseOBJ.writeRaw("""
                UPDATE produtos
                SET saldo = saldo - %s
                WHERE id = %s
            """, (quantidade, id_produto))
            
        elif operacao == 0:
            # Operação 0 = ENTRADA (Soma no saldo)
            databaseOBJ.writeRaw("""
                UPDATE produtos
                SET saldo = saldo + %s
                WHERE id = %s
            """, (quantidade, id_produto))

    except Exception as e:
        print("Erro ao registrar movimentacao:", e)
        return jsonify({
            "success": False,
            "error": "Erro interno ao atualizar o estoque."
        }), 500

    return jsonify({"success": True})

@app.route('/adm/clientes')
@login_required
@privilege_required(2)
def adm_clientes():
    return render_template('adm_clientes.html')

@app.route('/clientes', methods=['GET', 'POST', 'PUT', 'DELETE'])
def clientes():

    # ==========================
    # GET - LISTAR CLIENTES
    # ==========================
    if request.method == 'GET':

        clientes = databaseOBJ.readRaw("""
            SELECT id, nome, codigo
            FROM clientes
            WHERE visibilidade = true
            ORDER BY nome
        """, realdict=True)

        return jsonify({"clientes": clientes})


    # ADICIONAR
    if request.method == 'POST':

        nome = request.form['nome']
        codigo = request.form['codigo']

        # 🔎 verifica se já existe
        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM clientes
            WHERE codigo = %s
        """, (codigo,), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Código já cadastrado."
            })

        databaseOBJ.writeRaw("""
            INSERT INTO clientes (nome, codigo)
            VALUES (%s, %s)
        """, (nome, codigo))

        return jsonify({"success": True})


    # EDITAR
    if request.method == 'PUT':

        id = request.form['id']
        nome = request.form['nome']
        codigo = request.form['codigo']

        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM clientes
            WHERE codigo = %s
            AND id <> %s
        """, (codigo, id), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Código já cadastrado."
            })

        databaseOBJ.writeRaw("""
            UPDATE clientes
            SET nome = %s,
                codigo = %s
            WHERE id = %s
        """, (nome, codigo, id))

        return jsonify({"success": True})


    # ==========================
    # DELETE - EXCLUIR CLIENTE (Soft Delete)
    # ==========================
    elif request.method == 'DELETE':

        # Utilizando .get() para evitar KeyError caso o campo não seja enviado
        id_cliente = request.form.get('id')

        if not id_cliente:
            return abort(400)

        # Alterado de DELETE para UPDATE da coluna visibilidade
        databaseOBJ.writeRaw("""
            UPDATE clientes
            SET visibilidade = false
            WHERE id = %s
        """, (id_cliente,))

        return jsonify({"success": True})

@app.route('/dados_producao/<processo>')
@login_required
def dados_producao(processo):

    params = []
    filtro = ""

    # Mapa fixo URL -> ID do processo
    MAPA_PROCESSOS = {
        "materia_prima": 1,
        "estamparia": 2,
        "solda": 3,
        "retifica": 4,
        "envio_terceiros": 5,
        "recebimento_terceiros": 6,
        "inspecao_final": 7,
        "expedicao": 8
    }

    if processo.lower() != "geral":

        id_processo = MAPA_PROCESSOS.get(processo.lower())

        if id_processo:
            filtro = " AND producao.id_processo = %s "
            params.append(id_processo)
        else:
            print("Processo inválido recebido na URL:", processo)

    sql = f"""
        SELECT 
            operador.nome as operador,
            operador.codigo as numero_chapa,
            clientes.nome as cliente,
            processos.nome as processo,
            producao.id_processo as operacao,  
            material.codigo as material,
            ordem_de_producao.numero_qualidade as numero_qualidade,
            tratamentos.nome as tratamento,
            ordem_de_producao.id_tratamento as id_tratamento,
            producao.qtde_produzida as quantidade_produzida,

            CASE 
                WHEN producao.status = 1 THEN 'Em operação'
                WHEN producao.status = 2 THEN 'Finalizado'
                ELSE 'Aguardando'
            END as status,

            ordem_de_producao.numero_op as numero_op,
            ordem_de_producao.quantidade as quantidade_total_ordem,
            produtos.nome as produto,
            produtos.codigo as codigo,

            TO_CHAR(producao.dt_inicio, 'DD/MM/YYYY HH24:MI') as iniciado_em,
            TO_CHAR(producao.dt_fim, 'DD/MM/YYYY HH24:MI') as finalizado_em,
            TO_CHAR(ordem_de_producao.data_entrega, 'DD/MM/YYYY') as data_entrega

        FROM producao

        INNER JOIN processos 
            ON producao.id_processo = processos.id

        LEFT JOIN operador
            ON producao.id_operador = operador.id

        INNER JOIN ordem_de_producao
            ON producao.id_ordem_de_producao = ordem_de_producao.id

        LEFT JOIN tratamentos 
            ON ordem_de_producao.id_tratamento = tratamentos.id

        LEFT JOIN clientes 
            ON ordem_de_producao.id_cliente = clientes.id

        LEFT JOIN material 
            ON ordem_de_producao.id_material = material.id

        LEFT JOIN produtos
            ON ordem_de_producao.id_produto = produtos.id

        WHERE producao.status = 1
        AND ordem_de_producao.status_id <> 4
        {filtro}

        ORDER BY producao.dt_inicio DESC
    """

    print("Processo recebido:", processo)
    print("Params:", params)
    print("SQL gerado:\n", sql)

    valores = databaseOBJ.readRaw(sql, params=tuple(params), realdict=True)

    return jsonify(valores)

@app.route('/dados_ordens', methods=['GET'])
def dados_ordens():

    # Unificamos tudo em uma única consulta 'valores'
    valores = databaseOBJ.readRaw("""
        SELECT
            op.id,
            op.numero_op,
            op.quantidade AS quantidade_total_ordem,
            
            -- 👇 ADICIONAMOS AS DUAS COLUNAS NOVAS AQUI 👇
            op.ultimo_processo,
            op.processo_atual,

            TO_CHAR(op.data_entrega, 'DD/MM/YYYY') AS data_entrega,
            TO_CHAR(op.data_entrega, 'YYYY-MM-DD') AS data_entrega_iso,
            op.numero_qualidade,
            op.id_tratamento,
            op.status_id,
            op.id_cliente,
            op.id_material,
            op.data_criacao AS data_criacao_real,
            TO_CHAR(op.data_criacao, 'YYYY-MM-DD HH24:MI:SS') AS data_criacao_iso,
            TO_CHAR(op.data_criacao, 'DD/MM/YYYY HH24:MI') AS data_criacao,
            op.id_produto as id_produto,

            p.nome AS produto,
            p.codigo AS codigo,
            c.nome AS cliente,
            m.codigo AS material,
            m.descricao AS material_descricao,
            s.nome AS status_ordem

        FROM ordem_de_producao op

        INNER JOIN produtos p ON op.id_produto = p.id
        INNER JOIN clientes c ON op.id_cliente = c.id
        INNER JOIN material m ON op.id_material = m.id
        LEFT JOIN status s ON op.status_id = s.id

        ORDER BY op.data_criacao DESC
    """, realdict=True)

    # Agora o 'valores' contém todas as informações necessárias para o DataTable
    return jsonify(valores)

######################################################## VIEWS ########################################################

@app.route('/autenticacao', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def autenticacao():

    print("AUTH:", current_user.is_authenticated)
    print("USER:", current_user)
    print("PRIV:", getattr(current_user, 'privileges', 'SEM privileges'))
    print("SETOR:", getattr(current_user, 'setor', 'SEM setor'))

    if current_user.is_authenticated:

        privilegio = current_user.privileges

        # Nível 1 → monitoramento do próprio setor
        if privilegio == 1:

            setor = current_user.setor

            if setor:
                return redirect(
                    url_for('monitoramento_OP', processo=setor)
                )
            else:
                # Se por algum motivo não tiver setor definido
                return redirect(
                    url_for('monitoramento_OP', processo='geral')
                )

        # Nível 2 (PCP) ou 3 (ADM) → visão geral
        elif privilegio in [2,3]:

            return redirect(
                url_for('monitoramento_OP', processo='geral')
            )

    return render_template('autenticacao.html')

@app.route('/dados_historico')
@login_required
def dados_historico():

    privilegio = current_user.privileges
    setor_usuario = current_user.setor

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    params = []
    filtros = []

    # filtro por data
    if data_inicio and data_fim:
        filtros.append("producao.dt_fim BETWEEN %s AND %s")
        params.append(data_inicio + " 00:00:00")
        params.append(data_fim + " 23:59:59")

    # 🔐 restrição por setor
    if privilegio == 1 and setor_usuario:

        MAPA_PROCESSOS = {
            "materia_prima": 1,
            "estamparia": 2,
            "solda": 3,
            "retifica": 4,
            "envio_terceiros": 5,
            "recebimento_terceiros": 6,
            "inspecao_final": 7,
            "expedicao": 8
        }
        setor_normalizado = setor_usuario.lower().strip()
        id_processo = MAPA_PROCESSOS.get(setor_usuario)

        if id_processo:
            filtros.append("producao.id_processo = %s")
            params.append(id_processo)
        else:
            abort(403)

    # monta where dinâmico
    filtro_sql = ""
    if filtros:
        filtro_sql = " AND " + " AND ".join(filtros)

    sql = f"""
        SELECT 
            operador.nome as operador,
            operador.codigo as numero_chapa,
            clientes.nome as cliente,
            processos.nome as processo,
            producao.id_processo as operacao,  
            material.codigo as material,
            ordem_de_producao.numero_qualidade as numero_qualidade,
            tratamentos.nome as tratamento,
            ordem_de_producao.id_tratamento as id_tratamento,
            producao.qtde_produzida as quantidade_produzida,
            operador_fim.nome AS operador_fim,
            operador_fim.codigo AS chapa_fim,

            CASE 
                WHEN producao.status = 1 THEN 'Em operação'
                WHEN producao.status = 2 THEN 'Finalizado'
                ELSE 'Aguardando'
            END as status,

            ordem_de_producao.numero_op as numero_op,
            ordem_de_producao.quantidade as quantidade_total_ordem,
            produtos.nome as produto,
            produtos.codigo as codigo,

            TO_CHAR(producao.dt_inicio, 'DD/MM/YYYY HH24:MI') as iniciado_em,
            TO_CHAR(producao.dt_fim, 'DD/MM/YYYY HH24:MI') as finalizado_em,
            TO_CHAR(ordem_de_producao.data_entrega, 'DD/MM/YYYY') as data_entrega

        FROM producao

        INNER JOIN ordem_de_producao 
            ON producao.id_ordem_de_producao = ordem_de_producao.id

        INNER JOIN produtos 
            ON ordem_de_producao.id_produto = produtos.id

        LEFT JOIN operador
            ON producao.id_operador = operador.id

        INNER JOIN processos 
            ON producao.id_processo = processos.id

        LEFT JOIN tratamentos 
            ON ordem_de_producao.id_tratamento = tratamentos.id

        LEFT JOIN clientes 
            ON ordem_de_producao.id_cliente = clientes.id

        LEFT JOIN material 
            ON ordem_de_producao.id_material = material.id

        LEFT JOIN operador operador_fim
            ON producao.id_operador_fim = operador_fim.id

        WHERE producao.status = 2
        {filtro_sql}

        ORDER BY producao.dt_fim DESC
    """

    valores = databaseOBJ.readRaw(sql, params=tuple(params), realdict=True)

    return jsonify(valores)

@app.route('/exportar_historico_csv')
@login_required
def exportar_csv():

    privilegio = current_user.privileges
    setor_usuario = current_user.setor

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    params = []
    filtros = []

    if data_inicio and data_fim:
        filtros.append("producao.dt_fim BETWEEN %s AND %s")
        params.append(data_inicio + " 00:00:00")
        params.append(data_fim + " 23:59:59")

    # filtro por setor
    if privilegio == 1 and setor_usuario:

        MAPA_PROCESSOS = {
            "materia_prima": 1,
            "estamparia": 2,
            "solda": 3,
            "retifica": 4,
            "envio_terceiros": 5,
            "recebimento_terceiros": 6,
            "inspecao_final": 7,
            "expedicao": 8
        }

        setor_normalizado = setor_usuario.lower().strip()
        id_processo = MAPA_PROCESSOS.get(setor_normalizado)

        if not id_processo:
            return abort(403)

        filtros.append("producao.id_processo = %s")
        params.append(id_processo)

    filtro_sql = ""
    if filtros:
        filtro_sql = " AND " + " AND ".join(filtros)

    sql = f"""
        SELECT 
            operador.nome as operador,
            operador.codigo as numero_chapa,
            clientes.nome as cliente,
            processos.nome as processo,
            producao.id_processo as operacao,
            material.codigo as material,
            ordem_de_producao.numero_qualidade as numero_qualidade,
            tratamentos.nome as tratamento,
            producao.qtde_produzida as quantidade_produzida,
            operador_fim.nome AS operador_fim,
            operador_fim.codigo AS chapa_fim,

            CASE 
                WHEN producao.status = 1 THEN 'Em operação'
                WHEN producao.status = 2 THEN 'Finalizado'
                ELSE 'Aguardando'
            END as status,

            ordem_de_producao.numero_op as numero_op,
            ordem_de_producao.quantidade as quantidade_total_ordem,
            produtos.nome as produto,
            produtos.codigo as codigo,

            TO_CHAR(producao.dt_inicio, 'DD/MM/YYYY HH24:MI') as iniciado_em,
            TO_CHAR(producao.dt_fim, 'DD/MM/YYYY HH24:MI') as finalizado_em,
            TO_CHAR(ordem_de_producao.data_entrega, 'DD/MM/YYYY') as data_entrega

        FROM producao

        INNER JOIN ordem_de_producao 
            ON producao.id_ordem_de_producao = ordem_de_producao.id

        INNER JOIN produtos 
            ON ordem_de_producao.id_produto = produtos.id

        LEFT JOIN operador
            ON producao.id_operador = operador.id

        INNER JOIN processos 
            ON producao.id_processo = processos.id

        LEFT JOIN tratamentos 
            ON ordem_de_producao.id_tratamento = tratamentos.id

        LEFT JOIN clientes 
            ON ordem_de_producao.id_cliente = clientes.id

        LEFT JOIN material 
            ON ordem_de_producao.id_material = material.id

        LEFT JOIN operador operador_fim
            ON producao.id_operador_fim = operador_fim.id

        WHERE producao.status = 2
        {filtro_sql}

        ORDER BY producao.dt_fim DESC
    """

    dados = databaseOBJ.readRaw(sql, params=tuple(params), realdict=True)

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=';')

    writer.writerow([
        "OP",
        "Denominacao",
        "Peca Numero",
        "Quantidade",
        "Cliente",
        "Entrega",
        "Material",
        "A.Q.",
        "Processo",
        "Status",
        "Chapa",
        "Iniciado",
        "Chapa Fim",
        "Finalizado",
        "Producao"
    ])

    for row in dados:
        writer.writerow([
            row["numero_op"],
            row["produto"],
            row["codigo"],
            row["quantidade_total_ordem"],
            row["cliente"],
            row["data_entrega"],
            row["material"],
            row["numero_qualidade"],
            row["processo"],
            row["status"],
            row["numero_chapa"],
            row["iniciado_em"],
            row["chapa_fim"] or "-",
            row["finalizado_em"],
            row["quantidade_produzida"] or 0
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=historico_producao.csv"
        }
    )

@app.route('/historico')
@login_required
def historico():
    return render_template('historico_producao.html')

@app.route('/cancelar_ordem', methods=['POST'])
@login_required
@privilege_required(2)
def cancelar_ordem():

    id_ordem = request.form.get('id')

    if not id_ordem:
        return jsonify({"success": False, "error": "Ordem inválida"}), 400

    databaseOBJ.writeRaw("""
        UPDATE ordem_de_producao
        SET status_id = 4
        WHERE id = %s
    """, (id_ordem,))

    return jsonify({"success": True})

@app.route('/ordens', methods=['PUT'])
@login_required
def atualizar_ordem():

    id = request.form.get('id')
    numero_op = request.form.get('numero_op')
    id_produto = request.form.get('id_produto')
    numero_qualidade = request.form.get('numero_qualidade')
    id_cliente = request.form.get('id_cliente')
    id_material = request.form.get('id_material')
    id_tratamento = request.form.get('id_tratamento')
    quantidade = request.form.get('quantidade')
    data_entrega = request.form.get('data_entrega')
    status_id = request.form.get('status_id')

    # 🔎 1️⃣ Buscar numero_op atual
    ordem_atual = databaseOBJ.readRaw("""
        SELECT numero_op
        FROM ordem_de_producao
        WHERE id = %s
    """, (id,), realdict=True)

    if not ordem_atual:
        return jsonify({
            "success": False,
            "error": "Ordem não encontrada."
        }), 404

    numero_op = str(numero_op)
    numero_op_atual = str(ordem_atual[0]["numero_op"])

    if numero_op != numero_op_atual:

        existe_numero = databaseOBJ.readRaw("""
            SELECT 1
            FROM ordem_de_producao
            WHERE numero_op = %s
            AND id <> %s
            LIMIT 1
        """, (numero_op, id), realdict=True)

        if existe_numero:
            return jsonify({
                "success": False,
                "error": "Já existe uma OP com esse número."
            }), 400

    # 🔥 3️⃣ UPDATE protegido
    try:
        databaseOBJ.writeRaw("""
            UPDATE ordem_de_producao
            SET numero_op = %s,
                id_produto = %s,
                numero_qualidade = %s,
                id_cliente = %s,
                id_material = %s,
                id_tratamento = %s,
                quantidade = %s,
                data_entrega = %s,
                status_id = %s
            WHERE id = %s
        """, (
            numero_op,
            id_produto,
            numero_qualidade,
            id_cliente,
            id_material,
            id_tratamento,
            quantidade,
            data_entrega,
            status_id,
            id
        ))

    except Exception as e:
        print("Erro:", e)
        return jsonify({
            "success": False,
            "error": "Já existe uma OP com esse número."
        }), 400

    return jsonify({"success": True})

@app.route('/produto_info')
def produto_info():

    id_produto = request.args.get('id_produto')

    produto = databaseOBJ.readRaw("""
        SELECT nome
        FROM produtos
        WHERE ativo = true
        AND id = %s
    """, (id_produto,), realdict=True)

    if produto:
        return jsonify({
            "success": True,
            "nome": produto[0]["nome"]
        })

    return jsonify({"success": False})

@app.route('/monitoramento_OP/<processo>')
@login_required
def monitoramento_OP(processo):

    MAPA_PROCESSOS = {
        "materia_prima": 1,
        "estamparia": 2,
        "solda": 3,
        "retifica": 4,
        "envio_terceiros": 5,
        "recebimento_terceiros": 6,
        "inspecao_final": 7,
        "expedicao": 8
    }

    # 🔎 Valida processo
    id_processo = MAPA_PROCESSOS.get(processo)

    if processo == "geral":
        id_processo = None
    else:
        id_processo = MAPA_PROCESSOS.get(processo)

        if not id_processo:
            abort(404)

    privilegio = int(current_user.privileges)
    setor_usuario = current_user.setor

    # 🔐 Usuário nível 1 só acessa o próprio setor
    if privilegio == 1 and processo != setor_usuario:
        abort(403)

    # 🔎 Nome amigável do processo
    nomes = {
        "materia_prima": "Matéria-Prima",
        "estamparia": "Estamparia",
        "solda": "Solda",
        "retifica": "Retífica",
        "envio_terceiros": "Envio para Terceiros",
        "recebimento_terceiros": "Recebimento (Terceiros)",
        "inspecao_final": "Inspeção Final",
        "expedicao": "Expedição",
        "geral": "Geral"
    }

    nome_processo = nomes.get(processo, "Processo desconhecido")

    # filtros de status
    filtro_finalizar = "o.status_id = 2"
    filtro_iniciar = "o.status_id IN (1,2)"

    # 🔎 Ordens disponíveis para ESTE setor
    if processo == "geral":

        ordens = databaseOBJ.readRaw(f"""
            SELECT o.numero_op
            FROM ordem_de_producao o
            WHERE {filtro_finalizar}
            ORDER BY o.numero_op DESC
        """, realdict=True)

        ordens_iniciar_producao = databaseOBJ.readRaw(f"""
            SELECT o.numero_op
            FROM ordem_de_producao o
            WHERE {filtro_iniciar}
            ORDER BY o.numero_op DESC
        """, realdict=True)

    else:

        ordens = databaseOBJ.readRaw(f"""
            SELECT o.numero_op
            FROM ordem_de_producao o
            WHERE {filtro_finalizar}
            AND NOT EXISTS (
                SELECT 1
                FROM producao p
                WHERE p.id_ordem_de_producao = o.id
                AND p.id_processo = %s
                AND p.status = 2
            )
            ORDER BY o.numero_op DESC
        """, (id_processo,), realdict=True)

        ordens_iniciar_producao = databaseOBJ.readRaw(f"""
            SELECT o.numero_op
            FROM ordem_de_producao o
            WHERE {filtro_iniciar}
            AND NOT EXISTS (
                SELECT 1
                FROM producao p
                WHERE p.id_ordem_de_producao = o.id
                AND p.id_processo = %s
                AND p.status = 2
            )
            ORDER BY o.numero_op DESC
        """, (id_processo,), realdict=True)

    # 🔎 Operadores
    operadores = databaseOBJ.readRaw("""
        SELECT id, codigo, nome
        FROM operador
        ORDER BY nome ASC
    """, realdict=True)

    # 🔎 Máquinas
    machine_names = databaseOBJ.readRaw("""
        SELECT id, bancada, setor, empresa
        FROM maquina
        ORDER BY id ASC
    """, realdict=True)

    return render_template(
        'monitoramento_tabela.html',
        machine_names=machine_names,
        processo=processo,
        ordens=ordens,
        ordens_iniciar_producao=ordens_iniciar_producao,
        operadores=operadores,
        nome_processo=nome_processo
    )

@app.route('/buscar_produtos')
def buscar_produtos():

    search = request.args.get('search','')

    produtos = databaseOBJ.readRaw("""
        SELECT id, codigo, nome
        FROM produtos
        WHERE codigo ILIKE %s
        AND ativo = true
        ORDER BY codigo
        LIMIT 20
    """, (f"%{search}%",), realdict=True)

    return jsonify(produtos)

@app.route('/processos_por_ordem')
@login_required
def processos_por_ordem():

    numero_op = request.args.get("numero_op")

    if not numero_op:
        return jsonify([])

    sql = """
        SELECT DISTINCT pr.id, pr.nome
        FROM producao p
        INNER JOIN processos pr
            ON p.id_processo = pr.id
        INNER JOIN ordem_de_producao o
            ON p.id_ordem_de_producao = o.id
        WHERE o.numero_op = %s
        AND p.status != 2
        ORDER BY pr.id
    """

    valores = databaseOBJ.readRaw(sql, (numero_op,), realdict=True)

    return jsonify(valores)

@app.route('/setup_pcp')
@login_required
def setup_pcp():

    user = databaseOBJ.readRaw(
        "select id, nome from usuarios where privilegio = 1 order by id DESC;"
    )

    clientes = databaseOBJ.readRaw(
        "SELECT id, nome FROM clientes WHERE visibilidade = true ORDER BY nome ASC;",
        realdict=True
    )

    materiais = databaseOBJ.readRaw(
        "SELECT id, codigo, descricao FROM material ORDER BY codigo ASC;",
        realdict=True
    )

    status_ordens = databaseOBJ.readRaw("""
        SELECT id, nome
        FROM status
        ORDER BY id
    """, realdict=True)

    produtos = databaseOBJ.readRaw("""
        SELECT id, codigo, nome
        FROM produtos
        WHERE ativo = true
        ORDER BY codigo
    """, realdict=True)

    return render_template(
        'setup.html',
        user=user,
        materiais=materiais,
        status_ordens=status_ordens,
        produtos=produtos,
        clientes=clientes
    )

@app.route('/cadastro_usuarios', methods=['GET'])
@login_required
@privilege_required(2)
def cadastro_usuarios():
    global databaseOBJ

    machine_names = databaseOBJ.readRaw(
        "SELECT id, bancada FROM maquina ORDER BY id ASC;"
    )

    return render_template(
        'usuarios.html',
        machine_names=machine_names
    )

@app.route('/adicionar_usuario', methods=['POST'])
@login_required
@privilege_required(2)
def adicionar_usuario():

    global databaseOBJ
    import bcrypt

    print("FORM RECEBIDO:", request.form)

    usuario = request.form['usuario']
    senha = request.form['senha']
    confirmar_senha = request.form['confirmar_senha']
    setor = request.form['setor']
    privilegio = int(request.form['privilegios'])

    # validar senha
    if senha != confirmar_senha:
        return jsonify({
            'success': False,
            'error': 'As senhas não conferem!'
        })

    if len(senha) < 6:
        return jsonify({
            'success': False,
            'error': 'Senha deve ter pelo menos 6 caracteres'
        })

    # Proteção contra escalada de privilégio
    if privilegio > current_user.privileges:
        return jsonify({'success': False, 'error': 'Permissão inválida'})

    # Verifica se já existe
    existe = databaseOBJ.readRaw(
        "SELECT id FROM usuarios WHERE usuario=%s;",
        (usuario,)
    )

    if existe:
        return jsonify({'success': False, 'error': 'Usuário já existe'})

    # Hash bcrypt
    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

    databaseOBJ.writeRaw(
        """
        INSERT INTO usuarios(usuario, senha, setor, privilegio)
        VALUES (%s,%s,%s,%s)
        """,
        (usuario, senha_hash, setor, privilegio)
    )

    return jsonify({'success': True})

@app.route('/adm_operadores')
@login_required
@privilege_required(2)
def adm_operadores():
    return render_template('adm_operador.html')
 
@app.route('/dados_operadores', methods=['GET','POST','PUT','DELETE'])
@login_required
def dados_operadores():

    # LISTAR
    if request.method == 'GET':

        resultado = databaseOBJ.readRaw("""
            SELECT id, nome, codigo
            FROM operador
            WHERE visibilidade = true
            ORDER BY nome
        """, realdict=True)

        return jsonify({"operadores": resultado})


    # ADICIONAR
    elif request.method == 'POST':

        nome = request.form.get('nome')
        codigo = request.form.get('codigo')

        # 🔎 verifica se já existe a chapa
        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM operador
            WHERE codigo = %s
        """,(codigo,), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Chapa já cadastrada."
            })

        # ➜ se não existir, insere
        databaseOBJ.writeRaw("""
            INSERT INTO operador (nome, codigo)
            VALUES (%s,%s)
        """,(nome,codigo))

        return jsonify({"success":True})

    # EDITAR
    elif request.method == 'PUT':

        id_operador = request.form.get('id')
        nome = request.form.get('nome')
        codigo = request.form.get('codigo')

        # 🔎 verifica se já existe outra chapa com o mesmo código
        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM operador
            WHERE codigo = %s
            AND id <> %s
        """,(codigo,id_operador), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Chapa já cadastrada."
            })

        # ➜ atualiza
        databaseOBJ.writeRaw("""
            UPDATE operador
            SET nome=%s,
                codigo=%s
            WHERE id=%s
        """,(nome,codigo,id_operador))

        return jsonify({"success":True})


    # EXCLUIR (Soft Delete)
    elif request.method == 'DELETE':

        id_operador = request.form.get('id')

        # Alterado de DELETE para UPDATE da coluna visibilidade
        databaseOBJ.writeRaw("""
            UPDATE operador 
            SET visibilidade = false
            WHERE id = %s
        """, (id_operador,))

        # Mantido o mesmo retorno para o frontend continuar funcionando perfeitamente
        return jsonify({"success": True})

@app.route('/adicionar_ordem', methods=['POST'])
@login_required
@privilege_required(2)
def adicionar_ordem():
    global databaseOBJ
    from datetime import datetime

    print("===== INICIO ADICIONAR ORDEM =====")
    print("FORM RECEBIDO:", request.form) 

    try:
        numero_op = request.form['numero_op'].strip()

        id_produto = int(request.form['id_produto'])
        id_cliente = int(request.form['id_cliente'])
        id_material = int(request.form['id_material'])
        id_tratamento = int(request.form['id_tratamento'])
        

        quantidade_total_ordem = int(request.form['quantidade_total_ordem'])

        data_entrega = request.form['data_entrega'].strip()

        

        numero_qualidade = request.form.get('numero_qualidade', '').strip()

        print("DADOS RECEBIDOS:")
        print("OP:", numero_op)
        print("ID Produto:", id_produto)
        print("Quantidade:", quantidade_total_ordem)

    except (KeyError, ValueError) as e:
        print("ERRO AO RECEBER DADOS:", e)
        return jsonify({'success': False, 'error': 'Dados inválidos'})

    # Validações
    if not numero_op or id_produto <= 0 or id_cliente <= 0:
        print("CAMPOS OBRIGATORIOS FALTANDO")
        return jsonify({'success': False, 'error': 'Campos obrigatórios não preenchidos'})

    if quantidade_total_ordem <= 0:
        print("QUANTIDADE INVALIDA")
        return jsonify({'success': False, 'error': 'Quantidade deve ser maior que zero'})

    try:
        datetime.strptime(data_entrega, '%Y-%m-%d')
    except ValueError:
        print("DATA INVALIDA")
        return jsonify({'success': False, 'error': 'Data inválida'})

    # Verifica banco atual
    banco_atual = databaseOBJ.readRaw("SELECT current_database();")
    print("BANCO CONECTADO:", banco_atual)

    if quantidade_total_ordem <= 0:
        print("QUANTIDADE INVALIDA")
        return jsonify({'success': False, 'error': 'Quantidade deve ser maior que zero'})

    # Verifica se já existe
    # O banco recebe a query e o dado separadamente
    existe = databaseOBJ.readRaw("SELECT id FROM ordem_de_producao WHERE numero_op = %s;", (numero_op,))

    print("RESULTADO EXISTE:", existe)

    if existe:
        print("ORDEM JA EXISTE")
        return jsonify({'success': False, 'error': 'Ordem já existe'})

    print("ANTES DO INSERT")

    databaseOBJ.writeRaw("""
        INSERT INTO ordem_de_producao (
            numero_op, 
            id_produto, 
            id_cliente, 
            quantidade, 
            data_entrega, 
            id_tratamento, 
            id_material, 
            numero_qualidade,
            ultimo_processo,  -- PCP
            processo_atual,   -- PCP
            status_id         -- Aguardando (ID 1)
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            0, -- Define ultimo_processo como 0 (PCP)
            0, -- Define processo_atual como 0 (PCP)
            1  -- Define status_id como 1 (Aguardando)
        )
    """, (
        numero_op, 
        id_produto, 
        id_cliente, 
        quantidade_total_ordem, 
        data_entrega, 
        id_tratamento, 
        id_material, 
        numero_qualidade
    ))

    print("DEPOIS DO INSERT")

    # Verificação imediata
    teste = databaseOBJ.readRaw(
        "SELECT id, numero_op FROM ordem_de_producao WHERE numero_op='%s';" % numero_op
    )

    print("VERIFICACAO APOS INSERT:", teste)

    print("===== FIM ADICIONAR ORDEM =====")

    return jsonify({'success': True})

@app.route('/iniciar_producao', methods=['POST'])
@login_required
def iniciar_producao():

    from datetime import datetime

    numero_op = request.form['id_ordem']
    id_operador = int(request.form['id_operador'])
    privilegio = current_user.privileges
    setor_usuario = current_user.setor

    MAPA_PROCESSOS = {
        "materia_prima": 1,
        "estamparia": 2,
        "solda": 3,
        "retifica": 4,
        "envio_terceiros": 5,
        "recebimento_terceiros": 6,
        "inspecao_final": 7,
        "expedicao": 8
    }

    # 🔎 Busca a ordem
    ordens = databaseOBJ.readRaw("""
        SELECT id
        FROM ordem_de_producao
        WHERE numero_op = %s
    """, (numero_op,))

    if not ordens:
        return jsonify({"success": False, "erro": "Ordem não encontrada"}), 400

    id_ordem = ordens[0][0]

    # 👑 ADMIN (privilegio 3) pode escolher o processo
    if privilegio == 3:
        id_processo = int(request.form['id_processo'])

    # 👷 Usuário comum fica preso ao setor dele
    else:
        id_processo = MAPA_PROCESSOS.get(setor_usuario)

        if not id_processo:
            return jsonify({
                "success": False,
                "erro": "Setor inválido para este usuário."
            }), 403

    # 🚫 Verifica se já existe produção ativa para essa OP nesse processo
    existe = databaseOBJ.readRaw("""
        SELECT 1
        FROM producao
        WHERE id_ordem_de_producao = %s
          AND id_processo = %s
          AND status = 1
    """, (id_ordem, id_processo))

    if existe:
        return jsonify({
            "success": False,
            "erro": "Esta OP já está em produção neste processo."
        }), 400

    # ✅ 1. Insere o registro na tabela de produção (Inicia o cronômetro)
    databaseOBJ.writeRaw("""
        INSERT INTO producao (
            dt_inicio,
            status,
            qtde_produzida,
            id_operador,
            id_ordem_de_producao,
            id_processo
        )
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        datetime.now(),
        1,
        0,
        id_operador,
        id_ordem,
        id_processo
    ))

    # 🔄 2. ATUALIZA A OP: Define como "Em Produção" e marca o PROCESSO ATUAL
    databaseOBJ.writeRaw("""
        UPDATE ordem_de_producao
        SET status_id = 2,
            processo_atual = %s
        WHERE id = %s
    """, (id_processo, id_ordem))

    return jsonify({"success": True})

@app.route('/finalizar_producao', methods=['POST'])
@login_required
def finalizar_producao():

    from datetime import datetime

    numero_op = request.form.get('id_ordem')
    id_operador_fim = request.form.get("id_operador_fim")
    quantidade = request.form.get('quantidade')

    privilegio = current_user.privileges
    setor_usuario = current_user.setor

    MAPA_PROCESSOS = {
        "materia_prima": 1,
        "estamparia": 2,
        "solda": 3,
        "retifica": 4,
        "envio_terceiros": 5,
        "recebimento_terceiros": 6,
        "inspecao_final": 7,
        "expedicao": 8
    }

    # 👑 ADMIN precisa escolher setor
    if privilegio == 3:
        id_processo = request.form.get('id_processo')

        if not id_processo:
            return jsonify({
                "success": False,
                "erro": "Selecione o setor."
            }), 400

        id_processo = int(id_processo)

    else:
        id_processo = MAPA_PROCESSOS.get(setor_usuario)

        if not id_processo:
            return jsonify({
                "success": False,
                "erro": "Setor inválido."
            }), 403

    # 🔎 Busca OP (Agora pegando o id_produto junto!)
    ordem = databaseOBJ.readRaw("""
        SELECT id, id_produto
        FROM ordem_de_producao
        WHERE numero_op = %s
    """, (numero_op,))

    if not ordem:
        return jsonify({"success": False, "erro": "Ordem não encontrada."}), 400

    id_ordem = ordem[0][0]
    id_produto = ordem[0][1]

    # 🔎 Busca produção ativa daquele processo
    producao = databaseOBJ.readRaw("""
        SELECT id
        FROM producao
        WHERE id_ordem_de_producao = %s
          AND id_processo = %s
          AND status = 1
    """, (id_ordem, id_processo))

    if not producao:
        return jsonify({
            "success": False,
            "erro": "Não existe produção ativa para este setor."
        }), 400

    id_producao = producao[0][0]

    # ✅ 1. Finaliza somente aquela linha de produção
    databaseOBJ.writeRaw("""
        UPDATE producao
        SET status = 2,
            dt_fim = %s,
            qtde_produzida = %s,
            id_operador_fim = %s
        WHERE id = %s
    """, (datetime.now(), quantidade, id_operador_fim, id_producao))

    # 🆕 2. ATUALIZA O RASTRO: O processo finalizado agora vira o 'ultimo_processo' na OP
    databaseOBJ.writeRaw("""
        UPDATE ordem_de_producao
        SET ultimo_processo = %s
        WHERE id = %s
    """, (id_processo, id_ordem))

    # 🎯 3. Lógica de Status Geral da OP
    if id_processo == 8:
        
        # Expedição finaliza geral a OP
        databaseOBJ.writeRaw("""
            UPDATE ordem_de_producao
            SET status_id = 3
            WHERE id = %s
        """, (id_ordem,))

        # Atualiza o Saldo do Produto
        databaseOBJ.writeRaw("""
            UPDATE produtos
            SET saldo = saldo + %s
            WHERE id = %s
        """, (quantidade, id_produto))

        # Registra a ENTRADA no Histórico
        try:
            id_usuario_logado = current_user.id
            databaseOBJ.writeRaw("""
                INSERT INTO movimentacoes_estoque (id_produto, quantidade, operacao, id_usuario)
                VALUES (%s, %s, 0, %s)
            """, (id_produto, quantidade, id_usuario_logado))
            
        except Exception as e:
            return jsonify({
                "success": False, 
                "erro": f"O saldo subiu, mas o Histórico falhou. Erro do Banco: {str(e)}"
            })

    else:
        # Só volta para aguardando se não houver mais setores produzindo
        databaseOBJ.writeRaw("""
            UPDATE ordem_de_producao
            SET status_id = 1
            WHERE id = %s
            AND NOT EXISTS (
                SELECT 1
                FROM producao
                WHERE id_ordem_de_producao = %s
                AND dt_fim IS NULL
            )
        """, (id_ordem, id_ordem))

    return jsonify({"success": True})

@app.route('/produto_por_codigo', methods=['GET'])
@login_required
def produto_por_codigo():

    codigo = request.args.get('codigo')

    produto = databaseOBJ.readRaw("SELECT id, nome FROM produtos WHERE ativo = true AND codigo = %s;", (codigo,), realdict=True)

    if not produto:
        return jsonify({'success': False})

    return jsonify({
        'success': True,
        'id_produto': produto[0]['id'],
        'nome': produto[0]['nome'].strip()
    })   

@app.route('/historico_movimentacoes', methods=['GET'])
@login_required
def historico_movimentacoes():
    # 🔎 Correção feita no 'u.usuario'
    query = """
        SELECT 
            p.nome AS produto_nome, 
            p.codigo AS produto_codigo, 
            m.operacao, 
            m.quantidade, 
            u.usuario AS usuario_nome, 
            TO_CHAR(m.data, 'DD/MM/YYYY HH24:MI') as data_formatada
        FROM movimentacoes_estoque m
        JOIN produtos p ON m.id_produto = p.id
        JOIN usuarios u ON m.id_usuario = u.id
        ORDER BY m.data DESC
    """
    
    try:
        historico = databaseOBJ.readRaw(query, realdict=True)
        return jsonify({"success": True, "historico": historico})
    except Exception as e:
        print("Erro ao carregar histórico:", e)
        return jsonify({"success": False, "error": "Erro ao carregar o histórico."}), 500

#app.run(debug=True)

#app.run(host='10.104.2.9', port=5000, debug=True)

# No final do seu main.py
if __name__ == "__main__":
    # Isso só roda se você executar 'python main.py' manualmente
    # O Gunicorn ignora esse bloco, o que evita o conflito
    app.run(host='0.0.0.0', port=5000, debug=True)

