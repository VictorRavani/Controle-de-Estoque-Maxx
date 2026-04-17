# 📦 Sistema de Rastreabilidade de Ordens de Produção (OP)

## 📌 Visão Geral
Este projeto tem como objetivo implementar um **sistema independente de rastreabilidade de Ordens de Produção (OP)**, oferecendo maior **visibilidade, controle e confiabilidade** das informações ao longo do processo produtivo.

A solução foi desenhada para **apoiar o modelo de Lean Manufacturing** já existente na empresa, reduzindo desperdícios, retrabalho e falhas de comunicação entre os setores.

---

## 🚨 Descrição do Problema (Dor do Cliente)

Atualmente, a empresa não possui um sistema que permita rastrear a Ordem de Produção ao longo das etapas produtivas. Com isso:

- ❌ É necessário realizar **contatos manuais entre setores** para localizar a produção
- ❌ Não existe **confiabilidade na quantidade real produzida por OP**
- ❌ Peças podem avançar no processo com **quantidade inferior à prevista**, sem rastreabilidade da perda
- ❌ Falta **visibilidade em tempo real** da produção entre processos

👉 **Principal dor:** ausência de rastreabilidade e controle da OP ao longo do processo produtivo.

---

## 💡 Proposta da Solução

Será desenvolvido um **sistema web independente de rastreabilidade de Ordens de Produção**, sem integração direta com o ERP da empresa.

### Premissas da Solução
- 🧾 O ERP será responsável **apenas pela geração do QR Code**
- 🔍 O sistema utilizará exclusivamente os dados contidos no QR Code
- 🔄 **Não haverá troca de dados automática** com o ERP
- 🗄️ Banco de dados próprio para rastreabilidade

Essa abordagem garante **baixo acoplamento**, simplicidade e facilidade de manutenção.

---

## 🔲 QR Code da Ordem de Produção

O QR Code conterá as informações necessárias para identificação da OP, tais como:

- 📄 Número da OP
- 📊 Quantidade prevista
- 🏷️ Outras informações relevantes para rastreabilidade

Esses dados serão utilizados **exclusivamente pelo sistema desenvolvido**, sem retorno de informações ao ERP.

---

## 🏭 Escopo do Processo Produtivo

O sistema será implantado em **6 etapas do processo produtivo**:

| Código | Etapa                  |
|------:|------------------------|
| 0     | PCP                    |
| 1     | Corte                  |
| 2     | Estamparia             |
| 3     | Solda                  |
| 4     | Beneficiamento Externo |
| 5     | Expedição              |

---

## ⚙️ Funcionamento do Sistema

O sistema será utilizado em **computadores (PCs)** posicionados entre os processos produtivos.

### 🔁 Fluxo de Operação
1. 📷 O operador realiza a **leitura do QR Code da OP**
2. 🧠 O sistema carrega automaticamente os dados da OP
3. ✍️ Caso necessário, os dados podem ser preenchidos manualmente
4. 🔢 O operador informa a quantidade de peças encaminhadas para o próximo processo
5. ⚠️ Em caso de divergência entre quantidade prevista e informada:
   - Indicação visual da diferença (exemplo: uso de cores)
   - Registro da ocorrência para análise posterior
6. 🔍 Tela de consulta permite localizar rapidamente:
   - A etapa atual da OP
   - O histórico de movimentações e quantidades

---

## 🧱 Arquitetura da Aplicação

- 🌐 Aplicação **Web**, acessada via navegador
- 💻 Execução **local**, sem dependência de serviços externos
- 🗃️ Banco de dados próprio para rastreabilidade
- 🚫 Sem integração com o ERP

---

## ▶️ Execução Local da Aplicação (Windows)

### 🐍 Versão do Python

A versão oficial do projeto está definida no Dockerfile:

```dockerfile
FROM python:3.8-alpine
```

⚠️ **Importante:**  
A aplicação deve ser executada com **Python 3.8**. Versões superiores (ex: 3.12) podem causar erros de compatibilidade.

---

### 1️⃣ Verificar versões de Python instaladas

```powershell
py --list
```

✔️ Certifique-se de que **Python 3.8** esteja listado.

---

### 2️⃣ Instalar Python 3.8 (se necessário)

- Instale o Python 3.8 (64-bit)
- Não é necessário remover outras versões
- Múltiplas versões podem coexistir no Windows

```powershell
winget install Python.Python.3.8
```

---

### 3️⃣ Acessar a pasta do projeto

Exemplo:

```text
C:\Projects\EM_ANDAMENTO\ARO_ESTAMPARIA\Aplication\webapp
```

