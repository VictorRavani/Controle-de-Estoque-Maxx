# ==============================================================================
# 1. Bibliotecas Nativas (Built-ins)
# Já vêm no Python, não precisam ser instaladas. Leves e rápidas.
# ==============================================================================
import os                           # Permite que o Python interaja com o Sistema Operacional para ler variáveis de ambiente
import io                           # Para manipular arquivos na memória RAM (ex: gerar relatórios sem HD)
import re                           # Expressões regulares para validação de códigos de barras e higienização
import csv                          # Para ler ou exportar dados em formato de planilha/texto
import json                         # Manipulação de dados JSON
import secrets                      # Geração criptograficamente segura de tokens CSRF e chaves
import unicodedata                  # Normalização de textos e cabeçalhos de planilhas
import zipfile                      # Leitura nativa de arquivos .xlsx (ZIP/XML)
import xml.etree.ElementTree as ET  # Parser XML nativo para fallback de planilhas .xlsx
from decimal import Decimal, InvalidOperation # Conversão exata de códigos numéricos e notação científica do Excel
from datetime import datetime, timedelta # Para pegar a data atual e fazer cálculos simples
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
    flash,           # Para enviar mensagens rápidas de aviso na tela (ex: "Senha incorreta")
    session,         # Gerenciamento seguro de sessão e token CSRF
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

# Flask configuration
versao = '1.1.0'
app = Flask(__name__)

# Lê a variável do .env. Se não achar, assume False por segurança.
modo_debug = os.getenv('FLASK_DEBUG', 'False') == 'True'
app.config['DEBUG'] = modo_debug

# Configuração segura da Secret Key e Cookies de Sessão
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Limite máximo de upload: 10 MB

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)

# Database configuration
# Puxa o host do arquivo .env. Se não achar, usa 'localhost' para você testar no Windows.
db_host = os.getenv('DB_HOST', 'localhost')
databaseOBJ = database.postgresDatabase(host=db_host)

# Flag de controle de inicialização automática do schema e admin
_sistema_inicializado = False

def inicializar_sistema():
    """
    Garante que todas as colunas/tabelas novas existam no banco de dados,
    aplica a trigger de imutabilidade no histórico de movimentações e
    cria o usuário 'admin' padrão com obrigatoriedade de troca de senha no 1º login.
    """
    global _sistema_inicializado
    if _sistema_inicializado:
        return

    if not databaseOBJ.conectar():
        return

    try:
        # 1. Migrações seguras e idempotentes de schema
        databaseOBJ.writeRaw("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS visibilidade BOOLEAN DEFAULT TRUE;")
        databaseOBJ.writeRaw("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precisa_trocar_senha BOOLEAN DEFAULT FALSE;")
        databaseOBJ.writeRaw("ALTER TABLE produtos ADD COLUMN IF NOT EXISTS localizacao VARCHAR(100);")
        databaseOBJ.writeRaw("ALTER TABLE produtos ALTER COLUMN codigo TYPE VARCHAR(50);")

        databaseOBJ.writeRaw("""
            CREATE TABLE IF NOT EXISTS public.fornecedores (
                id bigint PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
                nome character varying(150) NOT NULL,
                whatsapp character varying(50),
                email character varying(120),
                forma_pagamento character varying(100),
                chave_pix character varying(150),
                ativo boolean DEFAULT true NOT NULL
            );
        """)

        databaseOBJ.writeRaw("""
            CREATE TABLE IF NOT EXISTS public.valor_de_compra (
                id bigint PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
                id_produto bigint NOT NULL REFERENCES public.produtos(id),
                id_fornecedor bigint NOT NULL REFERENCES public.fornecedores(id),
                preco_ultima_compra numeric(12,2) NOT NULL,
                data_modificacao timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
        """)

        # 2. Evolução da tabela movimentacoes_estoque para suportar Entradas (0), Saídas (1) e Ajustes (2) + Auditoria
        databaseOBJ.writeRaw("ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS saldo_anterior NUMERIC(12,2);")
        databaseOBJ.writeRaw("ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS saldo_posterior NUMERIC(12,2);")
        databaseOBJ.writeRaw("ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS observacao VARCHAR(255);")
        databaseOBJ.writeRaw("ALTER TABLE movimentacoes_estoque DROP CONSTRAINT IF EXISTS movimentacoes_estoque_operacao_check;")
        databaseOBJ.writeRaw("""
            ALTER TABLE movimentacoes_estoque
            ADD CONSTRAINT movimentacoes_estoque_operacao_check CHECK (operacao = ANY (ARRAY[0, 1, 2]));
        """)

        # 3. Trigger para tornar o log de movimentações estritamente imutável (bloqueia UPDATE e DELETE)
        databaseOBJ.writeRaw("""
            CREATE OR REPLACE FUNCTION public.bloquear_alteracao_movimentacoes()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Operação negada: O histórico de movimentações de estoque é um log de auditoria imutável.';
            END;
            $$ LANGUAGE plpgsql;
        """)
        databaseOBJ.writeRaw("DROP TRIGGER IF EXISTS trg_movimentacoes_imutavel ON public.movimentacoes_estoque;")
        databaseOBJ.writeRaw("""
            CREATE TRIGGER trg_movimentacoes_imutavel
            BEFORE UPDATE OR DELETE ON public.movimentacoes_estoque
            FOR EACH ROW EXECUTE FUNCTION public.bloquear_alteracao_movimentacoes();
        """)

        # 4. Criação/verificação automática do usuário 'admin' padrão
        senha_padrao_admin = os.getenv('ADMIN_DEFAULT_PASSWORD', 'admin123')
        admin_rows = databaseOBJ.readRaw(
            "SELECT id, senha, precisa_trocar_senha, visibilidade FROM usuarios WHERE usuario = %s LIMIT 1;",
            ('admin',),
            realdict=True
        )

        if not admin_rows:
            senha_hash = bcrypt.hashpw(senha_padrao_admin.encode(), bcrypt.gensalt()).decode()
            databaseOBJ.writeRaw(
                """
                INSERT INTO usuarios (usuario, senha, privilegio, visibilidade, precisa_trocar_senha)
                VALUES (%s, %s, 3, true, true);
                """,
                ('admin', senha_hash)
            )
            print("Usuário 'admin' padrão criado automaticamente (troca de senha obrigatória no 1º login).")
        else:
            admin_info = admin_rows[0]
            # Se o admin ainda estiver com a senha padrão 'admin123', garante que a trava de 1º login esteja ativa
            try:
                if bcrypt.checkpw(senha_padrao_admin.encode(), admin_info['senha'].encode()):
                    databaseOBJ.writeRaw(
                        "UPDATE usuarios SET precisa_trocar_senha = true, visibilidade = true, privilegio = 3 WHERE id = %s;",
                        (admin_info['id'],)
                    )
            except Exception:
                pass

        _sistema_inicializado = True
    except Exception as e:
        print("Aviso durante inicialização automática do sistema:", e)

# Tenta inicializar na subida da aplicação
inicializar_sistema()

############################################# SEGURANÇA E CÓDIGOS DE BARRAS ##########################################

def obter_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def sanitizar_celula_csv(valor):
    """Previne CSV Formula Injection no Excel (=, +, -, @ no início de textos)"""
    if valor is None:
        return ""
    texto = str(valor)
    if texto and texto[0] in ('=', '+', '-', '@') and not texto.startswith('="'):
        try:
            float(texto.replace(',', '.'))
        except ValueError:
            return "'" + texto
    return texto

def calcular_digito_ean13(base_12_digitos):
    """Calcula o dígito verificador oficial Modulo-10 de um código EAN-13"""
    soma = 0
    for idx, char in enumerate(base_12_digitos[:12]):
        digito = int(char)
        soma += digito if idx % 2 == 0 else digito * 3
    resto = soma % 10
    return str((10 - resto) % 10)

def validar_checksum_ean13(codigo_13):
    """Verifica se um código numérico de 13 dígitos possui dígito verificador EAN-13 válido"""
    if not codigo_13 or len(codigo_13) != 13 or not codigo_13.isdigit():
        return False
    return calcular_digito_ean13(codigo_13[:12]) == codigo_13[12]

def gerar_ean13_interno(numero_sequencial):
    """Gera um código de barras interno padrão EAN-13 (prefixo 200 de circulação interna) com dígito verificador válido"""
    base_12 = f"200{int(numero_sequencial):09d}"[:12]
    return base_12 + calcular_digito_ean13(base_12)

def limpar_codigo_barras(codigo_bruto):
    """
    Higieniza leituras de leitores ópticos ou planilhas:
    - Converte int/float/Decimal ou notação científica do Excel (ex: 7,8984E+12 / 7.8984E+12) para string inteira
    - Remove caracteres de controle invisíveis (CR, LF, TAB)
    - Remove formatação de exportação Excel (="...", apóstrofo inicial ') e sufixos .0 / ,0 de floats
    """
    if codigo_bruto is None or isinstance(codigo_bruto, bool):
        return ""

    # Se vier como número nativo (int, float, Decimal) do openpyxl
    if isinstance(codigo_bruto, int):
        return str(codigo_bruto)
    if isinstance(codigo_bruto, (float, Decimal)):
        try:
            d = Decimal(str(codigo_bruto))
            if d == d.to_integral_value():
                return str(int(d))
            return format(d.normalize(), 'f')
        except (InvalidOperation, ValueError):
            pass

    codigo = str(codigo_bruto).strip()
    if codigo.startswith('="') and codigo.endswith('"'):
        codigo = codigo[2:-1].strip()
    elif codigo.startswith("'") and len(codigo) > 1:
        codigo = codigo[1:].strip()
    elif codigo.startswith('"') and codigo.endswith('"') and len(codigo) >= 2:
        codigo = codigo[1:-1].strip()

    codigo = re.sub(r'[\x00-\x1f\x7f]', '', codigo).strip()

    # Trata sufixo decimal .0 ou ,0 adicionado por conversão float (ex: "7891452138945.0")
    if re.match(r'^\d+[.,]0+$', codigo):
        return re.split(r'[.,]', codigo)[0]

    # Trata notação científica gerada pelo Excel PT-BR ou EN (ex: "7,8984E+12" ou "7.898403650143E+12")
    if re.match(r'^[+-]?\d+(?:[.,]\d+)?[eE][+-]?\d+$', codigo):
        try:
            d = Decimal(codigo.replace(',', '.'))
            if d == d.to_integral_value():
                return str(int(d))
            return format(d, 'f').split('.')[0]
        except (InvalidOperation, ValueError):
            pass

    return codigo

def interpretar_codigo_barras(codigo_bruto):
    """
    Analisa, valida e interpreta códigos de barras:
    1. Etiqueta de Ordem de Produção (36 dígitos numéricos):
       [0:8]   -> Número da OP
       [8:16]  -> Número de Qualidade (Certificado A.Q.)
       [16:28] -> Código do Produto (12 posições)
       [28:36] -> Data de Entrega (YYYYMMDD)
    2. Código de Produto Comercial/Interno (EAN-8, UPC-12, EAN-13, DUN-14 ou Alfanumérico interno):
       Valida formato e retorna candidatos de busca (com e sem zeros à esquerda).
    """
    codigo = limpar_codigo_barras(codigo_bruto)
    if not codigo:
        return {"valido": False, "erro": "Código de barras vazio."}

    if codigo.upper() in ("SEM CODIGO", "SEM CÓDIGO", "-", "NULL", "NONE"):
        return {"valido": False, "erro": "O texto informado não é um código de barras rastreável."}

    # Caso 1: Código composto de Ordem de Produção (36 dígitos)
    if len(codigo) == 36 and codigo.isdigit():
        op_raw = codigo[0:8]
        aq_raw = codigo[8:16]
        prod_raw = codigo[16:28]
        data_raw = codigo[28:36]

        numero_op = op_raw.lstrip('0') or '0'
        numero_qualidade = aq_raw.lstrip('0') or '0'
        codigo_produto_sem_zeros = prod_raw.lstrip('0') or '0'

        data_iso = None
        try:
            dt = datetime.strptime(data_raw, "%Y%m%d")
            data_iso = dt.strftime("%Y-%m-%d")
        except ValueError:
            return {
                "valido": False,
                "erro": f"Data de entrega inválida na etiqueta de 36 dígitos ({data_raw})."
            }

        candidatos = []
        for c in (prod_raw, codigo_produto_sem_zeros):
            if c and c not in candidatos:
                candidatos.append(c)

        return {
            "valido": True,
            "tipo": "OP_36",
            "codigo_limpo": codigo,
            "numero_op": numero_op,
            "numero_qualidade": numero_qualidade,
            "codigo_produto": codigo_produto_sem_zeros,
            "data_entrega": data_iso,
            "candidatos_produto": candidatos
        }

    # Caso 2: Se tiver 36 caracteres mas não for numérico
    if len(codigo) > 36:
        return {"valido": False, "erro": "Comprimento de código de barras inválido (máximo 36 caracteres)."}

    # Caso 3: Código de barras de produto (EAN-8, UPC-12, EAN-13, DUN-14, Code128 / Interno)
    if not re.match(r'^[A-Za-z0-9\-_.]{3,35}$', codigo):
        return {
            "valido": False,
            "erro": "Formato de código inválido. Use apenas letras, números, hífen ou ponto (mín. 3 caracteres)."
        }

    candidatos = [codigo]
    sem_zeros = codigo.lstrip('0')
    if sem_zeros and sem_zeros not in candidatos:
        candidatos.append(sem_zeros)
    if codigo.isdigit() and len(codigo) == 12:
        # Compatibilidade UPC-A (12 dígitos) -> EAN-13 (0 + 12 dígitos)
        candidatos.append('0' + codigo)

    return {
        "valido": True,
        "tipo": "PRODUTO",
        "codigo_limpo": codigo,
        "codigo_produto": codigo,
        "ean13_valido": validar_checksum_ean13(codigo) if (len(codigo) == 13 and codigo.isdigit()) else None,
        "candidatos_produto": candidatos
    }

