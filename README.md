# Agentic Matching System

智能体需求匹配系统 - 一个基于智能体对话的需求匹配系统

## 快速启动

### 方式 1：使用 Shell 脚本 (macOS/Linux)

```bash
./start.sh
```

### 方式 2：使用 Python 脚本 (跨平台)

```bash
python3 start.py
```

### 方式 3：手动启动

1. 创建虚拟环境：
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入你的 OPENAI_API_KEY
   ```

4. 启动服务器：
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

然后访问 http://localhost:8000

## 项目结构

```
agentic_matching/
├── backend/
│   ├── models.py        # 数据模型
│   ├── storage.py       # 存储层
│   ├── agent_system.py  # 智能体系统
│   └── main.py          # FastAPI 服务
├── static/
│   └── index.html       # Web 前端
├── start.sh             # Shell 启动脚本
├── start.py             # Python 启动脚本
├── requirements.txt
└── .env
```