---

### 4️⃣ Criar o ambiente virtual (venv)

```powershell
py -3.8 -m venv venv
venv\Scripts\activate
```

Confirme:

```powershell
python --version
```

---

### 5️⃣ Instalar dependências

```powershell
pip install -r requirements.txt
```

📦 O arquivo `requirements.txt` já possui o NumPy compatível:

```text
numpy==1.21.6
```

---

### 6️⃣ Executar a aplicação

```powershell
python main.py
```

Ou:

```powershell
set FLASK_APP=main:app
flask run
```

---

## 🚀 Aplicação em Execução

Se aparecer:

```text
Serving Flask app 'main'
Running on http://127.0.0.1:5000
```

🎉 A aplicação está funcionando corretamente.

Acesse no navegador:

👉 **http://127.0.0.1:5000**

---

## ⚠️ Observações Importantes

- Servidor Flask é **apenas para desenvolvimento**
- Em produção, utilize **Docker + uWSGI**
- Avisos `SyntaxWarning` não impedem a execução

---

## ✅ Benefícios Esperados

- 📈 Maior visibilidade do fluxo produtivo
- 📉 Redução de perdas não identificadas
- 🔒 Maior confiabilidade das informações
- ⏱️ Menor dependência de comunicação manual
- 🏗️ Apoio direto às práticas de Lean Manufacturing

---

## 📄 Licença

Este projeto é distribuído conforme os termos definidos no arquivo `LICENSE`.

---

## Ao Iniciar a aplicação

Sempre que abrir um novo terminal, é necessário ativar o ambiente virtual antes de executar a aplicação.

No diretório raiz do projeto, execute:

```powershell
.\venv\Scripts\Activate
```

---

## Regra de ouro (grava isso na testa do projeto)
🔹 pg_restore SÓ funciona com:

.backup

.tar

formato Custom ou Directory

🔹 Arquivo .sql NÃO usa pg_restore

Arquivo .sql é restaurado com psql ou Query Tool.

---

## Para conectar ao banco

- Crie o Banco no PGAdmin 
- Faça o Restore do banco
- Use o arquivo .tar
- Conecte no Dbeaver colocando o nome do banco que vc criou em localhost

<img width="841" height="694" alt="image" src="https://github.com/user-attachments/assets/4f5fa9c9-587b-4b2e-8419-e802634fe93b" />

<img width="395" height="218" alt="image" src="https://github.com/user-attachments/assets/8e1e62ec-517b-4917-834f-811b5f12ae66" />

## Conexão com o DB: db_ARO

```powershell
class postgresDatabase():
    def __init__(self, user='postgres', password='postgres', host='localhost', dbname='db_ARO', port='5432'):
```


# 📋 REGRA DE NEGÓCIO  
## Sistema de Controle de Ordens de Produção

---

## 🏗️ 1. Estrutura Geral da OP

- Existe **apenas um cadastro de Ordem de Produção (OP)** no sistema.
- Cada OP pode possuir **até 8 processos vinculados**, conforme cadastro na tabela de Processos.
- Cada processo representa um setor produtivo (ex: Corte, Estampa, Tratamento, Expedição, etc.).
- Não pode existir duas OPs com o mesmo número.

---

## 🔄 2. Encerramento Automático

- Quando o setor **Expedição** finalizar seu processo:
  - O sistema automaticamente altera o status geral da OP para **FINALIZADO**.
  - Nenhum novo apontamento poderá ser realizado nessa OP.

---

## 👥 3. Níveis de Acesso

### 🔹 Operacional

**Permissões:**
- Visualizar monitoramento apenas do seu setor.
- Visualizar histórico apenas do seu setor.
- Iniciar produção (abrir OP no setor).
- Finalizar produção (fechar OP no setor).
- Localizar OP por código de barras ou manualmente.

**Restrições:**
- Não pode criar OP.
- Não pode editar cadastro de cliente ou produto.
- Não pode gerenciar usuários.

---

### 🔹 PCP

**Permissões:**
- Visão geral de todos os setores.
- Cadastrar produtos.
- Cadastrar clientes.
- Cadastrar OPs.
- Editar dados de OP.
- Acompanhar status geral.

---

### 🔹 Administrador

**Permissões:**
- Todas as permissões do PCP.
- Criar usuários.
- Alterar senhas.
- Gerenciar níveis de acesso.

---

## ⚙️ 4. Regras de Produção

### ▶️ 4.1 Início de Produção

Não é permitido iniciar produção se:

