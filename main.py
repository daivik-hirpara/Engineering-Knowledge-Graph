import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from connectors import DockerComposeConnector, TeamsConnector, KubernetesConnector
from graph.storage import GraphStorage
from graph.query import QueryEngine
from chat.llm import LLMClient
from chat.intent import IntentParser

load_dotenv()

storage = None
query_engine = None
llm_client = None
intent_parser = None


def load_graph():
    global storage, query_engine, llm_client, intent_parser
    
    storage = GraphStorage()
    storage.connect()
    
    storage.clear_all()
    
    docker_connector = DockerComposeConnector("data/docker-compose.yml")
    docker_nodes, docker_edges = docker_connector.parse()
    storage.bulk_upsert_nodes(docker_nodes)
    storage.bulk_upsert_edges(docker_edges)
    print(f"Loaded {len(docker_nodes)} nodes and {len(docker_edges)} edges from docker-compose.yml")
    
    teams_connector = TeamsConnector("data/teams.yaml")
    teams_nodes, teams_edges = teams_connector.parse()
    storage.bulk_upsert_nodes(teams_nodes)
    storage.bulk_upsert_edges(teams_edges)
    print(f"Loaded {len(teams_nodes)} nodes and {len(teams_edges)} edges from teams.yaml")
    
    if os.path.exists("data/k8s-deployments.yaml"):
        k8s_connector = KubernetesConnector("data/k8s-deployments.yaml")
        k8s_nodes, k8s_edges = k8s_connector.parse()
        storage.bulk_upsert_nodes(k8s_nodes)
        storage.bulk_upsert_edges(k8s_edges)
        print(f"Loaded {len(k8s_nodes)} nodes and {len(k8s_edges)} edges from k8s-deployments.yaml")
    
    query_engine = QueryEngine(storage)
    llm_client = LLMClient()
    intent_parser = IntentParser(query_engine)
    
    stats = query_engine.get_graph_stats()
    print(f"Graph loaded: {stats['total_nodes']} nodes, {stats['total_edges']} edges")
    print(f"Node types: {stats['nodes_by_type']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_graph()
    yield
    if storage:
        storage.close()


app = FastAPI(
    title="Engineering Knowledge Graph",
    description="Query your infrastructure with natural language",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: dict = None
    raw_result: dict = None


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/stats")
async def get_stats():
    try:
        stats = query_engine.get_graph_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nodes")
async def get_nodes(type: str = None):
    try:
        nodes = query_engine.get_nodes(node_type=type)
        return {"nodes": nodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nodes/{node_id}")
async def get_node(node_id: str):
    try:
        node = query_engine.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph")
async def get_graph():
    try:
        nodes = query_engine.get_nodes()
        edges = storage.get_all_edges()
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        schema = intent_parser.get_graph_schema()
        
        intent_data = llm_client.parse_query(
            request.message,
            schema,
            llm_client.conversation_history,
        )
        
        if intent_data.get("clarification"):
            llm_client.add_to_history("user", request.message)
            llm_client.add_to_history("assistant", intent_data["clarification"])
            return ChatResponse(
                response=intent_data["clarification"],
                intent=intent_data,
            )
        
        result = intent_parser.execute_intent(intent_data)
        
        formatted_response = llm_client.format_response(
            request.message,
            result,
            schema,
        )
        
        llm_client.add_to_history("user", request.message)
        llm_client.add_to_history("assistant", formatted_response)
        
        return ChatResponse(
            response=formatted_response,
            intent=intent_data,
            raw_result=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/clear")
async def clear_chat():
    llm_client.clear_history()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
