"""
Integration test: simulate real user conversations with the demand definition system.
Covers three user personas / demand types - rental tenant, dating seeker, gaming player.
Run with: python tests/test_demand_integration.py
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"


def register_and_login(username: str, password: str = "testpass123") -> str:
    """Register (or login if exists) and return access token."""
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "password": password})
    if r.status_code == 400:  # already exists → login
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def create_task(token: str) -> str:
    """Create a blank task and return task_id."""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/api/tasks/", json={
        "task_type": "new",
        "description": "test demand",
        "requirements": {}
    }, headers=headers)
    r.raise_for_status()
    return r.json()["id"]


def send_message(token: str, task_id: str, msg: str) -> str:
    """Send a message and return the agent reply text."""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/api/messages/", json={
        "task_id": task_id,
        "user_message": msg
    }, headers=headers)
    r.raise_for_status()
    return r.json()["message"]["content"]


def get_task(token: str, task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/tasks/{task_id}", headers=headers)
    r.raise_for_status()
    return r.json()


# ────────────────────────────────────────────────────────────────────────────
# SCENARIO 1: Rental tenant - brief but information-dense first message
# ────────────────────────────────────────────────────────────────────────────
def scenario_rental_tenant():
    print("\n" + "="*60)
    print("SCENARIO 1: Rental – Tenant (dense first message)")
    print("="*60)

    token = register_and_login("test_tenant_s1")
    task_id = create_task(token)

    turns = [
        "我想在CBD附近租一个两室一厅的公寓，预算每周600刀左右，希望3月底入住",
        "带家具的，需要停车位，最好允许养猫",
        "没有了",   # trigger confirming summary
        "确认",     # actually confirm
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n[User T{i}] {msg}")
        reply = send_message(token, task_id, msg)
        print(f"[Agent  ] {reply}")
        time.sleep(0.3)

    task = get_task(token, task_id)
    print(f"\n[Final task state] type={task['task_type']} status={task['status']}")
    meta = task.get("metadata", {})
    demand = meta.get("structured_demand")
    print(f"[Structured demand] {json.dumps(demand, ensure_ascii=False, indent=2) if demand else 'NOT SAVED'}")
    return task


# ────────────────────────────────────────────────────────────────────────────
# SCENARIO 2: Rental tenant - vague opener, step-by-step conversation
# ────────────────────────────────────────────────────────────────────────────
def scenario_rental_vague():
    print("\n" + "="*60)
    print("SCENARIO 2: Rental – Tenant (vague opener)")
    print("="*60)

    token = register_and_login("test_tenant_s2")
    task_id = create_task(token)

    turns = [
        "你好，我想找房子",
        "我想租单间（一居室），在St Kilda附近，公寓类型",
        "预算嘛500块每周吧，下周就想搬进去",
        "不需要停车，没有宠物，不需要带家具",
        "没有了",   # trigger confirming summary
        "确认",    # actually confirm
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n[User T{i}] {msg}")
        reply = send_message(token, task_id, msg)
        print(f"[Agent  ] {reply}")
        time.sleep(0.3)

    task = get_task(token, task_id)
    meta = task.get("metadata", {})
    demand = meta.get("structured_demand")
    print(f"\n[Final task type={task['task_type']}]")
    print(f"[Structured demand] {json.dumps(demand, ensure_ascii=False, indent=2) if demand else 'NOT SAVED'}")
    return task


# ────────────────────────────────────────────────────────────────────────────
# SCENARIO 3: Dating seeker
# ────────────────────────────────────────────────────────────────────────────
def scenario_dating():
    print("\n" + "="*60)
    print("SCENARIO 3: Dating – Seeker")
    print("="*60)

    token = register_and_login("test_dater_s3")
    task_id = create_task(token)

    turns = [
        "我想找对象",
        "我是女生，25岁，喜欢户外运动，在上海",
        "希望男生，年龄20到30岁，有稳定工作，目的是找长期关系",
        "没有了",   # trigger confirming summary
        "确认",    # actually confirm
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n[User T{i}] {msg}")
        reply = send_message(token, task_id, msg)
        print(f"[Agent  ] {reply}")
        time.sleep(0.3)

    task = get_task(token, task_id)
    meta = task.get("metadata", {})
    demand = meta.get("structured_demand")
    print(f"\n[Final task type={task['task_type']}]")
    print(f"[Structured demand] {json.dumps(demand, ensure_ascii=False, indent=2) if demand else 'NOT SAVED'}")
    return task


# ────────────────────────────────────────────────────────────────────────────
# SCENARIO 4: Gaming player
# ────────────────────────────────────────────────────────────────────────────
def scenario_gaming():
    print("\n" + "="*60)
    print("SCENARIO 4: Gaming – Player finds teammates")
    print("="*60)

    token = register_and_login("test_gamer_s4")
    task_id = create_task(token)

    turns = [
        "想找人一起打王者荣耀",
        "我是钻石段位，每天晚上8-11点在线，想找同段位一起排位",
        "没有了",   # trigger confirming summary
        "确认",    # actually confirm
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n[User T{i}] {msg}")
        reply = send_message(token, task_id, msg)
        print(f"[Agent  ] {reply}")
        time.sleep(0.3)

    task = get_task(token, task_id)
    meta = task.get("metadata", {})
    demand = meta.get("structured_demand")
    print(f"\n[Final task type={task['task_type']}]")
    print(f"[Structured demand] {json.dumps(demand, ensure_ascii=False, indent=2) if demand else 'NOT SAVED'}")
    return task


# ────────────────────────────────────────────────────────────────────────────
# SCENARIO 5: Mid-conversation correction
# ────────────────────────────────────────────────────────────────────────────
def scenario_correction():
    print("\n" + "="*60)
    print("SCENARIO 5: Rental – Tenant corrects a field mid-conversation")
    print("="*60)

    token = register_and_login("test_tenant_s5")
    task_id = create_task(token)

    turns = [
        "我要在Fitzroy租三室两厅（公寓），预算每周700",
        "大概四月入住，需要带家具",
        "我要修改，预算改为600",   # correction
        "没有了",   # trigger confirming summary
        "确认",    # actually confirm
    ]

    for i, msg in enumerate(turns, 1):
        print(f"\n[User T{i}] {msg}")
        reply = send_message(token, task_id, msg)
        print(f"[Agent  ] {reply}")
        time.sleep(0.3)

    task = get_task(token, task_id)
    meta = task.get("metadata", {})
    demand = meta.get("structured_demand")
    print(f"\n[Final task type={task['task_type']}]")
    print(f"[Structured demand] {json.dumps(demand, ensure_ascii=False, indent=2) if demand else 'NOT SAVED'}")
    return task


if __name__ == "__main__":
    results = {}
    for fn in [scenario_rental_tenant, scenario_rental_vague, scenario_dating, scenario_gaming, scenario_correction]:
        try:
            results[fn.__name__] = fn()
        except Exception as e:
            print(f"\n[ERROR in {fn.__name__}] {e}")
            results[fn.__name__] = None

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, task in results.items():
        if task is None:
            print(f"  {name}: ERROR")
            continue
        meta = task.get("metadata", {}) or {}
        completed = meta.get("demand_completed", False)
        demand = meta.get("structured_demand")
        values_count = len(demand.get("values", {})) if demand else 0
        print(f"  {name}: type={task['task_type']} completed={completed} fields_saved={values_count}")
