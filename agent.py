import os
import json
from dotenv import load_dotenv
import requests
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from google.genai import types

# --- CONFIGURAÇÃO ---
load_dotenv()
CHAVE_API = os.getenv("GOOGLE_API_KEY")
if not CHAVE_API:
    print("ERRO: Chave de API não encontrada no arquivo .env.")

client = genai.Client(api_key=CHAVE_API)

app = FastAPI(title="Agente de Compras Inteligente")

# --- MODELOS DE DADOS  ---

class SearchRequest(BaseModel):
    query: str

class ProdutoOferta(BaseModel):
    produto: str
    preco: str
    loja: str
    link: str

class AgentResponse(BaseModel):
    tipo: str  # "chat" ou "ofertas"
    mensagem: str # Texto explicativo ou resposta do chat
    ofertas: List[ProdutoOferta] = [] # Lista vazia se for apenas chat

# --- 1. FUNÇÃO DE LIMPEZA DE URL ---
def obter_link_limpo(url_suja: str) -> str:
    url_final = url_suja
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url_suja, headers=headers, allow_redirects=True, timeout=3, stream=True)
        url_final = response.url
        response.close()
    except Exception as e:
        pass 
    
    try:
        parsed = urlparse(url_final)
        params = parse_qs(parsed.query)
        params_bloqueados = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'ref']
        params_limpos = {k: v for k, v in params.items() if k not in params_bloqueados}
        query_limpa = urlencode(params_limpos, doseq=True)
        url_final = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query_limpa, parsed.fragment))
    except Exception:
        pass

    return url_final

# --- 2. INJETOR DE LINKS ---
def injetor_de_links(texto_resposta, metadata):
    lista_ofertas = []

    if not metadata or not metadata.grounding_chunks:
        return []

    fontes = []
    for chunk in metadata.grounding_chunks:
        if chunk.web and chunk.web.uri:
            fontes.append({
                "url": chunk.web.uri,
                "titulo": chunk.web.title.lower() if chunk.web.title else "",
                "usado": False 
            })

    linhas = texto_resposta.split('\n')
    nome_produto = linhas[0].strip() if linhas else "Produto"

    for linha in linhas:
        if "R$" in linha and "-" in linha:
            linha_lower = linha.lower()
            link_encontrado = None

            # Tentativa de Match
            for fonte in fontes:
                if not fonte["usado"]:
                    lojas_comuns = ["amazon", "mercado livre", "mercadolivre", "magalu", "magazine", "kabum", "fast", "girafa", "carrefour", "casas bahia", "ponto", "extra", "zoom", "buscapé", "terabyte", "pichau"]
                    match = False
                    
                    # Match por nome de loja
                    for loja in lojas_comuns:
                        if loja in linha_lower and (loja in fonte["url"] or loja in fonte["titulo"]):
                            match = True
                            break
                    
                    # Match por similaridade de título se não achou loja
                    if not match:
                        try:
                            termos_linha = linha_lower.split('-')[-1].strip() 
                            if len(termos_linha) > 3 and termos_linha in fonte["titulo"]:
                                match = True
                        except: pass

                    if match:
                        link_encontrado = fonte["url"]
                        fonte["usado"] = True
                        break
            
            # Fallback: pega o próximo link não usado
            if not link_encontrado:
                for fonte in fontes:
                    if not fonte["usado"]:
                        link_encontrado = fonte["url"]
                        fonte["usado"] = True
                        break

            if link_encontrado:
                try:
                    link_tratado = obter_link_limpo(link_encontrado)
                    
                    # Parsing da linha "1. R$ 1000 - Loja"
                    texto_limpo = linha.split('. ', 1)[-1] if '. ' in linha else linha
                    partes = texto_limpo.split(" - ")
                    preco_str = partes[0].strip()
                    loja_str = partes[1].strip() if len(partes) > 1 else "Loja Diversa"

                    oferta = {
                        "produto": nome_produto,
                        "preco": preco_str,
                        "loja": loja_str,
                        "link": link_tratado
                    }
                    lista_ofertas.append(oferta)
                except Exception as e:
                    print(f"Erro parse linha: {e}")
                    continue

    return lista_ofertas

# --- 3. LÓGICA DO AGENTE  ---

google_search_tool = types.Tool(google_search=types.GoogleSearchRetrieval)

# A. Prompts
PROMPT_CLASSIFICADOR = """
Você é um roteador de intenções. 
Analise a frase do usuário e retorne EXATAMENTE e APENAS um JSON com as chaves "tipo" e "termo_busca".

Regras:
1. Se o usuário quer comprar, saber preço, ver ofertas ou onde comprar:
   - "tipo": "OFERTAS"
   - "termo_busca": O nome do produto limpo (ex: "iPhone 15", "Geladeira Frost Free").

2. Se for dúvida técnica, conversa, "o que é", curiosidade ou se não houver intenção clara de compra:
   - "tipo": "CHAT"
   - "termo_busca": null

Frase: {query}

Resposta Obrigatória (JSON):
{{"tipo": "OFERTAS", "termo_busca": "..."}} ou {{"tipo": "CHAT", "termo_busca": null}}
"""

PROMPT_BUSCA_RIGIDA = """
Você é um Algoritmo de Classificação de Ofertas.
1. PESQUISA AMPLA: Busque preços atuais no Brasil.
2. SAÍDA: Apresente APENAS as 3 melhores ofertas no formato abaixo.
3. Não use markdown, negrito ou explicações extras.

FORMATO OBRIGATÓRIO:
[Nome do Produto Resumido]
1. R$ [Preço] - [Nome da Loja]
2. R$ [Preço] - [Nome da Loja]
3. R$ [Preço] - [Nome da Loja]
"""