################################################## AUTHENTICATION ####################################################

@app.context_processor
def inject_globals():
    """Injeta a data/hora atual e o token CSRF em todos os templates HTML automaticamente"""
    return {
        'now': datetime.now(),
        'csrf_token': obter_csrf_token
    }

@app.before_request
def middleware_seguranca_e_primeiro_login():
    """
    Middleware global:
    1. Garante inicialização do schema e do admin padrão.
    2. Protege rotas mutáveis (POST, PUT, DELETE) contra ataques CSRF.
    3. Bloqueia a navegação caso o usuário logado esteja marcado com 'precisa_trocar_senha' (1º login do admin).
    """
    inicializar_sistema()

    # Ignora arquivos estáticos
    if request.endpoint == 'static':
        return

    # 1. Validação CSRF para requisições que alteram estado
    if request.method in ('POST', 'PUT', 'DELETE'):
        token_sessao = session.get('_csrf_token')
        token_enviado = (
            request.headers.get('X-CSRFToken')
            or request.headers.get('X-CSRF-Token')
            or request.form.get('csrf_token')
            or request.values.get('csrf_token')
        )
        # Se já existe token na sessão, valida correspondência segura
        if token_sessao and token_enviado:
            if not secrets.compare_digest(str(token_sessao), str(token_enviado)):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    return jsonify({"success": False, "error": "Token de segurança (CSRF) inválido. Recarregue a página."}), 400
                abort(400)
        elif token_sessao and not token_enviado and request.endpoint not in ('login',):
            # Verifica se a requisição veio da mesma origem (Same-Origin fallback seguro)
            origin = request.headers.get('Origin') or request.headers.get('Referer') or ''
            if origin and request.host_url.rstrip('/') not in origin:
                return jsonify({"success": False, "error": "Requisição bloqueada por proteção CSRF."}), 403

    # 2. Trava obrigatória de troca de senha no primeiro login
    if current_user.is_authenticated and getattr(current_user, 'precisa_trocar_senha', False):
        rotas_permitidas = {'primeiro_acesso', 'mudarsenha', 'logout', 'static'}
        if request.endpoint not in rotas_permitidas:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method != 'GET':
                return jsonify({
                    "success": False,
                    "force_password_change": True,
                    "error": "Por segurança, você deve alterar a senha padrão antes de realizar qualquer operação."
                }), 403
            return redirect(url_for('primeiro_acesso'))

@app.after_request
def aplicar_headers_seguranca(response):
    """Adiciona cabeçalhos HTTP de proteção contra Clickjacking, MIME Sniffing e vazamento de Referrer"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Create class that extends default flask_login User Class
class User(UserMixin):
    def __init__(self):
        super(User, self).__init__()
        self.name = ''
        self.privileges = 1
        self.precisa_trocar_senha = False

@login_manager.user_loader
def load_user(userid):

    try:
        userid = int(userid)
    except Exception:
        return None

    credentials = databaseOBJ.readRaw(
        """
        SELECT id, usuario, privilegio, setor, COALESCE(precisa_trocar_senha, false) AS precisa_trocar_senha
        FROM usuarios
        WHERE id = %s AND COALESCE(visibilidade, true) = true
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
        user.precisa_trocar_senha = bool(credentials[0].get('precisa_trocar_senha', False))

        return user
    return None

# Callback to manage unauthorized access
@login_manager.unauthorized_handler
def unauth_handler():
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method != 'GET':
        return jsonify({"success": False, "error": "Sessão expirada ou usuário não autenticado."}), 401
    return redirect(url_for('autenticacao'))

