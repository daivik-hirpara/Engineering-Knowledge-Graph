# Engineering Knowledge Graph (EKG)

A prototype system that unifies engineering knowledge across code, infrastructure, and operations into a queryable graph with a natural language interface.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Gemini API Key

### Single Command Startup

```bash
# Set your Gemini API key
export GEMINI_API_KEY=your_api_key_here

# Start the system
docker-compose up --build
```

The system will:
1. Start Neo4j database
2. Parse configuration files (docker-compose.yml, teams.yaml, k8s-deployments.yaml)
3. Build the knowledge graph
4. Start the web interface at http://localhost:8000

### Local Development (Without Docker)

1. Install Neo4j locally and start it on bolt://localhost:7687
2. Create `.env` file:
   ```
   GEMINI_API_KEY=your_api_key_here
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python main.py
   ```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Engineering Knowledge Graph                      │
│                                                                          │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐          │
│  │Connectors │ → │  Graph    │ → │  Query    │ → │   Chat    │          │
│  │           │   │  Storage  │   │  Engine   │   │ Interface │          │
│  └───────────┘   └───────────┘   └───────────┘   └───────────┘          │
│       │               │               │               │                  │
│       ▼               ▼               ▼               ▼                  │
│  Parse YAML       Neo4j DB        Cypher          Gemini 2.5             │
│  configs          persistence     queries         Flash LLM              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Structure

```
vertex/
├── connectors/           # Pluggable configuration parsers
│   ├── base.py          # Base connector interface
│   ├── docker_compose.py # Docker Compose parser
│   ├── teams.py         # Teams configuration parser
│   └── kubernetes.py    # Kubernetes manifests parser (bonus)
├── graph/               # Graph operations
│   ├── storage.py       # Neo4j storage layer
│   └── query.py         # Query engine with traversals
├── chat/                # Natural language interface
│   ├── llm.py           # Gemini API client
│   └── intent.py        # Intent parsing and execution
├── static/              # Web UI
│   ├── index.html       # Main page
│   ├── styles.css       # Styling
│   └── app.js           # D3.js graph visualization
├── data/                # Configuration files to parse
│   ├── docker-compose.yml
│   ├── teams.yaml
│   └── k8s-deployments.yaml
├── main.py              # FastAPI application
├── validate_config.py   # Configuration validation script
├── docker-compose.yml   # Application deployment
├── Dockerfile           # Application container
└── requirements.txt     # Python dependencies
```

## Usage

### Web Interface

Navigate to http://localhost:8000 to access the chat interface.

**Example queries:**
- "Who owns the payment service?"
- "What does order-service depend on?"
- "What breaks if redis-main goes down?"
- "How does api-gateway connect to payments-db?"
- "List all services"
- "What teams are there?"

### API Endpoints

| Endpoint          | Method | Description                             |
| ----------------- | ------ | --------------------------------------- |
| `/`               | GET    | Web UI                                  |
| `/api/health`     | GET    | Health check                            |
| `/api/stats`      | GET    | Graph statistics                        |
| `/api/nodes`      | GET    | List all nodes (optional `type` filter) |
| `/api/nodes/{id}` | GET    | Get specific node                       |
| `/api/graph`      | GET    | Get full graph for visualization        |
| `/api/chat`       | POST   | Natural language query                  |

## Design Questions

### 1. Connector Pluggability
Adding a new connector (e.g., Terraform) requires:
1. Create `connectors/terraform.py` inheriting from `BaseConnector`
2. Implement the `parse()` method returning `(nodes, edges)` tuples
3. Import and instantiate in `main.py`'s `load_graph()` function

No changes to core code needed - the connector system uses a simple interface pattern.

### 2. Graph Updates
When configuration files change:
1. On startup, `clear_all()` removes existing nodes/edges
2. Connectors re-parse all config files
3. Graph is rebuilt with fresh data

For production, an incremental approach with file hashing and diffing would be more efficient.

### 3. Cycle Handling
Cycles are handled by:
1. Neo4j's Cypher queries use path length limits (`*1..10`)
2. `DISTINCT` keyword ensures nodes appear only once in results
3. The graph structure naturally avoids cycles in dependency relationships

### 4. Query Mapping
Natural language to graph queries:
1. LLM (Gemini 2.5 Flash) classifies intent into predefined categories
2. Intent parser extracts parameters (node IDs, team names)
3. Query engine executes appropriate Cypher traversals
4. LLM formats results into human-readable responses

### 5. Failure Handling
When queries can't be answered:
1. Unknown intents return helpful error messages suggesting valid query types
2. Node resolution fails gracefully with "Could not find X" messages
3. LLM is instructed to ask for clarification rather than hallucinate
4. JSON parsing errors default to asking for rephrasing

### 6. Scale Considerations
At 10K nodes, bottlenecks would emerge:
1. **Graph loading**: Bulk upserts would need batching
2. **Traversal queries**: Add depth limits and pagination
3. **LLM context**: Schema summary would need compression
4. **Visualization**: Implement clustering and progressive loading

## Tradeoffs & Limitations

### Intentional Simplifications
- Graph is rebuilt from scratch on each startup (no incremental updates)
- No authentication or authorization
- Single-user session (conversation history not persisted)
- Limited to 10-hop traversals

### Weakest Parts
- Ownership edge resolution relies on name matching heuristics
- LLM intent classification can fail on ambiguous queries
- No caching layer for repeated queries

### With 20 More Hours
- Add incremental graph updates with file watchers
- Implement query result caching
- Add user authentication
- Build admin interface for managing connectors
- Add more connector types (Terraform, AWS, GitHub)
- Improve graph visualization with better layout algorithms

## AI Usage

### AI Assistance
- Connectors: AI helped generate boilerplate parsing logic
- Query Engine: AI suggested Cypher patterns for traversals
- Web UI: AI generated D3.js visualization code
- Intent Parsing: AI designed the prompt engineering approach

### Corrections Made
- Fixed Neo4j connection handling for async contexts
- Adjusted Cypher queries for proper edge type filtering
- Refined LLM prompts to reduce hallucination

### Lessons Learned
- AI excels at boilerplate but needs guidance on architecture
- Prompt engineering is crucial for reliable intent classification
- Code review of AI suggestions prevents subtle bugs

## Bonus Features

- ✅ Kubernetes connector implemented
- ✅ Graph visualization in browser (D3.js)
- ✅ Configuration validation script
- ⬜ Live deployment (not implemented)

## Environment Variables

| Variable         | Description           | Default                 |
| ---------------- | --------------------- | ----------------------- |
| `GEMINI_API_KEY` | Google Gemini API key | Required                |
| `NEO4J_URI`      | Neo4j connection URI  | `bolt://localhost:7687` |
| `NEO4J_USER`     | Neo4j username        | `neo4j`                 |
| `NEO4J_PASSWORD` | Neo4j password        | `password`              |

## License

MIT