PROMPT_CHAT_AMIGAVEL = """
Você é o "Assistente Busca Preço", um curador inteligente especializado em encontrar os melhores produtos para o usuário.

SUAS REGRAS DE COMPORTAMENTO:

1. IDENTIDADE: Se o usuário perguntar quem você é ou o que você faz, responda que você é um curador de produtos e que sua funcionalidade principal é pesquisar ofertas e comparar preços de mercado.

2. CONCISÃO EXTREMA: Ao explicar sobre um produto ou tecnologia, seja direto. Evite textos longos ou técnicos demais. Resuma os pontos-chave (specs principais) em no máximo um parágrafo curto (3 a 4 frases). O usuário quer uma visão geral rápida, não um manual.

3. SEM PREÇOS AGORA: Não forneça listas de preços ou links nesta resposta. Foque apenas em tirar a dúvida ou explicar o produto.

4. FORMATATAÇÃO: Não use Markdown (negrito, itálico, tópicos). Envie apenas texto puro e limpo.
"""


# B. Funções de Execução
def detectar_intencao(query: str) -> dict:
    response = None # Inicializa para evitar erro no 'except'
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=PROMPT_CLASSIFICADOR.format(query=query),
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json" 
            )
        )
        
        texto_original = response.text
        # DEBUG: Mostra exatamente o que o Gemini mandou
        print(f"--- ROTEADOR RAW: {texto_original} ---") 

        # 1. Limpeza (se necessário)
        texto_limpo = texto_original.strip()
        if texto_limpo.startswith("```"):
            texto_limpo = texto_limpo.replace("```json", "").replace("```", "")
        
        # 2. Parsing seguro
        try:
            dados = json.loads(texto_limpo)
        except json.JSONDecodeError:
            print("--- ERRO: JSON inválido retornado pelo modelo.")
            return {"tipo": "CHAT", "termo_busca": None}

        # 3. Validação de Chaves (Usa .get para não quebrar com KeyError)
        tipo = dados.get("tipo", "CHAT") # Se não tiver 'tipo', assume CHAT
        termo = dados.get("termo_busca")

        # Se for OFERTAS mas não tem termo, vira CHAT
        if tipo == "OFERTAS" and not termo:
             print("--- AVISO: Oferta sem termo de busca. Fallback para CHAT.")
             return {"tipo": "CHAT", "termo_busca": None}
             
        return {"tipo": tipo, "termo_busca": termo}

    except Exception as e:
        print(f"ERRO CRÍTICO NO ROTEADOR: {e}")
        # Agora conseguimos ver o texto mesmo no erro
        if response:
            print(f"Conteúdo que causou erro: {response.text}")
        return {"tipo": "CHAT", "termo_busca": None}

def executar_busca_ofertas(termo_limpo: str) -> AgentResponse:
    """Busca ofertas usando o termo já limpo pelo roteador."""
    
    # Observe que aqui usamos termo_limpo, e não a frase inteira
    print(f"--- MODO OFERTAS: {termo_limpo} ---")
    
    termos_reforco = "comprar menor preço barato promoção oferta brasil online"
    query_especializada = f"{termos_reforco} {termo_limpo}"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=query_especializada,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                system_instruction=PROMPT_BUSCA_RIGIDA,
                temperature=0.1
            )
        )
        
        ofertas = []
        if response.candidates and response.candidates[0].grounding_metadata:
            ofertas = injetor_de_links(response.text, response.candidates[0].grounding_metadata)
        
        msg = f"Encontrei estas ofertas para {termo_limpo}:"
        if not ofertas:
            msg = f"Busquei ofertas para '{termo_limpo}', mas não consegui validar links."

        return AgentResponse(
            tipo="ofertas",
            mensagem=msg,
            ofertas=ofertas
        )

    except Exception as e:
        print(f"Erro busca ofertas: {e}")
        return AgentResponse(tipo="erro", mensagem="Erro ao buscar ofertas.", ofertas=[])

def executar_chat_geral(query: str) -> AgentResponse:
    """Executa uma conversa normal com acesso a dados atualizados."""
    print(f"--- MODO CHAT: {query} ---")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                system_instruction=PROMPT_CHAT_AMIGAVEL,
                temperature=0.7
            )
        )
        return AgentResponse(
            tipo="chat",
            mensagem=response.text,
            ofertas=[]
        )
    except Exception as e:
        return AgentResponse(tipo="erro", mensagem="Desculpe, não consegui processar sua pergunta.", ofertas=[])
    
def limpar_json(texto_sujo: str) -> str:
    """Remove crases de markdown (```json ... ```) se existirem."""
    texto_limpo = texto_sujo.strip()
    if texto_limpo.startswith("```"):
        # Remove a primeira linha (```json) e a última (```)
        linhas = texto_limpo.splitlines()
        if len(linhas) >= 3:
            texto_limpo = "\n".join(linhas[1:-1])
        else:
            texto_limpo = texto_limpo.replace("```json", "").replace("```", "")
    return texto_limpo.strip()

def processar_solicitacao(query: str):
    # 1. Detectar Intenção e Extrair (1 chamada apenas)
    dados_intencao = detectar_intencao(query)
    tipo = dados_intencao.get("tipo")
    produto = dados_intencao.get("termo_busca")
    
    # 2. Roteamento
    if tipo == "OFERTAS" and produto:
        # Passamos o produto limpo (ex: "iPhone 15")
        return executar_busca_ofertas(produto) 
    else:
        # No chat, passamos a query original para manter o contexto da conversa
        return executar_chat_geral(query)