@app.route('/login', methods=['POST'])
def login():

    user = request.form.get('user', '').strip()
    password = request.form.get('password', '')

    if not user or not password:
        return abort(400)

    credentials = databaseOBJ.readRaw(
        """
        SELECT id, usuario, privilegio, senha, setor, COALESCE(precisa_trocar_senha, false)
        FROM usuarios
        WHERE usuario = %s AND COALESCE(visibilidade, true) = true
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
            usuario_logado.precisa_trocar_senha = bool(credentials[0][5])

            # Se for o admin ainda com a senha padrão, força a flag mesmo em bancos legados
            senha_padrao_admin = os.getenv('ADMIN_DEFAULT_PASSWORD', 'admin123')
            if usuario_logado.usuario == 'admin' and password == senha_padrao_admin:
                usuario_logado.precisa_trocar_senha = True
                databaseOBJ.writeRaw(
                    "UPDATE usuarios SET precisa_trocar_senha = true WHERE id = %s;",
                    (usuario_logado.id,)
                )

            session.permanent = True
            login_user(usuario_logado)
            obter_csrf_token()

            return jsonify({
                'Login': True,
                'force_password_change': usuario_logado.precisa_trocar_senha,
                'redirect_url': url_for('primeiro_acesso') if usuario_logado.precisa_trocar_senha else url_for('adm_produtos')
            })

    return make_response({'Login': False})

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    session.clear()
    return jsonify({'Login': True})

@app.route('/primeiro_acesso', methods=['GET'])
@login_required
def primeiro_acesso():
    """Tela bloqueante que exige a redefinição da senha padrão no primeiro login"""
    if not getattr(current_user, 'precisa_trocar_senha', False):
        return redirect(url_for('adm_produtos'))
    return render_template('autenticacao.html', modo_primeiro_acesso=True)

def privilege_required(level):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if not current_user.is_authenticated:
                return redirect(url_for('autenticacao'))

            if current_user.privileges < level:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method != 'GET':
                    return jsonify({"success": False, "error": "Permissão insuficiente para executar esta ação."}), 403
                flash("Você não tem permissão para acessar esta página.")
                return redirect(url_for('adm_produtos'))

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
        userlogin = form.get('usuario', '').strip()
        usersector = form.get('setor')
        userprivileges = form.get('privilegios')
        novaSenha = form.get('novaSenha')

        if not (userid and userlogin and userprivileges):
            return jsonify({
                "success": False,
                "error": "Dados obrigatórios não informados."
            })

        userprivileges = int(userprivileges)

        # Proteção contra escalada de privilégio
        if userprivileges > current_user.privileges:
            return jsonify({
                "success": False,
                "error": "Permissão inválida."
            }), 403

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
            AND COALESCE(visibilidade, true) = true
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
                        senha = %s,
                        precisa_trocar_senha = false
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

        userlogin = form.get('usuario', '').strip()
        usersector = form.get('setor')
        userprivileges = form.get('privilegios')

        if not (userlogin and userprivileges):
            abort(400)

        if userprivileges == '1' and not usersector:
            abort(400)
        
        if userprivileges != '1':
            usersector = None

        if int(userprivileges) > current_user.privileges:
            abort(403)

        senha_hash = bcrypt.hashpw(
            userlogin.lower().encode(),
            bcrypt.gensalt()
        ).decode()

        databaseOBJ.writeRaw(
            """
            INSERT INTO usuarios (usuario, setor, senha, privilegio, precisa_trocar_senha)
            VALUES (%s, %s, %s, %s, true)
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

        id_processo = MAPA_PROCESSOS.get((setor_usuario or '').lower().strip())

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
    userlogin = request.args.get('usuario', '').strip()

    if userlogin:
        sql = "SELECT usuario FROM usuarios WHERE usuario = %s AND COALESCE(visibilidade, true) = true;"
        query = databaseOBJ.readRaw(sql, (userlogin,))
        return jsonify({'available': len(query) == 0})
    else:
        return abort(400)

@app.route('/mudarsenha', methods=['PUT', 'POST'])
@login_required
def mudarsenha():
    """
    Altera a senha do usuário autenticado.
    Aceita apenas métodos seguros (PUT/POST), exige mínimo de 6 caracteres,
    bloqueia reutilização da senha padrão e libera o bloqueio de 1º login.
    """
    form = request.form
    userid = current_user.get_id()
    currentPassword = form.get('currentPassword')
    newPassword = form.get('newPassword')

    if not currentPassword or not newPassword:
        return jsonify({'changeUserPassword': False, 'error': 'Preencha a senha atual e a nova senha.'}), 400

    if len(newPassword.strip()) < 6:
        return jsonify({'changeUserPassword': False, 'error': 'A nova senha deve possuir no mínimo 6 caracteres.'})

    senha_padrao_admin = os.getenv('ADMIN_DEFAULT_PASSWORD', 'admin123')
    if newPassword.strip() == currentPassword.strip() or newPassword.strip() == senha_padrao_admin:
        return jsonify({
            'changeUserPassword': False,
            'error': 'A nova senha deve ser diferente da senha atual e da senha padrão.'
        })

    password_query = databaseOBJ.readRaw("SELECT senha FROM usuarios WHERE id = %s;", (userid,))
    if not password_query:
        return jsonify({'changeUserPassword': False, 'error': 'Usuário não encontrado.'}), 404

    password_atual_hash = password_query[0][0]
    if bcrypt.checkpw(currentPassword.encode(), password_atual_hash.encode()):
        novo_hash = bcrypt.hashpw(newPassword.encode(), bcrypt.gensalt()).decode()
        databaseOBJ.writeRaw(
            "UPDATE usuarios SET senha = %s, precisa_trocar_senha = false WHERE id = %s;",
            (novo_hash, userid)
        )
        current_user.precisa_trocar_senha = False
        return jsonify({'changeUserPassword': True})
    else:
        return jsonify({'changeUserPassword': False, 'error': 'Senha atual incorreta.'})

################################################# PRODUTOS & ESTOQUE #################################################

@app.route('/adm/produtos')
@login_required
@privilege_required(1)
def adm_produtos():
    return render_template('adm_produtos.html')

@app.route('/gerar_codigo_barras', methods=['GET'])
@login_required
def gerar_codigo_barras():
    """Gera automaticamente um código EAN-13 interno único e válido para novos produtos sem código de fábrica"""
    prox_id_query = databaseOBJ.readRaw("SELECT COALESCE(MAX(id), 0) + 1 FROM produtos;")
    sequencia = int(prox_id_query[0][0]) if prox_id_query else 1

    while True:
        candidato = gerar_ean13_interno(sequencia)
        existe = databaseOBJ.readRaw(
            "SELECT 1 FROM produtos WHERE codigo = %s LIMIT 1;",
            (candidato,)
        )
        if not existe:
            return jsonify({"success": True, "codigo": candidato})
        sequencia += 1

@app.route('/produtos', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def produtos():

    # 🔎 LISTAR (acessível para usuários autenticados)
    if request.method == 'GET':

        produtos_lista = databaseOBJ.readRaw("""
            SELECT 
                p.id,
                p.nome,
                p.codigo,
                p.saldo,
                p.estoque_minimo,
                p.ativo,
                p.localizacao,
                menor.id_fornecedor AS id_fornecedor_menor_preco,
                menor.fornecedor_nome AS fornecedor_menor_preco,
                menor.whatsapp AS fornecedor_whatsapp,
                menor.forma_pagamento AS fornecedor_pagamento,
                menor.preco_ultima_compra AS menor_preco,
                menor.preco_ultima_compra AS ultimo_preco,
                COALESCE(todos_forn.qtd_fornecedores, 0) AS qtd_fornecedores,
                COALESCE(todos_forn.lista_fornecedores, '[]'::json) AS fornecedores_precos
            FROM produtos p
            LEFT JOIN LATERAL (
                SELECT 
                    ult.id_fornecedor,
                    f.nome AS fornecedor_nome,
                    f.whatsapp,
                    f.forma_pagamento,
                    ult.preco_ultima_compra,
                    ult.data_modificacao
                FROM (
                    SELECT DISTINCT ON (vc.id_fornecedor)
                        vc.id_fornecedor,
                        vc.preco_ultima_compra,
                        vc.data_modificacao
                    FROM valor_de_compra vc
                    WHERE vc.id_produto = p.id
                    ORDER BY vc.id_fornecedor, vc.data_modificacao DESC
                ) ult
                INNER JOIN fornecedores f ON f.id = ult.id_fornecedor
                WHERE f.ativo = true AND ult.preco_ultima_compra > 0
                ORDER BY ult.preco_ultima_compra ASC, ult.data_modificacao DESC
                LIMIT 1
            ) menor ON true
            LEFT JOIN LATERAL (
                SELECT 
                    COUNT(*) AS qtd_fornecedores,
                    json_agg(
                        json_build_object(
                            'id_fornecedor', OrderedForn.id_fornecedor,
                            'fornecedor_nome', OrderedForn.fornecedor_nome,
                            'whatsapp', OrderedForn.whatsapp,
                            'forma_pagamento', OrderedForn.forma_pagamento,
                            'preco', OrderedForn.preco_ultima_compra
                        )
                    ) AS lista_fornecedores
                FROM (
                    SELECT 
                        ult2.id_fornecedor,
                        f2.nome AS fornecedor_nome,
                        f2.whatsapp,
                        f2.forma_pagamento,
                        ult2.preco_ultima_compra
                    FROM (
                        SELECT DISTINCT ON (vc2.id_fornecedor)
                            vc2.id_fornecedor,
                            vc2.preco_ultima_compra,
                            vc2.data_modificacao
                        FROM valor_de_compra vc2
                        WHERE vc2.id_produto = p.id
                        ORDER BY vc2.id_fornecedor, vc2.data_modificacao DESC
                    ) ult2
                    INNER JOIN fornecedores f2 ON f2.id = ult2.id_fornecedor
                    WHERE f2.ativo = true AND ult2.preco_ultima_compra > 0
                    ORDER BY ult2.preco_ultima_compra ASC, ult2.data_modificacao DESC
                ) OrderedForn
            ) todos_forn ON true
            WHERE p.ativo = true
            ORDER BY p.nome
        """, realdict=True)

        return jsonify({"produtos": produtos_lista})

    # 🔒 Operações de escrita em produtos exigem nível >= 2 (PCP / Admin)
    if current_user.privileges < 2:
        return jsonify({"success": False, "error": "Permissão insuficiente para alterar o cadastro de produtos."}), 403

    # ➕ ADICIONAR
    if request.method == 'POST':

        nome = (request.values.get('nome') or '').strip()
        codigo_bruto = request.values.get('codigo') or ''
        saldo_str = request.values.get('saldo', '0')
        estoque_minimo_str = request.values.get('estoque_minimo', '0')
        id_fornecedor = request.values.get('id_fornecedor')
        preco = request.values.get('preco')
        localizacao = (request.values.get('localizacao') or '').strip()

        if not nome:
            return jsonify({"success": False, "error": "Informe a descrição/nome do produto."})

        # Se o código vier vazio ou "SEM CODIGO", gera um EAN-13 interno único
        codigo_limpo = limpar_codigo_barras(codigo_bruto)
        if not codigo_limpo or codigo_limpo.upper() in ("SEM CODIGO", "SEM CÓDIGO", "-"):
            prox_id_query = databaseOBJ.readRaw("SELECT COALESCE(MAX(id), 0) + 1 FROM produtos;")
            seq = int(prox_id_query[0][0]) if prox_id_query else 1
            while True:
                codigo_limpo = gerar_ean13_interno(seq)
                if not databaseOBJ.readRaw("SELECT 1 FROM produtos WHERE codigo = %s LIMIT 1;", (codigo_limpo,)):
                    break
                seq += 1
        else:
            validacao = interpretar_codigo_barras(codigo_limpo)
            if not validacao["valido"]:
                return jsonify({"success": False, "error": validacao["erro"]})
            codigo_limpo = validacao["codigo_produto"]

        try:
            saldo = float(str(saldo_str).replace(',', '.'))
            estoque_minimo = float(str(estoque_minimo_str).replace(',', '.'))
            if saldo < 0 or estoque_minimo < 0:
                return jsonify({"success": False, "error": "Saldo e estoque mínimo não podem ser negativos."})
        except ValueError:
            return jsonify({"success": False, "error": "Valores numéricos inválidos para saldo ou estoque mínimo."})

        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM produtos
            WHERE ativo = true
            AND codigo = %s
            LIMIT 1
        """, (codigo_limpo,), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": f"Operação bloqueada! O código '{codigo_limpo}' já está em uso por outro produto."
            })

        try:
            databaseOBJ.writeRaw("""
                INSERT INTO produtos (nome, codigo, saldo, estoque_minimo, localizacao, ativo)
                VALUES (%s, %s, %s, %s, %s, true)
            """, (nome, codigo_limpo, saldo, estoque_minimo, localizacao))

            produto_salvo = databaseOBJ.readRaw("""
                SELECT id FROM produtos WHERE codigo = %s AND ativo = true ORDER BY id DESC LIMIT 1
            """, (codigo_limpo,), realdict=True)

            if produto_salvo:
                id_novo = produto_salvo[0]['id']

                # Registra no log imutável se o produto já nasceu com saldo inicial > 0
                if saldo > 0:
                    databaseOBJ.writeRaw("""
                        INSERT INTO movimentacoes_estoque (
                            id_produto, operacao, quantidade, saldo_anterior, saldo_posterior, observacao, id_usuario
                        )
                        VALUES (%s, 0, %s, 0, %s, %s, %s)
                    """, (id_novo, saldo, saldo, 'Saldo inicial no cadastro', current_user.id))

                if id_fornecedor and preco:
                    preco_float = float(str(preco).replace(',', '.'))
                    databaseOBJ.writeRaw("""
                        INSERT INTO valor_de_compra (id_produto, id_fornecedor, preco_ultima_compra)
                        VALUES (%s, %s, %s)
                    """, (id_novo, id_fornecedor, preco_float))

            return jsonify({"success": True, "codigo": codigo_limpo})

        except Exception as e:
            print("Erro crítico de inserção:", e)
            return jsonify({"success": False, "error": "Erro interno ao salvar produto."})

    # ✏️ EDITAR
    if request.method == 'PUT':

        id_produto = request.values.get('id')
        nome = (request.values.get('nome') or '').strip()
        codigo_bruto = request.values.get('codigo') or ''
        saldo_str = request.values.get('saldo', '0')
        estoque_minimo_str = request.values.get('estoque_minimo', '0')
        localizacao = (request.values.get('localizacao') or '').strip()

        try:
            id_produto = int(id_produto)
            novo_saldo = float(str(saldo_str).replace(',', '.'))
            estoque_minimo = float(str(estoque_minimo_str).replace(',', '.'))
            if novo_saldo < 0 or estoque_minimo < 0:
                return jsonify({"success": False, "error": "Saldo e estoque mínimo não podem ser negativos."})
        except Exception:
            return jsonify({"success": False, "error": "Dados inválidos enviados para edição do produto."})

        codigo_limpo = limpar_codigo_barras(codigo_bruto)
        if not codigo_limpo or codigo_limpo.upper() in ("SEM CODIGO", "SEM CÓDIGO", "-"):
            codigo_limpo = gerar_ean13_interno(id_produto)
        else:
            validacao = interpretar_codigo_barras(codigo_limpo)
            if not validacao["valido"]:
                return jsonify({"success": False, "error": validacao["erro"]})
            codigo_limpo = validacao["codigo_produto"]

        existe = databaseOBJ.readRaw("""
            SELECT nome, codigo
            FROM produtos
            WHERE ativo = true
            AND codigo = %s
            AND id <> %s
            LIMIT 1
        """, (codigo_limpo, id_produto), realdict=True)

        if existe:
            conflito = existe[0]
            mensagem_erro = f"Conflito! O código '{conflito['codigo']}' já está sendo usado pelo produto: {conflito['nome']}."
            return jsonify({
                "success": False,
                "error": mensagem_erro
            })

        # Consulta o saldo anterior para registrar ajuste no histórico imutável se houver diferença
        atual_rows = databaseOBJ.readRaw(
            "SELECT saldo FROM produtos WHERE id = %s LIMIT 1;",
            (id_produto,),
            realdict=True
        )
        saldo_anterior = float(atual_rows[0]['saldo'] or 0) if atual_rows else 0.0

        databaseOBJ.writeRaw("""
            UPDATE produtos
            SET nome = %s,
                codigo = %s,
                saldo = %s,
                estoque_minimo = %s,
                localizacao = %s
            WHERE id = %s
        """, (nome, codigo_limpo, novo_saldo, estoque_minimo, localizacao, id_produto))

        # Se o saldo foi modificado diretamente na edição, registra um log imutável de Ajuste (operacao = 2)
        diferenca = round(novo_saldo - saldo_anterior, 2)
        if abs(diferenca) > 0:
            databaseOBJ.writeRaw("""
                INSERT INTO movimentacoes_estoque (
                    id_produto, operacao, quantidade, saldo_anterior, saldo_posterior, observacao, id_usuario
                )
                VALUES (%s, 2, %s, %s, %s, %s, %s)
            """, (
                id_produto,
                abs(diferenca),
                saldo_anterior,
                novo_saldo,
                f"Ajuste manual no cadastro ({'+' if diferenca > 0 else ''}{diferenca:g})",
                current_user.id
            ))

        # Processa a lista de preços atualizados vindos da tabela
        precos_json = request.values.get('precos_fornecedores')
        if precos_json:
            try:
                lista_precos = json.loads(precos_json)
                for item in lista_precos:
                    id_forn = item.get('id_fornecedor')
                    preco_novo = item.get('preco')
                    if id_forn and preco_novo:
                        databaseOBJ.writeRaw("""
                            INSERT INTO valor_de_compra (id_produto, id_fornecedor, preco_ultima_compra)
                            VALUES (%s, %s, %s)
                        """, (id_produto, id_forn, float(str(preco_novo).replace(',', '.'))))
            except Exception as e:
                print("Erro ao atualizar preços em lote:", e)

        return jsonify({"success": True})

    # 🗑 EXCLUIR (Soft Delete / Inativar)
    if request.method == 'DELETE':

        id_produto = request.values.get('id')
        databaseOBJ.writeRaw("""
            UPDATE produtos 
            SET ativo = FALSE
            WHERE id = %s
        """, (id_produto,))

        return jsonify({"success": True})

@app.route('/registrar_movimentacao', methods=['POST'])
@login_required
def registrar_movimentacao():
    """
    Registra movimentações no estoque com log de auditoria imutável:
    - operacao = 0: Entrada (soma ao saldo atual)
    - operacao = 1: Saída / Retirada (subtrai do saldo atual com trava de saldo insuficiente)
    - operacao = 2: Ajuste de Inventário (define o novo saldo exato e registra a diferença)
    Retorna alertas automáticos caso o produto atinja nível crítico ou de atenção.
    """
    id_produto = request.form.get('id_produto')
    quantidade = request.form.get('quantidade')
    operacao = request.form.get('operacao', '1')
    observacao = (request.form.get('observacao') or '').strip()

    try:
        id_produto = int(id_produto)
        qtd_informada = float(str(quantidade).replace(',', '.'))
        operacao = int(operacao)
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Dados numéricos inválidos enviados pelo formulário."
        }), 400

    if operacao not in (0, 1, 2):
        return jsonify({"success": False, "error": "Tipo de operação inválido."}), 400

    # Operadores (nível 1) realizam baixas; entradas e ajustes de inventário exigem nível >= 2 (ou fluxo de produção)
    if operacao == 2 and current_user.privileges < 2:
        return jsonify({"success": False, "error": "Apenas supervisores/administradores podem realizar ajustes de inventário."}), 403

    produto = databaseOBJ.readRaw("""
        SELECT id, nome, codigo, COALESCE(saldo, 0) AS saldo, COALESCE(estoque_minimo, 0) AS estoque_minimo
        FROM produtos
        WHERE ativo = true AND id = %s
    """, (id_produto,), realdict=True)

    if not produto:
        return jsonify({"success": False, "error": "Produto não encontrado ou inativo."})

    prod_info = produto[0]
    saldo_atual = float(prod_info['saldo'])
    estoque_minimo = float(prod_info['estoque_minimo'])

    if operacao == 1:
        # SAÍDA
        if qtd_informada <= 0:
            return jsonify({"success": False, "error": "A quantidade de saída deve ser maior que zero."})
        if qtd_informada > saldo_atual:
            saldo_tela = int(saldo_atual) if saldo_atual.is_integer() else saldo_atual
            return jsonify({
                "success": False,
                "error": f"Saldo insuficiente! O produto possui {saldo_tela} unidade(s) no estoque."
            })
        saldo_posterior = saldo_atual - qtd_informada
        qtd_registrada = qtd_informada
        obs_padrao = observacao or "Saída registrada"

    elif operacao == 0:
        # ENTRADA
        if qtd_informada <= 0:
            return jsonify({"success": False, "error": "A quantidade de entrada deve ser maior que zero."})
        saldo_posterior = saldo_atual + qtd_informada
        qtd_registrada = qtd_informada
        obs_padrao = observacao or "Entrada de estoque"

    else:
        # AJUSTE DE INVENTÁRIO (operacao == 2): qtd_informada representa o NOVO SALDO contado no inventário
        if qtd_informada < 0:
            return jsonify({"success": False, "error": "O novo saldo do inventário não pode ser negativo."})
        diferenca = round(qtd_informada - saldo_atual, 2)
        if abs(diferenca) == 0:
            return jsonify({"success": False, "error": "O saldo informado já é igual ao saldo atual em estoque."})
        saldo_posterior = qtd_informada
        qtd_registrada = abs(diferenca)
        sinal = "+" if diferenca > 0 else ""
        obs_padrao = observacao or f"Ajuste de inventário ({sinal}{diferenca:g})"

    id_usuario = current_user.id

    try:
        # 1. Insere no log imutável de movimentações
        databaseOBJ.writeRaw("""
            INSERT INTO movimentacoes_estoque (
                id_produto, operacao, quantidade, saldo_anterior, saldo_posterior, observacao, id_usuario
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            id_produto,
            operacao,
            qtd_registrada,
            saldo_atual,
            saldo_posterior,
            obs_padrao[:255],
            id_usuario
        ))

        # 2. Atualiza o saldo consolidado do produto
        databaseOBJ.writeRaw("""
            UPDATE produtos
            SET saldo = %s
            WHERE id = %s
        """, (saldo_posterior, id_produto))

    except Exception as e:
        print("Erro ao registrar movimentacao:", e)
        return jsonify({
            "success": False,
            "error": "Erro interno ao atualizar o estoque."
        }), 500

    # 3. Verifica alertas automáticos de estoque mínimo/crítico
    alerta_estoque = None
    if estoque_minimo > 0 and saldo_posterior < estoque_minimo:
        alerta_estoque = {
            "nivel": "critico",
            "mensagem": f"ALERTA CRÍTICO: O saldo de '{prod_info['nome']}' ({saldo_posterior:g}) ficou abaixo do estoque mínimo ({estoque_minimo:g})!"
        }
    elif estoque_minimo > 0 and saldo_posterior <= estoque_minimo * 1.5:
        alerta_estoque = {
            "nivel": "atencao",
            "mensagem": f"Atenção: O produto '{prod_info['nome']}' entrou na faixa de segurança ({saldo_posterior:g} un. / mín: {estoque_minimo:g})."
        }

    return jsonify({
        "success": True,
        "saldo_anterior": saldo_atual,
        "saldo_atual": saldo_posterior,
        "estoque_minimo": estoque_minimo,
        "alerta_estoque": alerta_estoque
    })

######################################## IMPORTAÇÃO EM LOTE (EXCEL / CSV) ########################################

def normalizar_chave_coluna(texto):
    """Remove acentos, espaços extras e converte para minúsculo para mapear colunas de planilhas com flexibilidade"""
    if not texto:
        return ""
    sem_acentos = ''.join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'[^a-z0-9]+', '_', sem_acentos.lower()).strip('_')

