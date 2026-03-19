import json
import requests

BASE = "http://127.0.0.1:8000"


def reg_login(username: str, password: str = "pass12345") -> str:
    r = requests.post(f"{BASE}/api/auth/register", json={"username": username, "password": password})
    if r.status_code == 400:
        r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def create_task(token: str) -> str:
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(
        f"{BASE}/api/tasks/",
        json={"task_type": "new", "description": "new", "requirements": {}},
        headers=h,
    )
    r.raise_for_status()
    return r.json()["id"]


def send_message(token: str, task_id: str, content: str) -> str:
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(
        f"{BASE}/api/messages/",
        json={"task_id": task_id, "user_message": content},
        headers=h,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def get_task(token: str, task_id: str) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}/api/tasks/{task_id}", headers=h)
    r.raise_for_status()
    return r.json()


def get_matches(token: str, task_id: str) -> list[dict]:
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}/api/tasks/{task_id}/matches/", headers=h)
    r.raise_for_status()
    return r.json()["matches"]


def run_flow(username: str, turns: list[str]) -> tuple[str, str, dict, list[str]]:
    token = reg_login(username)
    task_id = create_task(token)
    replies = []
    for turn in turns:
        replies.append(send_message(token, task_id, turn))
    task = get_task(token, task_id)
    return token, task_id, task, replies


def main() -> None:
    scenarios = {
        "iter1_landlord_hf": [
            "我要出租房子，我是房东。公寓，3室，合肥包河区，租金400，2026-06可入住，有家具，有停车位，租期6个月以上。",
            "没有了",
            "确认",
        ],
        "iter1_tenant_hf": [
            "我想租房，我是租客。公寓，3室，合肥包河区，预算400，2026-06入住，需要家具和停车位，租期6个月以上。",
            "没有了",
            "确认",
        ],
        "iter1_tenant_bj": [
            "我想租房，我是租客。公寓，2室，北京海淀，预算800，2026-06入住。",
            "没有了",
            "确认",
        ],
        "iter1_gamer_lol_1": [
            "想找游戏队友，我玩英雄联盟，晚上8-11点，偏好排位。",
            "没有了",
            "确认",
        ],
        "iter1_gamer_lol_2": [
            "想找游戏队友，我玩lol，晚上9-12点，也想排位。",
            "没有了",
            "确认",
        ],
    }

    results: dict[str, dict] = {}
    for username, turns in scenarios.items():
        token, task_id, task, replies = run_flow(username, turns)
        results[username] = {
            "token": token,
            "task_id": task_id,
            "task": task,
            "replies": replies,
        }

    matches_summary: dict[str, list[str]] = {}
    for username in scenarios.keys():
        token = results[username]["token"]
        task_id = results[username]["task_id"]
        matches = get_matches(token, task_id)
        matches_summary[username] = [m["id"] for m in matches]

    output = {
        "tasks": {
            username: {
                "id": data["task_id"],
                "type": data["task"]["task_type"],
                "status": data["task"]["status"],
                "desc": data["task"]["description"],
                "demand_completed": data["task"].get("metadata", {}).get("demand_completed", False),
                "structured_demand": data["task"].get("metadata", {}).get("structured_demand", {}),
                "last_reply": data["replies"][-1] if data["replies"] else "",
            }
            for username, data in results.items()
        },
        "matches": matches_summary,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