- A OP não estiver cadastrada no sistema.
- A OP estiver com status **Cancelado**.
- A OP estiver com status **Finalizado**.
  
---

### 🔁 4.2 Fluxo entre Setores

#### Status possíveis da OP

| Status        | Descrição |
|---------------|-----------|
| ⏳ Aguardando | OP cadastrada, aguardando início em algum setor |
| 🏭 Em Produção | OP em execução no setor |
| ✅ Finalizado | Processo encerrado na Expedição |
| ❌ Cancelado | OP cancelada, não pode mais produzir |

#### Regras de Transição

- Quando um setor finaliza:
  - status muda para **Aguardando**
  - Se for o setor **Expedição** → status muda para **Finalizado**

- OP **Cancelada**:
  - Não pode iniciar produção.
  - Permanece disponível para consulta no histórico.
  - Não pode gerar novos apontamentos.

---

## 🗂️ 5. Cadastro e Controle de OP

- O cadastro da OP é responsabilidade do **PCP**.
- O Operacional apenas executa produção.
- OP cancelada mantém todo o histórico produtivo.
- Não é possível iniciar produção de uma OP inexistente.

---

## 📷 6. Leitura de Código de Barras / QR Code

### 📌 Padrão Utilizado

- **Code 128**
- Exemplo: 0002775500012775015AB389444420260812

### 📐 Estrutura do Código

| Campo | Tamanho | Exemplo |
|--------|----------|----------|
| OP | 8 dígitos | 00027755 |
| AQ | 8 dígitos | 00012775 |
| Código Produto | 12 caracteres | 015AB3894444 |
| Data Entrega | 8 dígitos | 20260812 |

### 🔎 Tratamento da Leitura

O sistema:

- Ignora zeros à esquerda nos campos:
  - OP
  - AQ
  - Código do produto
- Converte a data para formato `YYYY-MM-DD`
- Preenche automaticamente:
  - Número da OP
  - Número AQ
  - Código do produto
  - Data de entrega
- Realiza busca automática do produto no banco pelo código.

---

## 🔍 7. Localização da OP

A OP pode ser localizada por:

- 📷 Leitura do código de barras
- ⌨️ Digitação manual do número da OP

---

## 📊 8. Controle por Processo

- Cada OP pode passar pelos 8 processos.
- Cada processo registra seu próprio status de execução, no menu de monitoramento e histórico de produção.
- A finalização do último processo (Expedição) encerra automaticamente a OP.

---

## 🧾 9. Histórico

- Todas as movimentações ficam registradas.
- OPs finalizadas ou canceladas permanecem disponíveis para consulta.
- O histórico é segmentado por setor conforme nível de acesso.

---

## 🚫 Regras Críticas

- Não pode haver produção simultânea da mesma OP no mesmo setor.
- Não é permitido iniciar produção sem OP cadastrada.
- OP Finalizada ou Cancelada não pode receber novos apontamentos.

---

### 🔐 Alteração Manual para Status **Finalizado**

A alteração manual do status da OP para **Finalizado** sem passar pelo processo da Expedição é permitida **somente para os níveis:**

- 👔 PCP  
- 🛠️ Administrador  

Usuários do nível **Operacional** não possuem permissão para realizar essa alteração.

Essa regra garante controle hierárquico e evita encerramentos indevidos de Ordens de Produção.

---

## ❓ 10. Regras Complementares do Sistema

### 🔄 Uma OP pode voltar de **Finalizado** para **Em Produção**?

**Sim.**

Basta alterar o status da ordem no menu:

> Ordens → Editar Ordem → Alterar Status

---

### ♻️ Uma OP Cancelada pode ser reativada?

**Sim.**

Basta alterar o status para **Aguardando** no menu:

> Ordens → Editar Ordem → Alterar Status

---

### 🏭 Pode existir produção simultânea da mesma OP em dois ou mais setores?

**Sim.**

O sistema foi projetado para permitir produção simultânea em setores diferentes.

Cada setor controla seu próprio processo de forma independente.

---

### 📦 Existe controle de quantidade produzida por setor?

**Sim.**

Existe um campo onde o operador informa a quantidade produzida ao finalizar o processo no setor.

---

### ✏️ Existe bloqueio para editar OP que já iniciou produção?

**Não.**

A OP pode ser editada durante o processo produtivo.

---

### 👤 Existe rastreabilidade por operador (chapa)?

**Sim.**

O sistema registra:

- Operador que iniciou a produção
- Operador que encerrou a produção

Isso garante rastreabilidade completa por setor.

---