def forcar_celula_para_texto(valor_celula, eh_coluna_codigo=False):
    """
    Garante que o valor lido de uma célula Excel (.xlsx) ou CSV seja convertido de forma
    estrita e segura para String (Texto), impedindo que códigos de barras longos (12-14 dígitos)
    sejam corrompidos por conversão float (.0) ou notação científica (7,8984E+12 / 7.8984E+12).
    """
    if valor_celula is None or isinstance(valor_celula, bool):
        return ""

    if isinstance(valor_celula, int):
        return str(valor_celula)

    if isinstance(valor_celula, (float, Decimal)):
        try:
            d = Decimal(str(valor_celula))
            if d == d.to_integral_value():
                return str(int(d))
            if eh_coluna_codigo:
                return format(d, 'f').split('.')[0]
            return format(d.normalize(), 'f')
        except (InvalidOperation, ValueError):
            return str(valor_celula).strip()

    texto = str(valor_celula).strip()
    if not texto:
        return ""

    if eh_coluna_codigo:
        return limpar_codigo_barras(texto)

    # Mesmo antes de saber o índice da coluna, se for um inteiro longo em float/notação científica (>= 8 dígitos), preserva como inteiro
    if re.match(r'^\d{8,}[.,]0+$', texto):
        return re.split(r'[.,]', texto)[0]

    return texto

def detectar_notacao_cientifica_truncada(valor_bruto):
    """
    Identifica se o Excel corrompeu um código EAN-13 ao salvar em CSV (ex: '7,8984E+12' ou '7,89145E+12'),
    onde os últimos dígitos foram descartados pelo Excel e viraram zeros ('7898400000000').
    """
    if valor_bruto is None:
        return False
    texto = str(valor_bruto).strip().strip('"').strip("'")
    match = re.match(r'^[+-]?(\d+)(?:[.,](\d+))?[eE][+-]?(\d+)$', texto)
    if not match:
        return False
    parte_inteira, parte_decimal, expoente = match.group(1), (match.group(2) or ""), int(match.group(3))
    digitos_significativos = len(parte_inteira + parte_decimal)
    # Em um EAN-13 (expoente 12 -> 13 dígitos), se a mantissa tiver menos de 12 dígitos significativos, o Excel truncou o final!
    return expoente >= 8 and digitos_significativos <= expoente

def ler_linhas_xlsx(arquivo_bytes):
    """
    Lê planilhas Excel (.xlsx) nativas retornando uma lista de listas de strings.
    Inspeciona cada célula (values_only=False) para forçar leitura textual exata de números inteiros/códigos,
    evitando totalmente problemas de delimitador (; vs ,) e de notação científica.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(arquivo_bytes), data_only=True)
        ws = wb.active
        linhas = []
        for row in ws.iter_rows(values_only=False):
            linha_str = []
            for cell in row:
                val = cell.value
                if val is None:
                    linha_str.append("")
                elif cell.data_type == 's':
                    linha_str.append(str(val).strip())
                elif isinstance(val, (int, float, Decimal)):
                    linha_str.append(forcar_celula_para_texto(val, eh_coluna_codigo=False))
                else:
                    linha_str.append(str(val).strip())
            linhas.append(linha_str)
        return linhas
    except ImportError:
        pass

    # Fallback nativo via zipfile + xml.etree.ElementTree (sem dependências externas)
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    with zipfile.ZipFile(io.BytesIO(arquivo_bytes)) as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root_ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root_ss.findall(f'{ns}si'):
                textos = [t.text or '' for t in si.iter(f'{ns}t')]
                shared_strings.append(''.join(textos))

        sheet_files = sorted([f for f in z.namelist() if f.startswith('xl/worksheets/sheet') and f.endswith('.xml')])
        if not sheet_files:
            raise ValueError("Nenhuma aba de dados encontrada no arquivo .xlsx.")

        root_sheet = ET.fromstring(z.read(sheet_files[0]))
        linhas = []

        def col_para_indice(ref_celula):
            letras = ''.join(ch for ch in ref_celula if ch.isalpha()).upper()
            idx = 0
            for ch in letras:
                idx = idx * 26 + (ord(ch) - ord('A') + 1)
            return max(idx - 1, 0)

        for row_el in root_sheet.iter(f'{ns}row'):
            celulas_dict = {}
            max_col = -1
            for idx_seq, c_el in enumerate(row_el.findall(f'{ns}c')):
                ref = c_el.attrib.get('r', '')
                col_idx = col_para_indice(ref) if ref else idx_seq
                max_col = max(max_col, col_idx)

                tipo = c_el.attrib.get('t', '')
                v_el = c_el.find(f'{ns}v')
                is_el = c_el.find(f'{ns}is')

                valor = ''
                if tipo == 's' and v_el is not None and v_el.text and v_el.text.isdigit():
                    s_idx = int(v_el.text)
                    valor = shared_strings[s_idx] if s_idx < len(shared_strings) else ''
                elif tipo == 'inlineStr' and is_el is not None:
                    valor = ''.join(t.text or '' for t in is_el.iter(f'{ns}t'))
                elif v_el is not None and v_el.text is not None:
                    valor_raw = v_el.text.strip()
                    # Se for número em notação científica no XML interno do Excel, converte com precisão Decimal
                    if re.match(r'^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$', valor_raw):
                        try:
                            d = Decimal(valor_raw)
                            valor = str(int(d)) if d == d.to_integral_value() else format(d.normalize(), 'f')
                        except (InvalidOperation, ValueError):
                            valor = valor_raw
                    else:
                        valor = valor_raw

                celulas_dict[col_idx] = str(valor).strip()

            if max_col >= 0:
                linhas.append([celulas_dict.get(i, '') for i in range(max_col + 1)])
        return linhas

def detectar_delimitador_csv(linhas_amostra):
    """
    Sniffer inteligente para arquivos CSV gerados pelo MS Excel (PT-BR ou Internacional):
    1. Analisa a linha de cabeçalho e as primeiras linhas de dados.
    2. Evita falsos positivos quando a descrição do produto contém vírgulas (ex: '115x1,0x22,23mm').
    3. Prioriza ';' (padrão Excel PT-BR) ou o delimitador que mantém contagem consistente de colunas.
    """
    if not linhas_amostra:
        return ';'

    candidatos = [';', ',', '\t', '|']
    melhor_delim = ';'
    melhor_score = -1

    for delim in candidatos:
        contagens = []
        for linha in linhas_amostra[:15]:
            try:
                parsed = next(csv.reader([linha], delimiter=delim))
                contagens.append(len(parsed))
            except Exception:
                pass

        if not contagens or contagens[0] < 2:
            continue

        cols_cabecalho = contagens[0]
        linhas_consistentes = sum(1 for c in contagens if c == cols_cabecalho)
        # Bônus para ';' (padrão nativo do Excel PT-BR) em caso de empate
        bonus_ptbr = 0.5 if delim == ';' else 0.0
        score = (linhas_consistentes * 10) + min(cols_cabecalho, 15) + bonus_ptbr

        if score > melhor_score:
            melhor_score = score
            melhor_delim = delim

    if melhor_score > 0:
        return melhor_delim

    # Fallback para csv.Sniffer nativo do Python
    try:
        amostra_texto = '\n'.join(linhas_amostra[:10])
        dialect = csv.Sniffer().sniff(amostra_texto, delimiters=';,\t|')
        return dialect.delimiter
    except Exception:
        return ';'

def ler_linhas_csv(arquivo_bytes):
    """
    Lê arquivos CSV com detecção automática de codificação (UTF-8 com/sem BOM, CP1252/Excel Windows, Latin-1)
    e sniffer de delimitador (';', ',' ou '\\t'), tratando inclusive linhas inteiras entre aspas geradas pelo Excel.
    """
    texto = None
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            texto = arquivo_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if texto is None:
        texto = arquivo_bytes.decode('utf-8', errors='replace')

    linhas_brutas = [l.strip() for l in texto.splitlines() if l.strip()]
    if not linhas_brutas:
        return []

    delimitador = detectar_delimitador_csv(linhas_brutas)
    leitor = csv.reader(io.StringIO(texto), delimiter=delimitador)

    linhas_processadas = []
    for row in leitor:
        # Caso especial do Excel: linha inteira envolvida em aspas contendo ';' interno (ex: '"Produto;7891345535684;10"')
        if len(row) == 1 and ';' in row[0]:
            sub_row = next(csv.reader([row[0]], delimiter=';'))
            if len(sub_row) > 1:
                row = sub_row
        linhas_processadas.append([str(c).strip() for c in row])

    return linhas_processadas

@app.route('/modelo_planilha_produtos', methods=['GET'])
@login_required
def modelo_planilha_produtos():
    """
    Gera uma planilha modelo nativa em formato Excel (.xlsx) com as colunas 'Código' e 'Código de Barras'
    pré-formatadas explicitamente como Texto ('@'), impedindo que o Excel converta EAN-13 para notação científica.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Importacao_Estoque"

        cabecalho = [
            "Código",
            "Produto",
            "Código de Barras",
            "Saldo Atual",
            "Estoque Mínimo",
            "Localização",
            "Fornecedor",
            "Preço (R$)"
        ]
        ws.append(cabecalho)

        exemplos = [
            ["INT-00001", "DISCO DE CORTE FINO - AÇO INOX - 115x1,0x22,23mm", "7891345535684", 50, 15, "Corredor A - Prat. 02", "Fornecedor Exemplo Ltda", 12.50],
            ["INT-00002", "THINNER PU - LATA 5L", "7901094100139", 20, 10, "Químicos - B1", "Distribuidora Tintas", 89.90],
            ["", "BOINA DUPLA FACE BRANCA 7 POLEGADAS", "SEM CODIGO", 12, 5, "Polimento - C3", "Auto Peças Brasil", 45.00]
        ]

        for linha_ex in exemplos:
            ws.append(linha_ex)

        # Estilização do cabeçalho (Preto Corporativo #121316 com texto Branco)
        header_fill = PatternFill(start_color="121316", end_color="121316", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for col_idx in range(1, len(cabecalho) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Pré-formata as colunas A (Código) e C (Código de Barras) estritamente como TEXTO ('@') até a linha 500
        for r_idx in range(2, 502):
            cell_cod = ws.cell(row=r_idx, column=1)
            cell_barras = ws.cell(row=r_idx, column=3)
            cell_cod.number_format = '@'
            cell_barras.number_format = '@'
            if cell_cod.value is not None:
                cell_cod.value = str(cell_cod.value)
                cell_cod.data_type = 's'
            if cell_barras.value is not None:
                cell_barras.value = str(cell_barras.value)
                cell_barras.data_type = 's'

        larguras = [16, 48, 22, 15, 16, 24, 28, 15]
        for i, larg in enumerate(larguras, start=1):
            col_letter = openpyxl.utils.get_column_letter(i)
            ws.column_dimensions[col_letter].width = larg

        buffer_xlsx = io.BytesIO()
        wb.save(buffer_xlsx)
        buffer_xlsx.seek(0)

        return Response(
            buffer_xlsx.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=modelo_importacao_estoque.xlsx"}
        )
    except ImportError:
        # Fallback CSV caso openpyxl não esteja instalado no ambiente
        output = io.StringIO(newline="")
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';')
        writer.writerow(["Código", "Produto", "Código de Barras", "Saldo Atual", "Estoque Mínimo", "Localização", "Fornecedor", "Preço (R$)"])
        writer.writerow(["INT-00001", "DISCO DE CORTE FINO - AÇO INOX - 115x1,0x22,23mm", '="7891345535684"', "50", "15", "Corredor A - Prat. 02", "Fornecedor Exemplo Ltda", "12,50"])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=modelo_importacao_estoque.csv"}
        )

