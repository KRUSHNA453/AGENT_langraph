import requests
url = "http://127.0.0.1:8000/api/agents/"
agents = requests.get(url).json()
last_agent = agents[-1]
print("Last agent ID:", last_agent["id"], "NAME:", last_agent["name"])

url_q = "http://127.0.0.1:8000/api/query/"
data = {
    "query": "hello world",
    "pref_cost": 0.33,
    "pref_latency": 0.33,
    "pref_accuracy": 0.34,
    "force_agent_id": last_agent["id"]
}
rs = requests.post(url_q, json=data)
print(rs.json())
