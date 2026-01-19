# 🛒 Agente de Compras Inteligente (Backend)

Este é o backend em Python para o assistente de compras Android. O projeto utiliza **FastAPI** para servir os endpoints e **Google ADK** para interpretar intenções do usuário, realizar buscas na web (Grounding) e retornar ofertas estruturadas ou conversas naturais.

## 🚀 Tecnologias Utilizadas

- **Linguagem:** Python 3.9+
- **Framework Web:** FastAPI
- **Servidor:** Uvicorn
- **IA & Busca:** Google ADK
- **Validação:** Pydantic
- **Ambiente:** Python Dotenv

## 🛠️ Configuração do Ambiente

Siga os passos abaixo para preparar o ambiente de desenvolvimento localmente.

### 1\. Pré-requisitos

Certifique-se de ter o **Python** e o **Git** instalados.

### 2\. Clonar e Criar Ambiente Virtual (.venv)

Recomendamos isolar as dependências do projeto para evitar conflitos.

``` bash
# Crie o ambiente virtual  
python -m venv .venv  
# Ative o ambiente virtual:  
\# Windows (PowerShell):  
.venv\\Scripts\\activate  
\# Linux/Mac:  
source .venv/bin/activate  
```

### 3\. Instalar Dependências

Instale as bibliotecas necessárias listadas no requirements.txt.
``` bash
pip install -r requirements.txt  
```
**Nota:** Se o seu requirements.txt estiver muito grande, as dependências essenciais para este projeto rodar são apenas: fastapi, uvicorn, pydantic, python-dotenv, requests e google-genai.

### 4\. Configurar Variáveis de Ambiente (.env)

O sistema precisa de uma chave de API do Google para funcionar.

- Localize o arquivo .env.example na raiz do projeto.
- Faça uma cópia dele e renomeie para .env.
- Abra o arquivo .env e insira sua chave:

``` bash
GOOGLE_GENAI_USE_VERTEXAI=0  
GOOGLE_API_KEY="SUA_CHAVE_AQUI_DO_AISTUDIO_GOOGLE_COM"  
```
## ▶️ Como Rodar o Projeto

Com o ambiente virtual ativado e as dependências instaladas, inicie o servidor:
``` bash
python api.py  
```
Você verá uma mensagem indicando que o servidor está rodando em:

<http://0.0.0.0:8000>

## 📡 Documentação da API

A API possui um endpoint principal que recebe mensagens do usuário e decide automaticamente se deve responder como um chat ou buscar ofertas de produtos.

### Endpoint: /buscar

- **Método:** POST
- **URL:** <http://localhost:8000/buscar>
- **Content-Type:** application/json

#### 📥 Payload de Requisição (O que enviar)
``` json
# Em caso de busca de ofertas 
{  
    "query": "qual o melhor celular até 2000 reais?"  
}  
``` 

| **Campo** | **Tipo** | **Obrigatório** | **Descrição** |
| --- | --- | --- | --- |
| query | string | Sim | O texto digitado pelo usuário no aplicativo Android. |

#### 📤 Payload de Resposta (O que esperar)

A API retorna um objeto JSON que pode variar dependendo da intenção detectada (chat ou ofertas).

- Cenário A: Intenção de Compra (Retorna Ofertas)

Quando o usuário pede preços, promoções ou onde comprar.

``` json
{  
    "tipo": "ofertas",  
    "mensagem": "Encontrei estas ofertas para celular até 2000 reais:",  
    "ofertas": [  
        {  
            "produto": "Samsung Galaxy A55 128GB",  
            "preco": "R$ 1.899,00",  
            "loja": "Amazon",  
            "link": "https://www.amazon.com.br/..."  
        },  
        {  
            "produto": "Motorola Edge 40 Neo",  
            "preco": "R$ 1.750,00",  
            "loja": "Mercado Livre",  
            "link": "https://www.mercadolivre.com.br/..."  
        }  
    ]  
}  

``` 

- Cenário B: Conversa Geral (Chat)

Quando o usuário pede especificações técnicas, opiniões ou dúvidas gerais.
``` json
{  
    "tipo": "chat",  
    "mensagem": "Nessa faixa de preço, o Galaxy A55 se destaca pela tela Super AMOLED e atualizações de sistema longas. Se preferir carregamento mais rápido, o Edge 40 Neo é uma ótima opção.",  
    "ofertas": []  
}  
```

| **Campo** | **Tipo** | **Descrição** |
| --- | --- | --- |
| tipo | string | Identificador de ação para o Frontend. Valores possíveis: "chat" ou "ofertas". |
| mensagem | string | O texto da resposta do assistente. |
| ofertas | List\[Object\] | Lista de cards de produtos. Será uma lista vazia \[\] se o tipo for chat. |

## 🧪 Teste Rápido (cURL)

Você pode testar o endpoint usando o terminal:

``` bash
curl -X POST "<http://localhost:8000/buscar>" \\  
\-H "Content-Type: application/json" \\  
\-d '{"query": "preço playstation 5"}'  
```

## 📂 Estrutura de Arquivos

- api.py: Arquivo principal da API (FastAPI). Define as rotas e modelos de dados.
- agent.py: Lógica de IA. Contém a integração com o Gemini, prompts e o "injetor de links" (tratamento de URLs).
- .env: Arquivo de segredos (NÃO versionado no Git).
- .env.example: Modelo do arquivo de configuração.