PLACEHOLDERS_CODIGO = {
    "", "-", "SEM CODIGO", "SEM CÓDIGO", "S/ CODIGO", "S/ CÓDIGO",
    "S/C", "SEM BARRAS", "NAO TEM", "NÃO TEM", "NAO POSSUI", "NÃO POSSUI",
    "N/A", "NA", "NULL", "NONE", "0"
}

def eh_placeholder_codigo(valor):
    if valor is None:
        return True
    return str(valor).strip().upper() in PLACEHOLDERS_CODIGO

def parece_descricao_de_produto(texto):
    """Detecta se uma string contém uma descrição textual de produto (ex: possui espaços e palavras) em vez de um código"""
    if not texto or eh_placeholder_codigo(texto):
        return False
    t = str(texto).strip()
    # Se possui espaços e pelo menos 3 letras (ex: 'DISCO DE CORTE...'), é uma descrição de produto
    letras = sum(1 for c in t if c.isalpha())
    return (' ' in t and letras >= 3) or len(t) > 36

def parece_codigo_de_barras_ou_interno(texto):
    """Verifica se uma string tem estrutura típica de código de barras (EAN/GTIN/Interno sem espaços) ou placeholder"""
    if not texto or eh_placeholder_codigo(texto):
        return True
    limpo = limpar_codigo_barras(texto)
    return bool(re.match(r'^[A-Za-z0-9\-_.]{3,36}$', limpo)) and (' ' not in limpo)

@app.route('/importar_planilha_produtos', methods=['POST'])
@login_required
@privilege_required(2)
def importar_planilha_produtos():
    """
    Endpoint seguro para importação em lote de produtos via Excel (.xlsx) ou CSV (.csv):
    1. Prioriza arquivos nativos .xlsx (evitando erros de delimitador e notação científica do Excel).
    2. Força a leitura das colunas 'Código de Barras' e 'Código' estritamente como String (Texto).
    3. Mantém fallback inteligente para CSV com sniffer de delimitador (';', ',' ou '\\t').
    4. Valida e protege o mapeamento entre 'Nome/Descrição', 'Código de Barras' e 'Código'.
    """
    if 'arquivo' not in request.files:
        return jsonify({"success": False, "error": "Nenhum arquivo enviado."}), 400

    arquivo = request.files['arquivo']
    nome_arquivo = (arquivo.filename or '').strip()
    if not nome_arquivo:
        return jsonify({"success": False, "error": "Selecione um arquivo .xlsx ou .csv válido."}), 400

    extensao = os.path.splitext(nome_arquivo.lower())[1]
    if extensao not in ('.xlsx', '.csv'):
        return jsonify({
            "success": False,
            "error": "Formato não suportado! Envie uma planilha Excel (.xlsx — recomendado) ou arquivo CSV (.csv)."
        }), 400

    try:
        conteudo = arquivo.read()
        if not conteudo:
            return jsonify({"success": False, "error": "O arquivo enviado está vazio."}), 400

        # Detecta inclusive se o arquivo tem assinatura ZIP (PK\x03\x04 de um .xlsx) mesmo que renomeado
        eh_xlsx_binario = (extensao == '.xlsx') or conteudo.startswith(b'PK\x03\x04')
        linhas = ler_linhas_xlsx(conteudo) if eh_xlsx_binario else ler_linhas_csv(conteudo)
    except Exception as e:
        print("Erro ao ler planilha:", e)
        return jsonify({"success": False, "error": f"Não foi possível ler o arquivo enviado: {str(e)}"}), 400

    # Filtra linhas completamente vazias
    linhas_validas = [r for r in linhas if any(str(c).strip() for c in r)]
    if len(linhas_validas) < 2:
        return jsonify({
            "success": False,
            "error": "A planilha deve conter a linha de cabeçalho e pelo menos 1 linha de produto."
        }), 400

    # Mapeamento rigoroso e separado de 'nome', 'codigo_barras' e 'codigo'
    # Nota: 'item' NÃO é incluído em 'nome' pois em planilhas brasileiras representa o nº sequencial (1, 2, 3...)
    ALIASES_COLUNAS = {
        "nome": {
            "produto", "produtos", "nome", "descricao", "descricao_do_produto",
            "descricao_produto", "nome_do_produto", "nome_produto", "denominacao",
            "material", "mercadoria", "especificacao"
        },
        "codigo_barras": {
            "codigo_de_barras", "codigo_barras", "cod_de_barras", "cod_barras",
            "ean", "ean13", "ean_13", "gtin", "barcode", "cod_ean"
        },
        "codigo": {
            "codigo", "cod", "codigo_produto", "codigo_do_produto", "cod_produto",
            "codigo_interno", "cod_interno", "sku", "referencia", "ref", "peca_n", "peca_numero"
        },
        "saldo": {
            "saldo", "saldo_atual", "quantidade", "qtd", "qtde",
            "estoque", "estoque_atual", "saldo_inicial", "saldo_estoque"
        },
        "estoque_minimo": {
            "estoque_minimo", "minimo", "qtd_minima", "saldo_minimo",
            "ponto_de_pedido", "estoque_min", "min"
        },
        "localizacao": {
            "localizacao", "endereco", "prateleira", "setor", "local", "corredor", "posicao"
        },
        "fornecedor": {
            "fornecedor", "fornecedor_menor_preco", "fornecedor_1", "empresa_fornecedora", "marca"
        },
        "preco": {
            "preco", "menor_preco_r", "menor_preco", "preco_1_r", "preco_r",
            "valor", "valor_unitario", "custo", "preco_ultima_compra", "preco_de_compra"
        }
    }

    # Localiza a linha de cabeçalho (caso a planilha tenha linhas de título no topo antes da tabela)
    indice_linha_cabecalho = 0
    indices = {}
    cabecalho_bruto = linhas_validas[0]

    for idx_candidato in range(min(5, len(linhas_validas))):
        cand_bruto = linhas_validas[idx_candidato]
        cand_norm = [normalizar_chave_coluna(c) for c in cand_bruto]
        cand_indices = {}
        for campo, sinonimos in ALIASES_COLUNAS.items():
            for col_i, col_norm in enumerate(cand_norm):
                if col_norm in sinonimos and col_i not in cand_indices.values():
                    cand_indices[campo] = col_i
                    break
        if "nome" in cand_indices or ("codigo" in cand_indices and len(cand_bruto) >= 2):
            indice_linha_cabecalho = idx_candidato
            cabecalho_bruto = cand_bruto
            indices = cand_indices
            break

    # Fallback se apenas "codigo" foi encontrado e a planilha tem 2+ colunas onde a outra coluna é a descrição
    if "nome" not in indices and len(cabecalho_bruto) == 2 and ("codigo" in indices or "codigo_barras" in indices):
        col_usada = indices.get("codigo_barras", indices.get("codigo", 0))
        indices["nome"] = 1 if col_usada == 0 else 0

    if "nome" not in indices:
        return jsonify({
            "success": False,
            "error": (
                f"Coluna obrigatória de Descrição/Produto não encontrada no cabeçalho ({', '.join(cabecalho_bruto)}). "
                "Certifique-se de que a planilha possui uma coluna chamada 'Produto', 'Nome' ou 'Descrição'."
            )
        }), 400

    inseridos = 0
    atualizados = 0
    erros = []
    avisos_notacao = 0

    prox_id_query = databaseOBJ.readRaw("SELECT COALESCE(MAX(id), 0) + 1 FROM produtos;")
    seq_ean = int(prox_id_query[0][0]) if prox_id_query else 1
    codigos_usados_no_lote = set()

    def obter_valor_celula(row, campo, padrao="", como_codigo=False):
        idx = indices.get(campo)
        if idx is not None and idx < len(row):
            return forcar_celula_para_texto(row[idx], eh_coluna_codigo=como_codigo)
        return padrao

    def converter_numero(val_str, padrao=None):
        if val_str is None or str(val_str).strip() in ("", "-"):
            return padrao
        limpo = str(val_str).replace("R$", "").replace(" ", "").strip()
        if "," in limpo and "." in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        else:
            limpo = limpo.replace(",", ".")
        return float(limpo)

    for OffsetLinha, row in enumerate(linhas_validas[indice_linha_cabecalho + 1:]):
        num_linha = indice_linha_cabecalho + 2 + OffsetLinha

        nome_bruto = obter_valor_celula(row, "nome", como_codigo=False)
        cod_barras_raw = obter_valor_celula(row, "codigo_barras", como_codigo=False)
        cod_simples_raw = obter_valor_celula(row, "codigo", como_codigo=False)

        # Prioriza 'Código de Barras' sobre 'Código'; se 'Código de Barras' estiver vazio/placeholder, usa 'Código'
        if cod_barras_raw and not eh_placeholder_codigo(cod_barras_raw):
            codigo_raw_escolhido = cod_barras_raw
        else:
            codigo_raw_escolhido = cod_simples_raw or cod_barras_raw

        # Proteção contra inversão de colunas na planilha (ex: Descrição colocada na coluna Código e Código na coluna Produto)
        if parece_descricao_de_produto(codigo_raw_escolhido) and parece_codigo_de_barras_ou_interno(nome_bruto):
            nome_bruto, codigo_raw_escolhido = codigo_raw_escolhido, nome_bruto

        nome = str(nome_bruto or "").strip()
        if not nome or nome == "-":
            continue

        # Verifica se o código veio truncado por notação científica do CSV do Excel (ex: '7,89145E+12')
        veio_notacao_truncada = detectar_notacao_cientifica_truncada(codigo_raw_escolhido)
        codigo_limpo = forcar_celula_para_texto(codigo_raw_escolhido, eh_coluna_codigo=True)
        codigo_eh_placeholder = eh_placeholder_codigo(codigo_limpo)

        # Se a célula de código contiver uma descrição/observação com espaços ou se foi truncada pelo CSV do Excel
        if not codigo_eh_placeholder:
            if veio_notacao_truncada:
                avisos_notacao += 1
                # Se já houve outro item no lote com o mesmo prefixo truncado (ex: vários '7,89145E+12'), trata como placeholder para não colidir
                if codigo_limpo in codigos_usados_no_lote:
                    codigo_eh_placeholder = True
            else:
                validacao = interpretar_codigo_barras(codigo_limpo)
                if validacao["valido"]:
                    codigo_limpo = validacao["codigo_produto"]
                else:
                    # Tenta sanitizar caracteres especiais (como barras ou espaços em códigos internos)
                    codigo_sanitizado = re.sub(r'[^A-Za-z0-9\-_.]', '-', codigo_limpo).strip('-_.')
                    if 3 <= len(codigo_sanitizado) <= 35 and not parece_descricao_de_produto(codigo_limpo):
                        codigo_limpo = codigo_sanitizado
                    else:
                        # Se o usuário escreveu texto livre/descrição na coluna de código, gera EAN-13 interno sem abortar a linha
                        codigo_eh_placeholder = True

        try:
            saldo_planilha = converter_numero(obter_valor_celula(row, "saldo"), padrao=None)
            minimo_planilha = converter_numero(obter_valor_celula(row, "estoque_minimo"), padrao=None)
            preco_planilha = converter_numero(obter_valor_celula(row, "preco"), padrao=None)
        except ValueError:
            erros.append(f"Linha {num_linha} ({nome[:30]}): Valores numéricos inválidos de saldo, mínimo ou preço.")
            continue

        if (saldo_planilha is not None and saldo_planilha < 0) or (minimo_planilha is not None and minimo_planilha < 0):
            erros.append(f"Linha {num_linha} ({nome[:30]}): Saldo ou estoque mínimo negativo não permitido.")
            continue

        localizacao_planilha = obter_valor_celula(row, "localizacao")
        if localizacao_planilha == "-":
            localizacao_planilha = ""
        fornecedor_planilha = obter_valor_celula(row, "fornecedor")
        if fornecedor_planilha == "-":
            fornecedor_planilha = ""

        # Busca se o produto já existe:
        # Se o código veio truncado por notação científica do CSV (7,89145E+12), busca primeiro pelo NOME para não confundir produtos da mesma marca!
        produto_existente = []
        if not codigo_eh_placeholder and not veio_notacao_truncada:
            produto_existente = databaseOBJ.readRaw("""
                SELECT id, nome, codigo, COALESCE(saldo, 0) AS saldo, COALESCE(estoque_minimo, 0) AS estoque_minimo, localizacao
                FROM produtos
                WHERE codigo = %s
                ORDER BY ativo DESC, id DESC
                LIMIT 1
            """, (codigo_limpo,), realdict=True)

        if not produto_existente:
            produto_existente = databaseOBJ.readRaw("""
                SELECT id, nome, codigo, COALESCE(saldo, 0) AS saldo, COALESCE(estoque_minimo, 0) AS estoque_minimo, localizacao
                FROM produtos
                WHERE LOWER(TRIM(nome)) = LOWER(TRIM(%s))
                ORDER BY ativo DESC, id DESC
                LIMIT 1
            """, (nome,), realdict=True)

        if produto_existente:
            # ATUALIZAR PRODUTO EXISTENTE
            prod = produto_existente[0]
            id_prod = prod['id']
            saldo_ant = float(prod['saldo'] or 0)
            novo_saldo = saldo_planilha if saldo_planilha is not None else saldo_ant
            novo_minimo = minimo_planilha if minimo_planilha is not None else float(prod['estoque_minimo'] or 0)
            nova_loc = localizacao_planilha if localizacao_planilha else (prod.get('localizacao') or '')

            codigo_atual = prod.get('codigo') or ''
            # Se o código na planilha era válido e NÃO veio truncado por notação científica, atualiza; caso contrário, preserva o código íntegro do banco
            if not codigo_eh_placeholder and not veio_notacao_truncada:
                novo_codigo = codigo_limpo
            elif not codigo_atual or eh_placeholder_codigo(codigo_atual):
                novo_codigo = gerar_ean13_interno(id_prod)
            else:
                novo_codigo = codigo_atual

            codigos_usados_no_lote.add(novo_codigo)

            ok = databaseOBJ.writeRaw("""
                UPDATE produtos
                SET nome = %s,
                    codigo = %s,
                    saldo = %s,
                    estoque_minimo = %s,
                    localizacao = %s,
                    ativo = true
                WHERE id = %s
            """, (nome, novo_codigo, novo_saldo, novo_minimo, nova_loc, id_prod))

            if ok:
                atualizados += 1
                diferenca = round(novo_saldo - saldo_ant, 2)
                if abs(diferenca) > 0:
                    databaseOBJ.writeRaw("""
                        INSERT INTO movimentacoes_estoque (
                            id_produto, operacao, quantidade, saldo_anterior, saldo_posterior, observacao, id_usuario
                        )
                        VALUES (%s, 2, %s, %s, %s, %s, %s)
                    """, (
                        id_prod,
                        abs(diferenca),
                        saldo_ant,
                        novo_saldo,
                        f"Importação via planilha ({'+' if diferenca > 0 else ''}{diferenca:g})",
                        current_user.id
                    ))
            else:
                erros.append(f"Linha {num_linha} ({nome[:30]}): Falha ao atualizar registro no banco.")
                continue

        else:
            # INSERIR NOVO PRODUTO
            # Se for placeholder, notação científica truncada ou código já existente em outro produto ativo, gera EAN-13 interno único
            precisa_gerar_ean = codigo_eh_placeholder or veio_notacao_truncada
            if not precisa_gerar_ean:
                ja_em_uso = databaseOBJ.readRaw("SELECT 1 FROM produtos WHERE codigo = %s LIMIT 1;", (codigo_limpo,))
                if ja_em_uso or (codigo_limpo in codigos_usados_no_lote):
                    precisa_gerar_ean = True

            if precisa_gerar_ean:
                while True:
                    candidato = gerar_ean13_interno(seq_ean)
                    seq_ean += 1
                    if candidato not in codigos_usados_no_lote and not databaseOBJ.readRaw("SELECT 1 FROM produtos WHERE codigo = %s LIMIT 1;", (candidato,)):
                        codigo_limpo = candidato
                        break

            codigos_usados_no_lote.add(codigo_limpo)
            novo_saldo = saldo_planilha if saldo_planilha is not None else 0.0
            novo_minimo = minimo_planilha if minimo_planilha is not None else 0.0

            ok = databaseOBJ.writeRaw("""
                INSERT INTO produtos (nome, codigo, saldo, estoque_minimo, localizacao, ativo)
                VALUES (%s, %s, %s, %s, %s, true)
            """, (nome, codigo_limpo, novo_saldo, novo_minimo, localizacao_planilha))

            if not ok:
                erros.append(f"Linha {num_linha} ({nome[:30]}): Erro ao inserir no banco de dados.")
                continue

            inseridos += 1
            recem_criado = databaseOBJ.readRaw(
                "SELECT id FROM produtos WHERE codigo = %s ORDER BY id DESC LIMIT 1;",
                (codigo_limpo,),
                realdict=True
            )
            id_prod = recem_criado[0]['id'] if recem_criado else None

            if id_prod and novo_saldo > 0:
                databaseOBJ.writeRaw("""
                    INSERT INTO movimentacoes_estoque (
                        id_produto, operacao, quantidade, saldo_anterior, saldo_posterior, observacao, id_usuario
                    )
                    VALUES (%s, 0, %s, 0, %s, %s, %s)
                """, (
                    id_prod,
                    novo_saldo,
                    novo_saldo,
                    "Carga inicial via importação de planilha",
                    current_user.id
                ))

        # Vincula preço e fornecedor se informados na planilha
        if id_prod and fornecedor_planilha and preco_planilha and preco_planilha > 0:
            forn_rows = databaseOBJ.readRaw(
                "SELECT id FROM fornecedores WHERE LOWER(TRIM(nome)) = LOWER(TRIM(%s)) LIMIT 1;",
                (fornecedor_planilha,),
                realdict=True
            )
            if forn_rows:
                id_forn = forn_rows[0]['id']
            else:
                databaseOBJ.writeRaw(
                    "INSERT INTO fornecedores (nome, ativo) VALUES (%s, true);",
                    (fornecedor_planilha,)
                )
                novo_forn = databaseOBJ.readRaw(
                    "SELECT id FROM fornecedores WHERE LOWER(TRIM(nome)) = LOWER(TRIM(%s)) ORDER BY id DESC LIMIT 1;",
                    (fornecedor_planilha,),
                    realdict=True
                )
                id_forn = novo_forn[0]['id'] if novo_forn else None

            if id_forn:
                databaseOBJ.writeRaw("""
                    INSERT INTO valor_de_compra (id_produto, id_fornecedor, preco_ultima_compra)
                    VALUES (%s, %s, %s)
                """, (id_prod, id_forn, preco_planilha))

    if avisos_notacao > 0:
        erros.insert(
            0,
            f"Atenção: {avisos_notacao} código(s) no CSV estavam em notação científica abreviada pelo Excel (ex: 7,89E+12). "
            "Os produtos foram importados com segurança preservando o código original ou gerando EAN-13 interno. "
            "Para preservar todos os 13 dígitos originais, salve e importe sua planilha no formato Excel (.xlsx)."
        )

    return jsonify({
        "success": True,
        "inseridos": inseridos,
        "atualizados": atualizados,
        "total_processados": inseridos + atualizados,
        "erros_count": len(erros),
        "erros": erros[:15]
    })

