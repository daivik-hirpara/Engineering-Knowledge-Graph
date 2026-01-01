import os
import json
from google import genai
from google.genai import types


class LLMClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-flash"
        self.conversation_history = []

    def get_system_prompt(self, graph_schema: dict) -> str:
        return f"""You are an Engineering Knowledge Graph assistant. You help users query and understand their infrastructure.

## Available Graph Data
{json.dumps(graph_schema, indent=2)}

## Your Capabilities
You can answer questions about:
- **Ownership**: Who owns a service/database? What does a team own?
- **Dependencies**: What does a service depend on? What services use a resource?
- **Blast Radius**: What breaks if something goes down? What's the impact?
- **Paths**: How does service A connect to service B?
- **Exploration**: List all services, databases, teams, etc.

## Response Format
When answering queries, you will receive structured data from the graph. Format your responses to be:
1. Clear and concise
2. Highlight the most important information first
3. Use bullet points for lists
4. Include oncall contacts when relevant

## Query Intent Classification
For each user query, you must determine the intent and required parameters:
- OWNERSHIP: node_id or team_name
- DEPENDENCY_DOWNSTREAM: node_id (what does X depend on?)
- DEPENDENCY_UPSTREAM: node_id (what uses X?)
- BLAST_RADIUS: node_id
- PATH: from_id, to_id
- LIST_NODES: node_type (service, database, cache, team)
- NODE_INFO: node_id
- SEARCH: query_text

Respond with a JSON object containing:
{{
    "intent": "INTENT_TYPE",
    "params": {{}},
    "clarification": null or "question if needed"
}}

If the query is ambiguous, ask for clarification."""

    def parse_query(self, user_query: str, graph_schema: dict, context: list = None) -> dict:
        system_prompt = self.get_system_prompt(graph_schema)
        
        messages = []
        if context:
            for ctx in context[-4:]:
                role = "model" if ctx["role"] == "assistant" else ctx["role"]
                messages.append({"role": role, "parts": [{"text": ctx["content"]}]})
        
        messages.append({"role": "user", "parts": [{"text": f"Parse this query and return only the JSON intent object: {user_query}"}]})
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=messages,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
            ),
        )
        
        response_text = response.text.strip()
        
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                "intent": "UNKNOWN",
                "params": {},
                "clarification": "I couldn't understand your query. Could you rephrase it?"
            }

    def format_response(self, user_query: str, query_result: dict, graph_schema: dict) -> str:
        system_prompt = """You are an Engineering Knowledge Graph assistant. Format the query results into a helpful, human-readable response.

Be concise but complete. Use bullet points for lists. Highlight important information like oncall contacts.
Do not make up information - only use what's provided in the query result."""

        prompt = f"""User asked: {user_query}

Query result data:
{json.dumps(query_result, indent=2)}

Format this into a helpful response for the user."""

        response = self.client.models.generate_content(
            model=self.model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
            ),
        )
        
        return response.text.strip()

    def add_to_history(self, role: str, content: str) -> None:
        self.conversation_history.append({
            "role": "assistant" if role == "assistant" else role,
            "content": content
        })
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

    def clear_history(self) -> None:
        self.conversation_history = []
