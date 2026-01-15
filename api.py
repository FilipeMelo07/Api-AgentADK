import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from agent_core import processar_pedido_usuario

app = FastAPI()

# 1. O que o Android manda
class PedidoBusca(BaseModel):
    query: str

# 2. O Schema do Objeto Individual (JSON)
class ProdutoOferta(BaseModel):
    produto: str
    preco: str
    loja: str
    link: str

# 3. A Rota retorna uma LISTA desses objetos
@app.post("/buscar", response_model=List[ProdutoOferta])
def buscar_ofertas(pedido: PedidoBusca):
    """
    Rota que o Android consome.
    Entrada: {"query": "iphone 15"}
    Saída: [
      {
        "produto": "iPhone 15", 
        "preco": "R$ 5000", 
        "loja": "Amazon", 
        "link": "https..."
      }
    ]
    """
    if not pedido.query:
        return []
    
    # O agente agora retorna uma LISTA DE DICIONÁRIOS
    lista_ofertas = processar_pedido_usuario(pedido.query)
    
    return lista_ofertas

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)