############################################### DASHBOARD RESUMIDO ###############################################

@app.route('/api/dashboard_estoque', methods=['GET'])
@login_required
def api_dashboard_estoque():
    """
    Retorna indicadores gerenciais em tempo real para o Dashboard da tela inicial:
    - Resumo Financeiro (Valor total estimado em estoque e custo estimado de reposição)
    - Alertas de Falta / Estoque Crítico e em Atenção
    - Ranking dos Itens Mais Movimentados (Giro de Estoque)
    """
    # 1. Resumo de produtos, status de estoque e valor financeiro baseado no menor preço ativo por item
    produtos = databaseOBJ.readRaw("""
        SELECT 
            p.id,
            p.nome,
            p.codigo,
            COALESCE(p.saldo, 0) AS saldo,
            COALESCE(p.estoque_minimo, 0) AS estoque_minimo,
            COALESCE(p.localizacao, '-') AS localizacao,
            COALESCE((
                SELECT ult.preco_ultima_compra
                FROM (
                    SELECT DISTINCT ON (vc.id_fornecedor)
                        vc.id_fornecedor,
                        vc.preco_ultima_compra,
                        vc.data_modificacao
                    FROM valor_de_compra vc
                    WHERE vc.id_produto = p.id
                    ORDER BY vc.id_fornecedor, vc.data_modificacao DESC
                ) ult
                INNER JOIN fornecedores f ON f.id = ult.id_fornecedor
                WHERE f.ativo = true AND ult.preco_ultima_compra > 0
                ORDER BY ult.preco_ultima_compra ASC, ult.data_modificacao DESC
                LIMIT 1
            ), 0) AS ultimo_preco
        FROM produtos p
        WHERE p.ativo = true
        ORDER BY p.nome
    """, realdict=True)

    total_produtos = len(produtos)
    total_unidades = 0.0
    valor_total_estoque = 0.0
    custo_reposicao_criticos = 0.0

    qtd_criticos = 0
    qtd_atencao = 0
    qtd_ok = 0
    itens_criticos = []

    for p in produtos:
        saldo = float(p['saldo'] or 0)
        minimo = float(p['estoque_minimo'] or 0)
        preco = float(p['ultimo_preco'] or 0)

        total_unidades += saldo
        valor_total_estoque += saldo * preco

        if minimo > 0 and saldo < minimo:
            qtd_criticos += 1
            deficit = minimo - saldo
            custo_reposicao_criticos += deficit * preco
            itens_criticos.append({
                "id": p['id'],
                "nome": p['nome'],
                "codigo": p['codigo'],
                "saldo": saldo,
                "estoque_minimo": minimo,
                "deficit": deficit,
                "localizacao": p['localizacao'],
                "ultimo_preco": preco
            })
        elif minimo > 0 and saldo <= minimo * 1.5:
            qtd_atencao += 1
        else:
            qtd_ok += 1

    # Ordena itens críticos pelo maior déficit percentual
    itens_criticos.sort(key=lambda x: (x['saldo'] / x['estoque_minimo']) if x['estoque_minimo'] > 0 else 1)

    # 2. Itens mais movimentados (Top 6 por volume total movimentado)
    mais_movimentados = databaseOBJ.readRaw("""
        SELECT 
            p.id,
            p.nome,
            p.codigo,
            COUNT(m.id) AS total_operacoes,
            COALESCE(SUM(m.quantidade), 0) AS volume_total,
            COALESCE(SUM(CASE WHEN m.operacao = 1 THEN m.quantidade ELSE 0 END), 0) AS total_saidas,
            COALESCE(SUM(CASE WHEN m.operacao = 0 THEN m.quantidade ELSE 0 END), 0) AS total_entradas
        FROM movimentacoes_estoque m
        INNER JOIN produtos p ON p.id = m.id_produto
        WHERE p.ativo = true
        GROUP BY p.id, p.nome, p.codigo
        ORDER BY volume_total DESC, total_operacoes DESC
        LIMIT 6
    """, realdict=True)

    # 3. Total de movimentações realizadas hoje
    mov_hoje_rows = databaseOBJ.readRaw("""
        SELECT COUNT(id)
        FROM movimentacoes_estoque
        WHERE DATE(data) = CURRENT_DATE;
    """)
    movimentacoes_hoje = int(mov_hoje_rows[0][0]) if mov_hoje_rows else 0

    return jsonify({
        "success": True,
        "kpis": {
            "total_produtos": total_produtos,
            "total_unidades": round(total_unidades, 2),
            "valor_total_estoque": round(valor_total_estoque, 2),
            "custo_reposicao_criticos": round(custo_reposicao_criticos, 2),
            "qtd_criticos": qtd_criticos,
            "qtd_atencao": qtd_atencao,
            "qtd_ok": qtd_ok,
            "movimentacoes_hoje": movimentacoes_hoje
        },
        "itens_criticos": itens_criticos[:10],
        "itens_mais_movimentados": mais_movimentados
    })

