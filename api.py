import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from agent import processar_solicitacao, ProdutoOferta

app = FastAPI(title="API Agente Android")

# Modelo de entrada 
class PedidoBusca(BaseModel):
    query: str

# Modelo de Resposta (O que vai para o Android)
class RespostaAgente(BaseModel):
    tipo: str               # "chat" ou "ofertas"
    mensagem: str           # O texto da resposta
    ofertas: List[ProdutoOferta] = [] # Lista de cards (vazia se for chat)

@app.post("/buscar", response_model=RespostaAgente)
def buscar_endpoint(pedido: PedidoBusca):
    """
    Endpoint principal para o App Android.
    """
    if not pedido.query:
        return RespostaAgente(
            tipo="chat",
            mensagem="Por favor, digite algo para que eu possa ajudar.",
            ofertas=[]
        )

    try:
        # Chama a inteligência do agent.py
        # O agent.py deve retornar um objeto/dict com: tipo, mensagem e ofertas
        resultado = processar_solicitacao(pedido.query)
        
        return resultado

    except Exception as e:
        print(f"Erro na API: {e}")
        # Retorno de erro gracioso para o Android não crashar
        return RespostaAgente(
            tipo="chat",
            mensagem="Desculpe, tive um erro interno ao processar seu pedido. Tente novamente.",
            ofertas=[]
        )

if __name__ == "__main__":
    # Host 0.0.0.0 permite que o emulador Android ou celular na mesma rede acesse
    uvicorn.run(app, host="0.0.0.0", port=8000)