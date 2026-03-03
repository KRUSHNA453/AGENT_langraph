from __future__ import annotations

import os
import re
import random
from typing import Any, Dict, List, Optional, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph


class RouterState(TypedDict, total=False):
    query: str
    prefs: Dict[str, float]
    candidates: List[Dict[str, Any]]
    normalized_prefs: Dict[str, float]
    capability_scores: Dict[str, float]
    filtered_candidates: List[Dict[str, Any]]
    scored_candidates: List[Dict[str, Any]]
    selected: Optional[Dict[str, Any]]
    response: Optional[str]
    error: Optional[str]


class RoutingAgent:
    """
    A LangGraph-based router that chooses the best marketplace agent by combining:
    - capability relevance (lexical + optional HF semantic signal)
    - weighted cost/latency/accuracy preferences
    """

    _INTENT_KEYWORDS = {
        "math": (
            "math",
            "algebra",
            "calculus",
            "equation",
            "integral",
            "derivative",
            "proof",
            "solve",
        ),
        "code": (
            "code",
            "coding",
            "program",
            "programming",
            "python",
            "javascript",
            "debug",
            "function",
            "algorithm",
        ),
        "creative": (
            "creative",
            "poem",
            "poetry",
            "poetic",
            "story",
            "narrative",
            "copywriting",
            "marketing",
        ),
    }

    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        self.hf_embedding_model = os.getenv(
            "HF_ROUTER_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.enable_semantic_routing = (
            os.getenv("HF_ENABLE_SEMANTIC_ROUTING", "false").strip().lower() == "true"
        )
        self.async_client = httpx.AsyncClient(timeout=60.0)
        self.graph = self._build_graph()
        
    async def close(self):
        await self.async_client.aclose()

    def _build_graph(self):
        graph = StateGraph(RouterState)
        graph.add_node("normalize_preferences", self._normalize_preferences_node)
        graph.add_node("capability_filter", self._capability_filter_node)
        graph.add_node("score_candidates", self._score_candidates_node)
        graph.add_node("select_best", self._select_best_node)
        graph.add_node("invoke_agent", self._invoke_agent_node)
        graph.add_node("fallback_agent", self._fallback_agent_node)

        graph.add_edge(START, "normalize_preferences")
        graph.add_edge("normalize_preferences", "capability_filter")
        graph.add_edge("capability_filter", "score_candidates")
        graph.add_edge("score_candidates", "select_best")
        graph.add_edge("select_best", "invoke_agent")

        graph.add_conditional_edges(
            "invoke_agent",
            lambda state: "fallback_agent" if state.get("error") else END,
            {"fallback_agent": "fallback_agent", END: END}
        )
        graph.add_conditional_edges(
            "fallback_agent",
            lambda state: "invoke_agent" if state.get("selected") else END,
            {"invoke_agent": "invoke_agent", END: END}
        )
        return graph.compile()

    async def ainvoke_agent(self, state: RouterState) -> RouterState:
        return await self.graph.ainvoke(state)

    def select_best_agent(
        self,
        query: str,
        candidate_agents: List[Dict[str, Any]],
        prefs: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        if not candidate_agents:
            return None

        final_state = self.graph.invoke(
            {
                "query": query,
                "prefs": prefs,
                "candidates": candidate_agents,
            }
        )
        return final_state.get("selected")

    async def aselect_best_agent_and_invoke(
        self,
        query: str,
        candidate_agents: List[Dict[str, Any]],
        prefs: Dict[str, float]
    ) -> RouterState:
        if not candidate_agents:
            return {"error": "No candidates provided", "response": None}

        state: RouterState = {
            "query": query,
            "prefs": prefs,
            "candidates": candidate_agents,
        }
        return await self.ainvoke_agent(state)

    def _normalize_preferences_node(self, state: RouterState) -> Dict[str, Any]:
        prefs = state.get("prefs") or {}
        cost = float(prefs.get("cost", 0.33))
        latency = float(prefs.get("latency", 0.33))
        accuracy = float(prefs.get("accuracy", 0.33))
        total = cost + latency + accuracy

        if total <= 0:
            normalized = {"cost": 0.33, "latency": 0.33, "accuracy": 0.34}
        else:
            normalized = {
                "cost": cost / total,
                "latency": latency / total,
                "accuracy": accuracy / total,
            }
        return {"normalized_prefs": normalized}

    async def _capability_filter_node(self, state: RouterState) -> Dict[str, Any]:
        query = (state.get("query") or "").strip()
        candidates = state.get("candidates") or []
        if not candidates:
            return {"filtered_candidates": [], "capability_scores": {}}

        semantic_scores: Dict[str, float] = {}
        if self.hf_token and self.enable_semantic_routing:
            semantic_scores = await self._semantic_capability_scores(query, candidates)

        filtered_candidates: List[Dict[str, Any]] = []
        capability_scores: Dict[str, float] = {}
        specialist_matches: List[Dict[str, Any]] = []
        intent_aligned_matches: List[Dict[str, Any]] = []

        for agent in candidates:
            name = agent.get("name", "")
            tags = self._parse_tags(agent.get("capabilities", ""))
            lexical_score = self._lexical_capability_score(query, tags)
            semantic_score = semantic_scores.get(name, 0.0)
            intent_bonus = self._intent_bonus(query, tags)

            if "general" in tags and lexical_score == 0 and intent_bonus == 0:
                lexical_score = 0.15

            # Capability signal favors lexical certainty, semantic fallback, and intent/domain bonus.
            capability_score = min(
                1.0, (0.7 * lexical_score) + (0.2 * semantic_score) + intent_bonus
            )
            capability_scores[name] = capability_score

            specialist_signal = lexical_score + intent_bonus
            is_relevant = (
                specialist_signal > 0
                or semantic_score >= 0.35
                or "general" in tags
                or len(tags) == 0
            )
            if is_relevant:
                filtered_candidates.append(agent)
            if specialist_signal >= 0.18 and "general" not in tags:
                specialist_matches.append(agent)
            if intent_bonus > 0 and "general" not in tags:
                intent_aligned_matches.append(agent)

        # Intent-aligned specialists take precedence; otherwise use lexical specialists.
        if intent_aligned_matches:
            filtered_candidates = intent_aligned_matches
        elif specialist_matches:
            filtered_candidates = specialist_matches

        if not filtered_candidates:
            filtered_candidates = candidates
            for agent in filtered_candidates:
                capability_scores.setdefault(agent.get("name", ""), 0.0)

        return {
            "filtered_candidates": filtered_candidates,
            "capability_scores": capability_scores,
        }

    def _score_candidates_node(self, state: RouterState) -> Dict[str, Any]:
        candidates = state.get("filtered_candidates") or []
        prefs = state.get("normalized_prefs") or {"cost": 0.33, "latency": 0.33, "accuracy": 0.34}
        capability_scores = state.get("capability_scores") or {}

        if not candidates:
            return {"scored_candidates": []}

        costs = [float(a.get("cost_per_request", 0.0)) for a in candidates]
        latencies = [float(a.get("average_latency_ms", 0.0)) for a in candidates]
        min_cost, max_cost = min(costs), max(costs)
        min_lat, max_lat = min(latencies), max(latencies)

        def normalize_inverse(value: float, min_v: float, max_v: float) -> float:
            if max_v - min_v <= 1e-12:
                return 1.0
            return 1.0 - ((value - min_v) / (max_v - min_v))

        scored = []
        for agent in candidates:
            cost = float(agent.get("cost_per_request", 0.0))
            latency = float(agent.get("average_latency_ms", 0.0))
            accuracy = float(agent.get("accuracy_score", 0.0))
            accuracy = min(1.0, max(0.0, accuracy))
            call_count = int(agent.get("call_count", 0))

            cost_score = normalize_inverse(cost, min_cost, max_cost)
            latency_score = normalize_inverse(latency, min_lat, max_lat)
            metric_score = (
                prefs["cost"] * cost_score
                + prefs["latency"] * latency_score
                + prefs["accuracy"] * accuracy
            )
            capability_score = capability_scores.get(agent.get("name", ""), 0.0)

            jitter = random.uniform(0.0, 0.02)
            usage_penalty = min(0.1, call_count * 0.001)

            final_score = (0.8 * metric_score) + (0.2 * capability_score) + jitter - usage_penalty
            scored.append(
                {
                    **agent,
                    "_routing_score": final_score,
                    "_metric_score": metric_score,
                    "_capability_score": capability_score,
                }
            )

        scored.sort(key=lambda a: a.get("_routing_score", 0.0), reverse=True)
        return {"scored_candidates": scored}

    def _select_best_node(self, state: RouterState) -> Dict[str, Any]:
        scored = state.get("scored_candidates") or []
        if not scored:
            return {"selected": None}
        selected = dict(scored[0])
        selected.pop("_routing_score", None)
        selected.pop("_metric_score", None)
        selected.pop("_capability_score", None)
        return {"selected": selected}

    async def _invoke_agent_node(self, state: RouterState) -> Dict[str, Any]:
        selected = state.get("selected")
        if not selected:
            return {"error": "No agent selected", "response": None}

        query = state.get("query", "")
        model_id = selected.get("model_id")
        
        if not model_id:
            return {"error": "Selected Hugging Face agent has no model_id configured.", "response": None}

        url = selected.get("api_endpoint") or "https://router.huggingface.co/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        
        system_content = "You are a helpful AI assistant in a multi-agent marketplace."
        
        # --- Live Context Injection ---
        agent_name = selected.get("name", "").lower()
        tags = self._parse_tags(selected.get("capabilities", ""))
        
        if "weather" in tags or "weather" in agent_name:
            try:
                words = re.findall(r'\b\w+\b', query.lower())
                loc = ""
                if "in" in words:
                    loc = words[words.index("in") + 1]
                elif "for" in words:
                    loc = words[words.index("for") + 1]
                else:
                    loc = words[-1] if words else ""

                if loc:
                    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={loc}&count=1&language=en&format=json"
                    geo_res = await self.async_client.get(geo_url, timeout=5.0)
                    data = geo_res.json()
                    if "results" in data:
                        lat = data["results"][0]["latitude"]
                        lon = data["results"][0]["longitude"]
                        country = data["results"][0].get("country", "")
                        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                        w_res = await self.async_client.get(weather_url, timeout=5.0)
                        cw = w_res.json().get("current_weather", {})
                        weather_text = f"{cw.get('temperature')}°C, Wind {cw.get('windspeed')} km/h"
                        query += f"\n\n[SYSTEM INJECTED REAL-TIME DATA] Current live weather in {loc}, {country}: {weather_text}\nUse this exact data to fulfill the user's request. Do not mention your knowledge cutoff."
            except Exception as e:
                print(f"Weather data injection failed: {e}")

        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {"role": "user", "content": query},
            ],
            "max_tokens": 256,
            "temperature": 0.2,
        }

        try:
            response = await self.async_client.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            parsed_res = self._parse_huggingface_response(response.json())
            return {"response": parsed_res, "error": None}
        except Exception as exc:
            return {"error": str(exc), "response": f"Error calling agent: {exc}"}

    def _fallback_agent_node(self, state: RouterState) -> Dict[str, Any]:
        scored = state.get("scored_candidates", [])
        original_error = state.get("error", "Unknown API error")
        if not scored:
            return {"selected": None, "error": original_error}
        
        # Remove the top candidate (which failed) and pop it
        scored.pop(0)

        if not scored:
             return {"selected": None, "error": f"Forced agent failed: {original_error}", "scored_candidates": []}

        selected = dict(scored[0])
        selected.pop("_routing_score", None)
        selected.pop("_metric_score", None)
        selected.pop("_capability_score", None)
        
        return {"selected": selected, "error": None, "scored_candidates": scored}

    @staticmethod
    def _parse_tags(capabilities: str) -> List[str]:
        if not capabilities:
            return []
        return [t.strip().lower() for t in capabilities.split(",") if t.strip()]

    @staticmethod
    def _parse_huggingface_response(payload: Any) -> str:
        if isinstance(payload, dict) and isinstance(payload.get("choices"), list) and payload["choices"]:
            first = payload["choices"][0]
            if isinstance(first, dict):
                message = first.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    reasoning = message.get("reasoning_content")
                    if content:
                        return str(content)
                    if reasoning:
                        return str(reasoning)

        if isinstance(payload, dict):
            if "error" in payload:
                raise RuntimeError(str(payload["error"]))
            for key in ("generated_text", "summary_text", "translation_text", "answer", "text"):
                if key in payload:
                    return str(payload[key])
            return str(payload)

        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                for key in ("generated_text", "summary_text", "translation_text", "answer", "text"):
                    if key in first:
                        return str(first[key])
            return str(payload)

        return str(payload)

    @staticmethod
    def _lexical_capability_score(query: str, tags: List[str]) -> float:
        if not tags:
            return 0.0
        query_lower = query.lower()
        query_terms = RoutingAgent._tokenize_and_normalize(query_lower)
        matched = 0
        for tag in tags:
            tag_terms = RoutingAgent._tokenize_and_normalize(tag)
            prefix_match = any(
                len(t) >= 4 and len(q) >= 4 and (t.startswith(q[:4]) or q.startswith(t[:4]))
                for t in tag_terms
                for q in query_terms
            )
            if tag in query_lower or bool(tag_terms & query_terms) or prefix_match:
                matched += 1
        return matched / max(1, len(tags))

    @staticmethod
    def _normalize_token(token: str) -> str:
        token = re.sub(r"[^a-z0-9]+", "", token.lower())
        if not token:
            return ""

        # Canonicalize common variations used in capabilities and queries.
        if token.startswith("poetr") or token.startswith("poet"):
            return "poet"
        if token.startswith("writ"):
            return "writ"
        if token.startswith("program"):
            return "program"
        if token.startswith("debug"):
            return "debug"
        if token.startswith("calcul"):
            return "calculus"

        for suffix in (
            "ization",
            "ation",
            "ingly",
            "edly",
            "ing",
            "ed",
            "ly",
            "ies",
            "es",
            "s",
            "ic",
        ):
            if len(token) > len(suffix) + 2 and token.endswith(suffix):
                token = token[: -len(suffix)]
                break
        return token

    @staticmethod
    def _tokenize_and_normalize(text: str) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        normalized = set()
        for token in tokens:
            canon = RoutingAgent._normalize_token(token)
            if canon:
                normalized.add(canon)
        return normalized

    def _intent_bonus(self, query: str, tags: List[str]) -> float:
        query_terms = self._tokenize_and_normalize(query)
        if not query_terms:
            return 0.0

        tag_terms: set[str] = set()
        for tag in tags:
            tag_terms.update(self._tokenize_and_normalize(tag))
        if not tag_terms:
            return 0.0

        bonus = 0.0
        for words in self._INTENT_KEYWORDS.values():
            normalized_words = {self._normalize_token(w) for w in words}
            query_hits = len(query_terms & normalized_words)
            if query_hits == 0:
                continue
            tag_hits = len(tag_terms & normalized_words)
            if tag_hits == 0:
                continue
            # 0.28 - 0.40 range for intent-aligned specialists.
            current = min(0.40, 0.20 + (0.08 * min(tag_hits, 3)))
            bonus = max(bonus, current)
        return bonus

    async def _semantic_capability_scores(
        self, query: str, candidates: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        texts = [query] + [a.get("capabilities", "") for a in candidates]
        vectors = await self._hf_embed_texts(texts)
        if not vectors or len(vectors) != len(texts):
            return {}

        query_vec = vectors[0]
        scores: Dict[str, float] = {}
        for idx, agent in enumerate(candidates, start=1):
            sim = self._cosine_similarity(query_vec, vectors[idx])
            # Convert cosine similarity [-1,1] to [0,1].
            scores[agent.get("name", "")] = max(0.0, min(1.0, (sim + 1.0) / 2.0))
        return scores

    async def _hf_embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self.hf_token:
            return None

        # This route is optional and disabled by default. Enable with HF_ENABLE_SEMANTIC_ROUTING=true.
        url = f"https://router.huggingface.co/hf-inference/models/{self.hf_embedding_model}/pipeline/feature-extraction"
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        payload = {"inputs": texts, "options": {"wait_for_model": True}}

        try:
            resp = await self.async_client.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code >= 400:
                return None
            data = resp.json()
        except Exception:
            return None

        if isinstance(data, dict) and data.get("error"):
            return None
        if not isinstance(data, list):
            return None

        vectors: List[List[float]] = []
        for item in data:
            vec = self._pool_embedding(item)
            if not vec:
                return None
            vectors.append(vec)
        return vectors

    @staticmethod
    def _pool_embedding(item: Any) -> Optional[List[float]]:
        # Case 1: item already is a vector [dim]
        if isinstance(item, list) and item and isinstance(item[0], (int, float)):
            return [float(v) for v in item]

        # Case 2: token-level embedding [tokens][dim] -> mean pool across tokens
        if isinstance(item, list) and item and isinstance(item[0], list):
            dims = len(item[0])
            if dims == 0:
                return None
            out = [0.0] * dims
            token_count = 0
            for token_vec in item:
                if not isinstance(token_vec, list) or len(token_vec) != dims:
                    return None
                for idx, value in enumerate(token_vec):
                    out[idx] += float(value)
                token_count += 1
            if token_count == 0:
                return None
            return [v / token_count for v in out]

        return None

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if len(vec_a) != len(vec_b) or not vec_a:
            return 0.0
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for a, b in zip(vec_a, vec_b):
            dot += a * b
            norm_a += a * a
            norm_b += b * b
        if norm_a <= 1e-12 or norm_b <= 1e-12:
            return 0.0
        return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))