#################################################### CLIENTES & PCP ####################################################

@app.route('/adm/clientes')
@login_required
@privilege_required(2)
def adm_clientes():
    return render_template('adm_clientes.html')

@app.route('/clientes', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@privilege_required(2)
def clientes():

    # ==========================
    # GET - LISTAR CLIENTES
    # ==========================
    if request.method == 'GET':

        clientes_lista = databaseOBJ.readRaw("""
            SELECT id, nome, codigo
            FROM clientes
            WHERE visibilidade = true
            ORDER BY nome
        """, realdict=True)

        return jsonify({"clientes": clientes_lista})

    # ADICIONAR
    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()
        codigo = request.form.get('codigo', '').strip()

        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM clientes
            WHERE codigo = %s AND COALESCE(visibilidade, true) = true
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

        id_cli = request.form.get('id')
        nome = request.form.get('nome', '').strip()
        codigo = request.form.get('codigo', '').strip()

        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM clientes
            WHERE codigo = %s
            AND id <> %s
            AND COALESCE(visibilidade, true) = true
        """, (codigo, id_cli), realdict=True)

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
        """, (nome, codigo, id_cli))

        return jsonify({"success": True})

    # ==========================
    # DELETE - EXCLUIR CLIENTE (Soft Delete)
    # ==========================
    elif request.method == 'DELETE':

        id_cliente = request.form.get('id')

        if not id_cliente:
            return abort(400)

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

    valores = databaseOBJ.readRaw(sql, params=tuple(params), realdict=True)

    return jsonify(valores)

@app.route('/dados_ordens', methods=['GET'])
@login_required
def dados_ordens():

    valores = databaseOBJ.readRaw("""
        SELECT
            op.id,
            op.numero_op,
            op.quantidade AS quantidade_total_ordem,
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

    return jsonify(valores)

######################################################## VIEWS ########################################################

@app.route('/autenticacao', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def autenticacao():

    if current_user.is_authenticated:
        if getattr(current_user, 'precisa_trocar_senha', False):
            return redirect(url_for('primeiro_acesso'))
        return redirect(url_for('adm_produtos'))

    return render_template('autenticacao.html', modo_primeiro_acesso=False)

@app.route('/dados_historico')
@login_required
def dados_historico():

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

        if id_processo:
            filtros.append("producao.id_processo = %s")
            params.append(id_processo)
        else:
            abort(403)

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
            sanitizar_celula_csv(row["numero_op"]),
            sanitizar_celula_csv(row["produto"]),
            sanitizar_celula_csv(row["codigo"]),
            row["quantidade_total_ordem"],
            sanitizar_celula_csv(row["cliente"]),
            row["data_entrega"],
            sanitizar_celula_csv(row["material"]),
            sanitizar_celula_csv(row["numero_qualidade"]),
            sanitizar_celula_csv(row["processo"]),
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
@privilege_required(2)
def atualizar_ordem():

    id_op = request.form.get('id')
    numero_op = request.form.get('numero_op')
    id_produto = request.form.get('id_produto')
    numero_qualidade = request.form.get('numero_qualidade')
    id_cliente = request.form.get('id_cliente')
    id_material = request.form.get('id_material')
    id_tratamento = request.form.get('id_tratamento')
    quantidade = request.form.get('quantidade')
    data_entrega = request.form.get('data_entrega')
    status_id = request.form.get('status_id')

    ordem_atual = databaseOBJ.readRaw("""
        SELECT numero_op
        FROM ordem_de_producao
        WHERE id = %s
    """, (id_op,), realdict=True)

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
        """, (numero_op, id_op), realdict=True)

        if existe_numero:
            return jsonify({
                "success": False,
                "error": "Já existe uma OP com esse número."
            }), 400

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
            id_op
        ))

    except Exception as e:
        print("Erro:", e)
        return jsonify({
            "success": False,
            "error": "Já existe uma OP com esse número."
        }), 400

    return jsonify({"success": True})

@app.route('/produto_info')
@login_required
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

    if processo == "geral":
        id_processo = None
    else:
        id_processo = MAPA_PROCESSOS.get(processo)
        if not id_processo:
            abort(404)

    privilegio = int(current_user.privileges)
    setor_usuario = current_user.setor

    if privilegio == 1 and processo != setor_usuario:
        abort(403)

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

    filtro_finalizar = "o.status_id = 2"
    filtro_iniciar = "o.status_id IN (1,2)"

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

    operadores = databaseOBJ.readRaw("""
        SELECT id, codigo, nome
        FROM operador
        ORDER BY nome ASC
    """, realdict=True)

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
@login_required
def buscar_produtos():

    search = request.args.get('search', '')

    produtos_busca = databaseOBJ.readRaw("""
        SELECT id, codigo, nome
        FROM produtos
        WHERE (codigo ILIKE %s OR nome ILIKE %s)
        AND ativo = true
        ORDER BY codigo
        LIMIT 20
    """, (f"%{search}%", f"%{search}%"), realdict=True)

    return jsonify(produtos_busca)

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
        "select id, usuario from usuarios where privilegio = 1 order by id DESC;"
    )

    clientes_lista = databaseOBJ.readRaw(
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

    produtos_lista = databaseOBJ.readRaw("""
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
        produtos=produtos_lista,
        clientes=clientes_lista
    )

@app.route('/cadastro_usuarios', methods=['GET'])
@login_required
@privilege_required(2)
def cadastro_usuarios():
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

    usuario = request.form.get('usuario', '').strip()
    senha = request.form.get('senha', '')
    confirmar_senha = request.form.get('confirmar_senha', '')
    setor = request.form.get('setor')
    privilegio = int(request.form.get('privilegios', 1))

    if not usuario or not senha:
        return jsonify({'success': False, 'error': 'Usuário e senha são obrigatórios.'})

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

    if privilegio > current_user.privileges:
        return jsonify({'success': False, 'error': 'Permissão inválida'}), 403

    existe = databaseOBJ.readRaw(
        "SELECT id FROM usuarios WHERE usuario=%s AND COALESCE(visibilidade, true) = true;",
        (usuario,)
    )

    if existe:
        return jsonify({'success': False, 'error': 'Usuário já existe'})

    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

    databaseOBJ.writeRaw(
        """
        INSERT INTO usuarios(usuario, senha, setor, privilegio, precisa_trocar_senha)
        VALUES (%s,%s,%s,%s,false)
        """,
        (usuario, senha_hash, setor, privilegio)
    )

    return jsonify({'success': True})

@app.route('/adm_operadores')
@login_required
@privilege_required(2)
def adm_operadores():
    return render_template('adm_operador.html')
 
@app.route('/dados_operadores', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@privilege_required(2)
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

        nome = request.form.get('nome', '').strip()
        codigo = request.form.get('codigo', '').strip()

        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM operador
            WHERE codigo = %s AND COALESCE(visibilidade, true) = true
        """, (codigo,), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Chapa já cadastrada."
            })

        databaseOBJ.writeRaw("""
            INSERT INTO operador (nome, codigo)
            VALUES (%s,%s)
        """, (nome, codigo))

        return jsonify({"success": True})

    # EDITAR
    elif request.method == 'PUT':

        id_operador = request.form.get('id')
        nome = request.form.get('nome', '').strip()
        codigo = request.form.get('codigo', '').strip()

        existe = databaseOBJ.readRaw("""
            SELECT 1
            FROM operador
            WHERE codigo = %s
            AND id <> %s
            AND COALESCE(visibilidade, true) = true
        """, (codigo, id_operador), realdict=True)

        if existe:
            return jsonify({
                "success": False,
                "error": "Chapa já cadastrada."
            })

        databaseOBJ.writeRaw("""
            UPDATE operador
            SET nome=%s,
                codigo=%s
            WHERE id=%s
        """, (nome, codigo, id_operador))

        return jsonify({"success": True})

    # EXCLUIR (Soft Delete)
    elif request.method == 'DELETE':

        id_operador = request.form.get('id')

        databaseOBJ.writeRaw("""
            UPDATE operador 
            SET visibilidade = false
            WHERE id = %s
        """, (id_operador,))

        return jsonify({"success": True})

@app.route('/adicionar_ordem', methods=['POST'])
@login_required
@privilege_required(2)
def adicionar_ordem():
    try:
        numero_op = request.form['numero_op'].strip()
        id_produto = int(request.form['id_produto'])
        id_cliente = int(request.form['id_cliente'])
        id_material = int(request.form['id_material'])
        id_tratamento = int(request.form['id_tratamento'])
        quantidade_total_ordem = int(request.form['quantidade_total_ordem'])
        data_entrega = request.form['data_entrega'].strip()
        numero_qualidade = request.form.get('numero_qualidade', '').strip()
    except (KeyError, ValueError) as e:
        print("ERRO AO RECEBER DADOS:", e)
        return jsonify({'success': False, 'error': 'Dados inválidos'})

    if not numero_op or id_produto <= 0 or id_cliente <= 0:
        return jsonify({'success': False, 'error': 'Campos obrigatórios não preenchidos'})

    if quantidade_total_ordem <= 0:
        return jsonify({'success': False, 'error': 'Quantidade deve ser maior que zero'})

    try:
        datetime.strptime(data_entrega, '%Y-%m-%d')
    except ValueError:
        return jsonify({'success': False, 'error': 'Data inválida'})

    existe = databaseOBJ.readRaw("SELECT id FROM ordem_de_producao WHERE numero_op = %s;", (numero_op,))

    if existe:
        return jsonify({'success': False, 'error': 'Ordem já existe'})

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
            ultimo_processo,
            processo_atual,
            status_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            0,
            0,
            1
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

    # Correção de SQL Injection: uso estrito de query parametrizada (%s, tupla)
    teste = databaseOBJ.readRaw(
        "SELECT id, numero_op FROM ordem_de_producao WHERE numero_op = %s;",
        (numero_op,)
    )
    print("VERIFICACAO APOS INSERT:", teste)

    return jsonify({'success': True})

