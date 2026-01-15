import time
import uvicorn
from typing import List
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from google.genai import types

# --- CONFIGURAÇÃO ---
CHAVE_API = "AIzaSyDWwMXm2CZO_4BEdYqKM3WnlxepRFZSWMs" 
client = genai.Client(api_key=CHAVE_API)

# --- INICIALIZAÇÃO DA API ---
app = FastAPI(title="Busca Ofertas API")

# Modelo de Entrada
class SearchRequest(BaseModel):
    query: str

# Modelo de Saída (JSON Estruturado)
class ProdutoOferta(BaseModel):
    produto: str
    preco: str
    loja: str
    link: str

# 1. PROMPT (Mantido Intacto)
instrucao_sistema = """
Você é um Algoritmo de Classificação de Ofertas.

SEU PROCESSO (CoT):
1. PESQUISA AMPLA: Ao receber o produto, busque em múltiplas fontes (Lojas oficiais, marketplaces, comparadores) para encontrar o maior número possível de preços (Tente identificar pelo menos 5 a 10 opções internamente).
2. VERIFICAÇÃO: Cheque se o preço condiz com o produto real (descarte acessórios ou preços errados).
3. ORDENAÇÃO: Ordene mentalmente todas as opções encontradas do MENOR para o MAIOR preço.
4. SAÍDA: Apresente APENAS as 3 primeiras posições (as mais baratas).

REGRAS DE OURO:
- Se o produto não existir (ex: iPhone 50), diga claramente: "Produto ainda não lançado ou indisponível."
- Priorize preço à vista/Pix.
- Mantenha o formato estrito de lista.

FORMATO OBRIGATÓRIO (Lista Limpa):
[Nome do Produto]
1. R$ [Preço] - [Nome da Loja Exato]
2. R$ [Preço] - [Nome da Loja Exato]
3. R$ [Preço] - [Nome da Loja Exato]

(Não escreva links no texto, nem introdução, nem conclusão).
"""

google_search_tool = types.Tool(
    google_search=types.GoogleSearchRetrieval
)

chat = client.chats.create(
    model="gemini-2.5-flash", 
    config=types.GenerateContentConfig(
        tools=[google_search_tool],
        response_modalities=["TEXT"],
        system_instruction=instrucao_sistema,
        temperature=0.1
    )
)

# 2. FUNÇÃO INJETORA MODIFICADA (Retorna Lista de JSON)
def injetor_de_links(texto_resposta, metadata):
    """
    Função que pega o texto puro, acha os links, e monta uma LISTA DE OBJETOS JSON.
    """
    lista_ofertas = []

    if not metadata or not metadata.grounding_chunks:
        return []

    # 1. Extrai links e títulos dos metadados
    fontes = []
    for chunk in metadata.grounding_chunks:
        if chunk.web and chunk.web.uri:
            fontes.append({
                "url": chunk.web.uri,
                "titulo": chunk.web.title.lower() if chunk.web.title else "",
                "usado": False 
            })

    linhas = texto_resposta.split('\n')
    
    # Tenta descobrir o nome do produto (geralmente a primeira linha)
    nome_produto = "Produto Desconhecido"
    if len(linhas) > 0:
        nome_produto = linhas[0].strip()

    for linha in linhas:
        # Se a linha parecer uma oferta (tem "R$" e "-"), processamos
        if "R$" in linha and "-" in linha:
            linha_lower = linha.lower()
            link_encontrado = None

            # Tenta casar o nome da loja na linha com a URL ou Título da fonte
            for fonte in fontes:
                if not fonte["usado"]:
                    lojas_comuns = ["amazon", "mercado livre", "mercadolivre", "magalu", "magazine", "kabum", "fast", "girafa", "carrefour", "casas bahia", "ponto", "extra", "zoom", "buscapé", "buscape"]
                    
                    match = False
                    for loja in lojas_comuns:
                        if loja in linha_lower and (loja in fonte["url"] or loja in fonte["titulo"]):
                            match = True
                            break
                    
                    if not match:
                        try:
                            termos_linha = linha_lower.split('-')[-1].strip() 
                            if len(termos_linha) > 3 and termos_linha in fonte["titulo"]:
                                match = True
                        except:
                            pass

                    if match:
                        link_encontrado = fonte["url"]
                        fonte["usado"] = True
                        break
            
            # Fallback: Se não achou link exato, pega o próximo disponível
            if not link_encontrado:
                for fonte in fontes:
                    if not fonte["usado"]:
                        link_encontrado = fonte["url"]
                        fonte["usado"] = True
                        break

            # Se temos um link, montamos o objeto JSON
            if link_encontrado:
                try:
                    # Parse da string "1. R$ 1000,00 - Amazon"
                    # Remove o número inicial "1. " se houver
                    texto_limpo = linha.split('. ', 1)[-1] if '. ' in linha else linha
                    
                    # Separa preço e loja pelo traço " - "
                    partes = texto_limpo.split(" - ")
                    preco_str = partes[0].strip()
                    loja_str = partes[1].strip() if len(partes) > 1 else "Loja Diversa"

                    oferta = {
                        "produto": nome_produto,
                        "preco": preco_str,
                        "loja": loja_str,
                        "link": link_encontrado
                    }
                    lista_ofertas.append(oferta)
                except Exception as e:
                    print(f"Erro ao parsear linha '{linha}': {e}")
                    continue

    return lista_ofertas

# 3. PROCESSADOR MODIFICADO (Retorna List[dict] ou [])
def processar_pedido_usuario(texto_usuario) -> List[dict]:
    termos_reforco = "comprar menor preço barato promoção oferta brasil online"
    query_especializada = f"{termos_reforco} {texto_usuario}"
    
    max_tentativas = 3
    for tentativa in range(max_tentativas):
        try:
            print(f"DEBUG API - Buscando: {query_especializada}") 
            
            response = chat.send_message(query_especializada)
            texto_bruto = response.text
            
            # Chama o injetor se houver metadados
            if response.candidates and response.candidates[0].grounding_metadata:
                return injetor_de_links(texto_bruto, response.candidates[0].grounding_metadata)
            
            # Se não tiver metadados (raro), retorna lista vazia
            return []

        except Exception as e:
            erro_str = str(e)
            if "429" in erro_str:
                print(f"⚠️ Cota excedida. Aguardando 5s...")
                time.sleep(5)
                continue
            else:
                print(f"Erro: {erro_str}")
                return []

    return []

# --- ROTA DA API ---
@app.post("/buscar", response_model=List[ProdutoOferta])
def rota_buscar(request: SearchRequest):
    """
    Recebe JSON: {"query": "iphone 15"}
    Retorna Lista JSON:
    [
      {
        "produto": "iPhone 15",
        "preco": "R$ 4.000",
        "loja": "Amazon",
        "link": "https://..."
      }
    ]
    """
    resultado_lista = processar_pedido_usuario(request.query)
    return resultado_lista

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    # Roda o servidor acessível na rede local
    uvicorn.run(app, host="0.0.0.0", port=8000)