@app.route('/iniciar_producao', methods=['POST'])
@login_required
def iniciar_producao():

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

    ordens = databaseOBJ.readRaw("""
        SELECT id
        FROM ordem_de_producao
        WHERE numero_op = %s
    """, (numero_op,))

    if not ordens:
        return jsonify({"success": False, "erro": "Ordem não encontrada"}), 400

    id_ordem = ordens[0][0]

    if privilegio == 3:
        id_processo = int(request.form['id_processo'])
    else:
        id_processo = MAPA_PROCESSOS.get(setor_usuario)
        if not id_processo:
            return jsonify({
                "success": False,
                "erro": "Setor inválido para este usuário."
            }), 403

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

    ordem = databaseOBJ.readRaw("""
        SELECT id, id_produto
        FROM ordem_de_producao
        WHERE numero_op = %s
    """, (numero_op,))

    if not ordem:
        return jsonify({"success": False, "erro": "Ordem não encontrada."}), 400

    id_ordem = ordem[0][0]
    id_produto = ordem[0][1]

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

    databaseOBJ.writeRaw("""
        UPDATE producao
        SET status = 2,
            dt_fim = %s,
            qtde_produzida = %s,
            id_operador_fim = %s
        WHERE id = %s
    """, (datetime.now(), quantidade, id_operador_fim, id_producao))

    databaseOBJ.writeRaw("""
        UPDATE ordem_de_producao
        SET ultimo_processo = %s
        WHERE id = %s
    """, (id_processo, id_ordem))

    if id_processo == 8:
        qtd_num = float(quantidade or 0)
        prod_rows = databaseOBJ.readRaw("SELECT COALESCE(saldo, 0) FROM produtos WHERE id = %s;", (id_produto,))
        saldo_ant = float(prod_rows[0][0]) if prod_rows else 0.0
        saldo_post = saldo_ant + qtd_num

        databaseOBJ.writeRaw("""
            UPDATE ordem_de_producao
            SET status_id = 3
            WHERE id = %s
        """, (id_ordem,))

        databaseOBJ.writeRaw("""
            UPDATE produtos
            SET saldo = saldo + %s
            WHERE id = %s
        """, (quantidade, id_produto))

        try:
            id_usuario_logado = current_user.id
            databaseOBJ.writeRaw("""
                INSERT INTO movimentacoes_estoque (
                    id_produto, quantidade, operacao, saldo_anterior, saldo_posterior, observacao, id_usuario
                )
                VALUES (%s, %s, 0, %s, %s, %s, %s)
            """, (id_produto, quantidade, saldo_ant, saldo_post, f"Entrada via Expedição OP {numero_op}", id_usuario_logado))
        except Exception as e:
            return jsonify({
                "success": False, 
                "erro": f"O saldo subiu, mas o Histórico falhou. Erro do Banco: {str(e)}"
            })
    else:
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
    """
    Busca um produto ativo pelo código de barras bipado (suporta tanto códigos de barras
    diretos do produto — EAN-8, UPC-12, EAN-13, DUN-14, códigos internos — quanto etiquetas
    compostas de 36 dígitos de Ordem de Produção).
    """
    codigo_bruto = request.args.get('codigo', '')
    analise = interpretar_codigo_barras(codigo_bruto)

    if not analise["valido"]:
        return jsonify({'success': False, 'error': analise["erro"]})

    candidatos = analise["candidatos_produto"]
    codigo_base = analise["codigo_produto"]

    produto = databaseOBJ.readRaw("""
        SELECT id, nome, codigo, COALESCE(saldo, 0) AS saldo, COALESCE(estoque_minimo, 0) AS estoque_minimo, localizacao
        FROM produtos
        WHERE ativo = true
          AND UPPER(TRIM(codigo)) NOT IN ('SEM CODIGO', 'SEM CÓDIGO', '-')
          AND (
              codigo = ANY(%s)
              OR LTRIM(codigo, '0') = LTRIM(%s, '0')
          )
        ORDER BY CASE WHEN codigo = %s THEN 0 ELSE 1 END
        LIMIT 1;
    """, (candidatos, codigo_base, codigo_base), realdict=True)

    if not produto:
        return jsonify({
            'success': False,
            'error': f"Nenhum produto ativo encontrado para o código '{codigo_base}'."
        })

    p = produto[0]
    resposta = {
        'success': True,
        'id_produto': p['id'],
        'nome': p['nome'].strip(),
        'codigo': p['codigo'],
        'saldo': float(p['saldo'] or 0),
        'estoque_minimo': float(p['estoque_minimo'] or 0),
        'localizacao': p.get('localizacao') or '-',
        'tipo_codigo': analise['tipo']
    }
    if analise['tipo'] == 'OP_36':
        resposta['numero_op'] = analise['numero_op']
        resposta['numero_qualidade'] = analise['numero_qualidade']
        resposta['data_entrega'] = analise['data_entrega']

    return jsonify(resposta)

@app.route('/historico_movimentacoes', methods=['GET'])
@login_required
def historico_movimentacoes():
    query = """
        SELECT 
            m.id,
            p.nome AS produto_nome, 
            p.codigo AS produto_codigo, 
            m.operacao, 
            m.quantidade,
            m.saldo_anterior,
            m.saldo_posterior,
            COALESCE(m.observacao, '-') AS observacao,
            u.usuario AS usuario_nome, 
            TO_CHAR(m.data, 'DD/MM/YYYY HH24:MI:SS') as data_formatada
        FROM movimentacoes_estoque m
        JOIN produtos p ON m.id_produto = p.id
        JOIN usuarios u ON m.id_usuario = u.id
        ORDER BY m.data DESC, m.id DESC
    """
    
    try:
        historico_lista = databaseOBJ.readRaw(query, realdict=True)
        return jsonify({"success": True, "historico": historico_lista})
    except Exception as e:
        print("Erro ao carregar histórico:", e)
        return jsonify({"success": False, "error": "Erro ao carregar o histórico."}), 500


@app.route('/fornecedores', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def crud_fornecedores():
    if request.method == 'GET':
        fornecedores = databaseOBJ.readRaw("""
            SELECT id, nome, whatsapp, email, forma_pagamento, chave_pix
            FROM fornecedores 
            WHERE ativo = true 
            ORDER BY nome;
        """, realdict=True)
        return jsonify({"fornecedores": fornecedores})

    if current_user.privileges < 2:
        return jsonify({"success": False, "error": "Permissão insuficiente."}), 403
        
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        email = request.form.get('email', '').strip()
        pagamento = request.form.get('forma_pagamento', '').strip()
        pix = request.form.get('chave_pix', '').strip()
        
        databaseOBJ.writeRaw("""
            INSERT INTO fornecedores (nome, whatsapp, email, forma_pagamento, chave_pix)
            VALUES (%s, %s, %s, %s, %s)
        """, (nome, whatsapp, email, pagamento, pix))
        return jsonify({"success": True})
        
    elif request.method == 'PUT':
        id_forn = request.form.get('id')
        nome = request.form.get('nome', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        email = request.form.get('email', '').strip()
        pagamento = request.form.get('forma_pagamento', '').strip()
        pix = request.form.get('chave_pix', '').strip()
        
        databaseOBJ.writeRaw("""
            UPDATE fornecedores
            SET nome = %s, whatsapp = %s, email = %s, forma_pagamento = %s, chave_pix = %s
            WHERE id = %s
        """, (nome, whatsapp, email, pagamento, pix, id_forn))
        return jsonify({"success": True})
        
    elif request.method == 'DELETE':
        id_forn = request.form.get('id')
        databaseOBJ.writeRaw("UPDATE fornecedores SET ativo = false WHERE id = %s", (id_forn,))
        return jsonify({"success": True})

@app.route('/dados_compra_produto', methods=['GET'])
@login_required
def dados_compra_produto():
    id_produto = request.args.get('id_produto')
    
    dados = databaseOBJ.readRaw("""
        SELECT id_fornecedor, preco_ultima_compra, TO_CHAR(data_modificacao, 'DD/MM/YYYY HH24:MI') as data_modificacao
        FROM valor_de_compra
        WHERE id_produto = %s
        ORDER BY data_modificacao DESC LIMIT 1
    """, (id_produto,), realdict=True)
    
    if dados:
        return jsonify({"success": True, "dados": dados[0]})
    return jsonify({"success": False})

@app.route('/fornecedores_produto', methods=['GET'])
@login_required
def fornecedores_produto():
    id_produto = request.args.get('id_produto')
    
    sql = """
        SELECT 
            f.id as id_fornecedor,
            f.nome as fornecedor_nome,
            vc.preco_ultima_compra as preco,
            TO_CHAR(vc.data_modificacao, 'DD/MM/YYYY HH24:MI') as data_modificacao
        FROM (
            SELECT DISTINCT ON (id_fornecedor) id_fornecedor, preco_ultima_compra, data_modificacao
            FROM valor_de_compra
            WHERE id_produto = %s
            ORDER BY id_fornecedor, data_modificacao DESC
        ) vc
        INNER JOIN fornecedores f ON f.id = vc.id_fornecedor
        WHERE f.ativo = true
        ORDER BY f.nome
    """
    
    dados = databaseOBJ.readRaw(sql, (id_produto,), realdict=True)
    return jsonify({"success": True, "fornecedores": dados})

@app.route('/atualizar_preco_fornecedor', methods=['POST'])
@login_required
@privilege_required(2)
def atualizar_preco_fornecedor():
    try:
        id_produto = int(request.form.get('id_produto'))
        id_fornecedor = int(request.form.get('id_fornecedor'))
        
        preco_str = request.form.get('preco', '0')
        preco_str = preco_str.replace(',', '.')
        preco = float(preco_str)
        
        if preco <= 0:
            return jsonify({"success": False, "error": "Valor inválido."})

        databaseOBJ.writeRaw("""
            INSERT INTO valor_de_compra (id_produto, id_fornecedor, preco_ultima_compra)
            VALUES (%s, %s, %s)
        """, (id_produto, id_fornecedor, preco))
        
        return jsonify({"success": True})

    except Exception as e:
        print("ERRO AO SALVAR PREÇO:", e)
        return jsonify({"success": False, "error": "Erro interno ao salvar o preço."})


@app.route('/exportar_produtos_csv')
@login_required
def exportar_produtos_csv():
    formato = (request.args.get('formato') or 'xlsx').lower()

    produtos_lista = databaseOBJ.readRaw("""
        SELECT id, nome, codigo, saldo, estoque_minimo, localizacao
        FROM produtos 
        WHERE ativo = true 
        ORDER BY nome;
    """, realdict=True)

    compras = databaseOBJ.readRaw("""
        SELECT vc.id_produto, f.nome as fornecedor_nome, vc.preco_ultima_compra
        FROM (
            SELECT DISTINCT ON (id_produto, id_fornecedor) 
                   id_produto, id_fornecedor, preco_ultima_compra, data_modificacao
            FROM valor_de_compra
            ORDER BY id_produto, id_fornecedor, data_modificacao DESC
        ) vc
        INNER JOIN fornecedores f ON f.id = vc.id_fornecedor
        WHERE f.ativo = true
        ORDER BY vc.id_produto, vc.preco_ultima_compra ASC, vc.data_modificacao DESC;
    """, realdict=True)

    historico_por_produto = {}
    max_fornecedores = 0

    for compra in compras:
        id_prod = compra['id_produto']
        if id_prod not in historico_por_produto:
            historico_por_produto[id_prod] = []
        
        historico_por_produto[id_prod].append({
            "nome": compra['fornecedor_nome'],
            "preco": compra['preco_ultima_compra']
        })
        
        qtd = len(historico_por_produto[id_prod])
        if qtd > max_fornecedores:
            max_fornecedores = qtd

    cabecalho = ["Produto", "Código de Barras", "Localização", "Saldo Atual", "Estoque Mínimo"]
    for i in range(1, max_fornecedores + 1):
        cabecalho.append(f"Fornecedor {i}")
        cabecalho.append(f"Preço {i} (R$)")

    # Exportação nativa em Excel (.xlsx) com coluna de Código de Barras travada como Texto ('@')
    if formato != 'csv':
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Estoque_Produtos"
            ws.append(cabecalho)

            header_fill = PatternFill(start_color="121316", end_color="121316", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            for col_idx in range(1, len(cabecalho) + 1):
                c_head = ws.cell(row=1, column=col_idx)
                c_head.fill = header_fill
                c_head.font = header_font
                c_head.alignment = Alignment(horizontal="center", vertical="center")

            for row_idx, p in enumerate(produtos_lista, start=2):
                codigo_str = str(p.get("codigo") or "-").strip()
                linha_xlsx = [
                    str(p.get("nome") or "-"),
                    codigo_str,
                    str(p.get("localizacao") or "-"),
                    float(p.get("saldo") or 0),
                    float(p.get("estoque_minimo") or 0)
                ]

                fornecedores_deste_produto = historico_por_produto.get(p['id'], [])
                for i in range(max_fornecedores):
                    if i < len(fornecedores_deste_produto):
                        f = fornecedores_deste_produto[i]
                        linha_xlsx.append(str(f['nome']))
                        linha_xlsx.append(float(f['preco']) if f['preco'] is not None else 0.0)
                    else:
                        linha_xlsx.append("-")
                        linha_xlsx.append("-")

                ws.append(linha_xlsx)
                # Força a célula de Código de Barras (Coluna 2) estritamente como String/Texto ('@')
                cell_barcode = ws.cell(row=row_idx, column=2)
                cell_barcode.number_format = '@'
                cell_barcode.value = codigo_str
                cell_barcode.data_type = 's'

            ws.column_dimensions['A'].width = 45
            ws.column_dimensions['B'].width = 22
            ws.column_dimensions['C'].width = 22
            ws.column_dimensions['D'].width = 15
            ws.column_dimensions['E'].width = 16

            buffer_out = io.BytesIO()
            wb.save(buffer_out)
            buffer_out.seek(0)
            return Response(
                buffer_out.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=lista_de_produtos.xlsx"}
            )
        except ImportError:
            pass

    output = io.StringIO(newline="")
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(cabecalho)

    for p in produtos_lista:
        codigo_bruto = p.get("codigo")
        codigo_formatado = f'="{codigo_bruto}"' if codigo_bruto else "-"
        
        linha = [
            sanitizar_celula_csv(p.get("nome", "-")),
            codigo_formatado,
            sanitizar_celula_csv(p.get("localizacao") or "-"),
            p.get("saldo") or 0,
            p.get("estoque_minimo") or 0
        ]
        
        fornecedores_deste_produto = historico_por_produto.get(p['id'], [])
        
        for i in range(max_fornecedores):
            if i < len(fornecedores_deste_produto):
                f = fornecedores_deste_produto[i]
                preco_formatado = str(f['preco']).replace('.', ',') if f['preco'] else ""
                linha.append(sanitizar_celula_csv(f['nome']))
                linha.append(preco_formatado)
            else:
                linha.append("-")
                linha.append("-")
        
        writer.writerow(linha)

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=lista_de_produtos.csv"
        }
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=modo_debug)
