# AgentComm Protocol (ACP) - 智能体通信协议设计

## 一、协议概述

**AgentComm Protocol (ACP)** 是一个结构化的智能体通信协议，用于规范智能体、用户、系统三方之间的信息交换格式。该协议确保模型输入能够融合多源信息，模型输出能够被准确解析并分发到不同目标。

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **多源输入融合** | 支持用户输入、系统指令、上下文记忆等多来源信息 |
| **多目标输出分离** | 输出内容可明确区分：对用户响应、对系统指令、状态更新 |
| **严格格式定义** | 使用结构化标记，便于解析 |
| **状态感知** | 包含需求定义进展、任务状态等元信息 |
| **可扩展性** | 支持新场景、新指令类型的添加 |

---

## 二、协议格式定义

### 2.1 整体结构

```
[ACP v1.0]
<session>
  session_id: {session_id}
  timestamp: {timestamp}
  turn_count: {turn_count}
</session>

<context>
  demand_type: {demand_type}
  current_state: {state}
  completed_required: {completed_count}/{total_required}
  pending_fields: [{field1}, {field2}, ...]
</context>

<input>
  <user>
    {user_message}
  </user>
  
  <system>
    <instruction priority="high|medium|low">
      {system_instruction}
    </instruction>
    <constraints>
      {system_constraints}
    </constraints>
  </system>
  
  <memory>
    <short_term>
      {recent_conversation}
      extracted_info: {extracted_info_json}
    </short_term>
    <long_term>
      prefilled: {prefilled_json}
      user_profile: {profile_summary}
    </long_term>
  </memory>
</input>

<output>
  <to_user>
    {response_to_user}
  </to_user>
  
  <to_system>
    <status_update>
      state: {new_state}
      completion_ratio: {ratio}
      can_enter_matching: {true/false}
    </status_update>
    
    <extracted>
      {extracted_fields_json}
    </extracted>
    
    <pending>
      {pending_fields_json}
    </pending>
    
    <custom_requirements>
      {custom_requirements_list}
    </custom_requirements>
    
    <actions>
      {system_actions_json}
    </actions>
  </to_system>
  
  <metadata>
    confidence: {overall_confidence}
    processing_time_ms: {time}
    model: {model_name}
  </metadata>
</output>
```

### 2.2 详细字段说明

#### 会话标识区 `<session>`
```xml
<session>
  session_id: "sess_789012"                # 会话ID
  timestamp: "2026-03-10T14:30:00Z"        # 时间戳
  turn_count: 5                             # 当前对话轮次
  user_id: "u_123456"                       # 用户ID（可选）
</session>
```

#### 上下文区 `<context>`
```xml
<context>
  demand_type: "rental"                      # 需求类型
  role: "tenant"                              # 用户角色
  current_state: "filling_required"           # 当前状态
  completed_required: "3/5"                    # 必填项完成情况
  completed_optional: "1/8"                    # 选填项完成情况
  pending_fields: ["move_in_date", "furnished"] # 待填字段
  matching_readiness: 0.6                      # 匹配就绪度 0-1
</context>
```

#### 输入区 `<input>`

**用户输入 `<user>`**
```xml
<user>
  <message id="msg_001">
    我想找墨尔本大学附近的两室一厅，预算600左右
  </message>
  <message id="msg_002" type="modification">
    预算提高到700吧
  </message>
</user>
```

**系统指令 `<system>`**
```xml
<system>
  <instruction priority="high">
    判断当前需求定义是否已完成必填项，如果完成则输出can_enter_matching=true
  </instruction>
  
  <instruction priority="medium">
    从用户消息中提取所有实体信息，更新extracted字段
  </instruction>
  
  <constraints>
    - 响应语言使用中文
    - 每次最多询问一个必填项
    - 如果用户表达不确定，提供选项参考
  </constraints>
  
  <rules>
    - 当连续3次用户无法回答时，标记为可完成
    - 价格单位统一为AUD/week
  </rules>
</system>
```

**记忆区 `<memory>`**
```xml
<memory>
  <short_term>
    <conversation>
      <turn role="user" turn_id="1">我想在墨尔本找房子</turn>
      <turn role="assistant" turn_id="2">好的，您是想租房还是买房？</turn>
      <turn role="user" turn_id="3">租房，两室一厅</turn>
    </conversation>
    
    <extracted_info>
      {
        "property_type": "apartment",
        "bedrooms": 2,
        "location_area": "墨尔本",
        "intent": "rental"
      }
    </extracted_info>
    
    <mentioned_custom>
      ["近火车站"]
    </mentioned_custom>
  </short_term>
  
  <long_term>
    <prefilled>
      {
        "max_price": 600,
        "furnished": true,
        "amenities": ["gym", "balcony"]
      }
    </prefilled>
    
    <profile_summary>
      {
        "age": 28,
        "occupation": "software_engineer",
        "verified": ["identity", "income"],
        "history_count": 12,
        "success_rate": 0.85
      }
    </profile_summary>
    
    <preferences>
      {
        "rental": {
          "property_type": "apartment",
          "max_price": 600,
          "bedrooms": 2
        }
      }
    </preferences>
  </long_term>
</memory>
```

#### 输出区 `<output>`

**对用户响应 `<to_user>`**
```xml
<to_user>
  <message type="response" priority="normal">
    好的，已为您更新预算为$700/周。根据您的需求，我还需要了解：
    1. 您计划什么时候入住？
    2. 您需要带家具的房子吗？
    
    您可以随时告诉我这些信息，或者直接说"开始匹配"跳过可选问题。
  </message>
  
  <suggestions>
    - 2月1日入住
    - 3月1日入住
    - 时间灵活
  </suggestions>
</to_user>
```

**对系统输出 `<to_system>`**
```xml
<to_system>
  <status_update>
    <state>filling_optional</state>
    <completion_ratio>0.7</completion_ratio>
    <can_enter_matching>false</can_enter_matching>
    <readiness_reason>missing_required_fields: move_in_date</readiness_reason>
  </status_update>
  
  <extracted>
    {
      "property_type": "apartment",
      "bedrooms": 2,
      "max_price": 700,
      "location": "墨尔本大学附近",
      "move_in_date": null,
      "furnished": null
    }
  </extracted>
  
  <pending_fields>
    [
      {
        "name": "move_in_date",
        "type": "date",
        "required": true,
        "prompt": "您计划什么时候入住？"
      },
      {
        "name": "furnished",
        "type": "enum",
        "options": ["yes", "no", "partial"],
        "required": false,
        "prompt": "您需要带家具吗？"
      }
    ]
  </pending_fields>
  
  <custom_requirements>
    [
      {
        "text": "近火车站",
        "confidence": 0.9,
        "importance": "high",
        "embedding": [0.123, 0.456, ...]
      }
    ]
  </custom_requirements>
  
  <actions>
    [
      {
        "action": "update_memory",
        "target": "short_term.extracted_info",
        "value": {"max_price": 700}
      },
      {
        "action": "check_completion",
        "condition": "required_fields_filled",
        "next": "ready_for_matching"
      }
    ]
  </actions>
  
  <diagnostics>
    <confidence_scores>
      <entity name="property_type">0.95</entity>
      <entity name="bedrooms">0.98</entity>
      <entity name="max_price">0.92</entity>
      <entity name="location">0.85</entity>
    </confidence_scores>
    
    <ambiguities>
      用户提到的"600左右"被理解为最高预算，准确率92%
    </ambiguities>
  </diagnostics>
</to_system>
```

**元数据 `<metadata>`**
```xml
<metadata>
  <version>ACP v1.0</version>
  <processing_time_ms>342</processing_time_ms>
  <model>gpt-4-turbo</model>
  <token_count>
    <input>1245</input>
    <output>876</output>
  </token_count>
  <confidence>0.88</confidence>
</metadata>
```

---

## 三、协议使用示例

### 3.1 完整输入示例

```xml
[ACP v1.0]
<session>
  session_id: "sess_789012"
  timestamp: "2026-03-10T14:30:00Z"
  turn_count: 5
</session>

<context>
  demand_type: "rental"
  role: "tenant"
  current_state: "filling_required"
  completed_required: "3/5"
  pending_fields: ["move_in_date", "furnished"]
</context>

<input>
  <user>
    预算提高到700吧
  </user>
  
  <system>
    <instruction priority="high">
      1. 更新extracted_info中的max_price为700
      2. 检查必填项是否已全部完成
      3. 如果完成，设置can_enter_matching=true
    </instruction>
    
    <constraints>
      - 保持友好的对话语气
      - 确认变更前先向用户确认
    </constraints>
  </system>
  
  <memory>
    <short_term>
      <extracted_info>
        {
          "property_type": "apartment",
          "bedrooms": 2,
          "max_price": 600,
          "location": "墨尔本大学附近"
        }
      </extracted_info>
    </short_term>
    
    <long_term>
      <prefilled>
        {
          "furnished": true
        }
      </prefilled>
    </long_term>
  </memory>
</input>
```

### 3.2 完整输出示例

```xml
[ACP v1.0]
<session>
  session_id: "sess_789012"
  timestamp: "2026-03-10T14:30:05Z"
  turn_count: 6
</session>

<context>
  demand_type: "rental"
  role: "tenant"
  current_state: "filling_required"
  completed_required: "4/5"
  pending_fields: ["move_in_date"]
</context>

<output>
  <to_user>
    <message>
      好的，已将您的预算更新为$700/周。

      根据您的需求，我现在还需要知道：
      您计划什么时候入住？

      您可以告诉我具体日期，比如"2月1日"，或者选择：
      • 尽快入住
      • 时间灵活
    </message>
    
    <suggestions>
      尽快入住
      2月1日
      3月1日
      时间灵活
    </suggestions>
  </to_user>
  
  <to_system>
    <status_update>
      <state>filling_required</state>
      <completion_ratio>0.8</completion_ratio>
      <can_enter_matching>false</can_enter_matching>
      <readiness_reason>missing_move_in_date</readiness_reason>
    </status_update>
    
    <extracted>
      {
        "property_type": "apartment",
        "bedrooms": 2,
        "max_price": 700,
        "location": "墨尔本大学附近",
        "furnished": true
      }
    </extracted>
    
    <pending_fields>
      [
        {
          "name": "move_in_date",
          "type": "date",
          "required": true,
          "prompt": "您计划什么时候入住？"
        }
      ]
    </pending_fields>
    
    <actions>
      [
        {
          "action": "update_memory",
          "target": "short_term.extracted_info.max_price",
          "value": 700
        },
        {
          "action": "log",
          "level": "info",
          "message": "预算从600更新为700"
        }
      ]
    </actions>
  </to_system>
  
  <metadata>
    <processing_time_ms>287</processing_time_ms>
    <model>gpt-4-turbo</model>
    <confidence>0.94</confidence>
  </metadata>
</output>
```

---

## 四、协议解析器实现

```python
# acp_parser.py

import re
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ACPVersion(Enum):
    V1_0 = "ACP v1.0"

@dataclass
class ACPSession:
    session_id: str
    timestamp: str
    turn_count: int
    user_id: Optional[str] = None

@dataclass
class ACPContext:
    demand_type: str
    role: Optional[str]
    current_state: str
    completed_required: str
    completed_optional: Optional[str]
    pending_fields: list
    matching_readiness: Optional[float]

@dataclass
class ACPInput:
    user_messages: list
    system_instructions: list
    constraints: list
    short_term_memory: Dict
    long_term_memory: Dict

@dataclass
class ACPOutput:
    to_user: Dict
    to_system: Dict
    metadata: Dict

class ACPParser:
    """ACP协议解析器"""
    
    def __init__(self):
        self.version_pattern = r'\[ACP (v\d+\.\d+)\]'
        self.tag_pattern = r'<(\w+)>(.*?)</\1>'
    
    def parse_input(self, acp_text: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        解析输入格式的ACP文本
        返回: (version, parsed_data)
        """
        # 提取版本
        version_match = re.search(self.version_pattern, acp_text)
        version = version_match.group(1) if version_match else None
        
        parsed = {}
        
        # 提取各个区块
        blocks = re.findall(self.tag_pattern, acp_text, re.DOTALL)
        for tag, content in blocks:
            if tag == 'session':
                parsed['session'] = self._parse_session(content)
            elif tag == 'context':
                parsed['context'] = self._parse_context(content)
            elif tag == 'input':
                parsed['input'] = self._parse_input_block(content)
            elif tag == 'memory':
                parsed['memory'] = self._parse_memory(content)
        
        return version, parsed
    
    def parse_output(self, acp_text: str) -> Tuple[Optional[str], ACPOutput]:
        """
        解析输出格式的ACP文本
        """
        version, parsed = self.parse_input(acp_text)
        
        output_block = parsed.get('output', {})
        
        return version, ACPOutput(
            to_user=output_block.get('to_user', {}),
            to_system=output_block.get('to_system', {}),
            metadata=output_block.get('metadata', {})
        )
    
    def _parse_session(self, content: str) -> ACPSession:
        """解析session块"""
        data = {}
        for line in content.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
        
        return ACPSession(
            session_id=data.get('session_id', ''),
            timestamp=data.get('timestamp', ''),
            turn_count=int(data.get('turn_count', 0)),
            user_id=data.get('user_id')
        )
    
    def _parse_context(self, content: str) -> ACPContext:
        """解析context块"""
        data = {}
        for line in content.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
        
        # 解析pending_fields
        pending = data.get('pending_fields', '[]')
        if pending.startswith('[') and pending.endswith(']'):
            try:
                pending_fields = json.loads(pending.replace("'", '"'))
            except:
                pending_fields = []
        else:
            pending_fields = []
        
        return ACPContext(
            demand_type=data.get('demand_type', ''),
            role=data.get('role'),
            current_state=data.get('current_state', ''),
            completed_required=data.get('completed_required', '0/0'),
            completed_optional=data.get('completed_optional'),
            pending_fields=pending_fields,
            matching_readiness=float(data.get('matching_readiness', 0))
        )
    
    def _parse_input_block(self, content: str) -> Dict:
        """解析input块"""
        result = {}
        
        # 解析user块
        user_match = re.search(r'<user>(.*?)</user>', content, re.DOTALL)
        if user_match:
            user_content = user_match.group(1).strip()
            # 解析多个message
            messages = re.findall(r'<message[^>]*>(.*?)</message>', user_content, re.DOTALL)
            if messages:
                result['user_messages'] = messages
            else:
                result['user_messages'] = [user_content]
        
        # 解析system块
        system_match = re.search(r'<system>(.*?)</system>', content, re.DOTALL)
        if system_match:
            system_content = system_match.group(1)
            instructions = re.findall(r'<instruction[^>]*>(.*?)</instruction>', system_content, re.DOTALL)
            result['system_instructions'] = instructions
            
            constraints_match = re.search(r'<constraints>(.*?)</constraints>', system_content, re.DOTALL)
            if constraints_match:
                constraints = constraints_match.group(1).strip().split('\n')
                result['constraints'] = [c.strip('- ').strip() for c in constraints if c.strip()]
        
        return result
    
    def _parse_memory(self, content: str) -> Dict:
        """解析memory块"""
        result = {}
        
        # 解析short_term
        st_match = re.search(r'<short_term>(.*?)</short_term>', content, re.DOTALL)
        if st_match:
            st_content = st_match.group(1)
            
            # 提取conversation
            conv_match = re.search(r'<conversation>(.*?)</conversation>', st_content, re.DOTALL)
            if conv_match:
                turns = re.findall(r'<turn[^>]*>(.*?)</turn>', conv_match.group(1), re.DOTALL)
                result['conversation'] = turns
            
            # 提取extracted_info
            ext_match = re.search(r'<extracted_info>(.*?)</extracted_info>', st_content, re.DOTALL)
            if ext_match:
                try:
                    result['extracted_info'] = json.loads(ext_match.group(1).strip())
                except:
                    result['extracted_info'] = {}
        
        # 解析long_term
        lt_match = re.search(r'<long_term>(.*?)</long_term>', content, re.DOTALL)
        if lt_match:
            lt_content = lt_match.group(1)
            
            prefilled_match = re.search(r'<prefilled>(.*?)</prefilled>', lt_content, re.DOTALL)
            if prefilled_match:
                try:
                    result['prefilled'] = json.loads(prefilled_match.group(1).strip())
                except:
                    result['prefilled'] = {}
        
        return result
    
    def build_input_prompt(self, 
                          session_id: str,
                          user_message: str,
                          context: Dict,
                          short_term_memory: Dict,
                          long_term_memory: Dict,
                          system_instructions: list = None) -> str:
        """
        构建输入提示词
        """
        lines = []
        
        # 版本头
        lines.append("[ACP v1.0]")
        
        # session
        lines.append("<session>")
        lines.append(f"  session_id: {session_id}")
        lines.append(f"  timestamp: {datetime.now().isoformat()}Z")
        lines.append(f"  turn_count: {context.get('turn_count', 0)}")
        if 'user_id' in context:
            lines.append(f"  user_id: {context['user_id']}")
        lines.append("</session>")
        lines.append("")
        
        # context
        lines.append("<context>")
        lines.append(f"  demand_type: {context.get('demand_type', 'unknown')}")
        lines.append(f"  role: {context.get('role', 'unknown')}")
        lines.append(f"  current_state: {context.get('current_state', 'initial')}")
        lines.append(f"  completed_required: {context.get('completed_required', '0/0')}")
        if 'completed_optional' in context:
            lines.append(f"  completed_optional: {context['completed_optional']}")
        lines.append(f"  pending_fields: {json.dumps(context.get('pending_fields', []))}")
        lines.append("</session>")
        lines.append("")
        
        # input
        lines.append("<input>")
        lines.append("  <user>")
        lines.append(f"    {user_message}")
        lines.append("  </user>")
        lines.append("")
        
        if system_instructions:
            lines.append("  <system>")
            for inst in system_instructions:
                lines.append(f'    <instruction priority="high">')
                lines.append(f"      {inst}")
                lines.append(f'    </instruction>')
            lines.append("  </system>")
            lines.append("")
        
        lines.append("  <memory>")
        lines.append("    <short_term>")
        if 'conversation' in short_term_memory:
            lines.append("      <conversation>")
            for turn in short_term_memory['conversation'][-5:]:  # 最近5轮
                lines.append(f"        <turn role=\"{turn['role']}\">{turn['message']}</turn>")
            lines.append("      </conversation>")
        
        if 'extracted_info' in short_term_memory:
            lines.append(f"      <extracted_info>")
            lines.append(f"        {json.dumps(short_term_memory['extracted_info'], indent=2, ensure_ascii=False)}")
            lines.append(f"      </extracted_info>")
        lines.append("    </short_term>")
        lines.append("")
        
        lines.append("    <long_term>")
        if 'prefilled' in long_term_memory:
            lines.append(f"      <prefilled>")
            lines.append(f"        {json.dumps(long_term_memory['prefilled'], indent=2, ensure_ascii=False)}")
            lines.append(f"      </prefilled>")
        lines.append("    </long_term>")
        lines.append("  </memory>")
        lines.append("</input>")
        
        return "\n".join(lines)
    
    def extract_output(self, model_response: str) -> Dict:
        """
        从模型响应中提取输出
        """
        _, output = self.parse_output(model_response)
        
        return {
            'to_user': output.to_user.get('message', ''),
            'suggestions': output.to_user.get('suggestions', []),
            'status': output.to_system.get('status_update', {}),
            'extracted': output.to_system.get('extracted', {}),
            'pending': output.to_system.get('pending_fields', []),
            'actions': output.to_system.get('actions', []),
            'metadata': output.metadata
        }
```

---

## 五、在智能体系统中的集成

### 5.1 智能体处理流程

```python
# agent_with_acp.py

class ACPAgent:
    """使用ACP协议的智能体"""
    
    def __init__(self, llm_client, memory_service):
        self.llm = llm_client
        self.memory = memory_service
        self.parser = ACPParser()
    
    async def process_message(self, 
                            session_id: str,
                            user_message: str,
                            user_id: str = None):
        """
        处理用户消息，使用ACP协议
        """
        # 1. 加载记忆
        short_term = await self.memory.load_short_term(session_id)
        long_term = await self.memory.load_long_term(user_id) if user_id else {}
        
        # 2. 获取当前上下文
        context = self._build_context(short_term)
        context['user_id'] = user_id
        context['turn_count'] = short_term.get('turn_count', 0) + 1
        
        # 3. 构建系统指令
        system_instructions = self._build_system_instructions(context)
        
        # 4. 构建ACP输入
        acp_input = self.parser.build_input_prompt(
            session_id=session_id,
            user_message=user_message,
            context=context,
            short_term_memory=short_term,
            long_term_memory=long_term,
            system_instructions=system_instructions
        )
        
        # 5. 调用LLM
        model_response = await self.llm.complete(acp_input)
        
        # 6. 解析输出
        output = self.parser.extract_output(model_response)
        
        # 7. 更新记忆
        await self._update_memory(session_id, user_id, output)
        
        # 8. 执行系统动作
        await self._execute_actions(output.get('actions', []))
        
        return {
            'response': output['to_user'],
            'suggestions': output.get('suggestions', [])
        }
    
    def _build_system_instructions(self, context: Dict) -> list:
        """构建系统指令"""
        instructions = [
            "请根据用户输入更新需求信息。",
            "检查必填项是否已完成，如果完成则设置can_enter_matching=true。",
            "提取所有实体信息到extracted字段。",
            "如果用户表达不确定，提供选项参考。"
        ]
        
        # 根据状态添加特定指令
        if context.get('current_state') == 'filling_required':
            instructions.append("每次最多询问一个必填项，避免信息过载。")
        
        return instructions
    
    async def _update_memory(self, session_id: str, user_id: str, output: Dict):
        """更新记忆"""
        # 更新短期记忆
        if 'extracted' in output:
            await self.memory.update_short_term(
                session_id,
                {'extracted_info': output['extracted']}
            )
        
        # 记录对话
        await self.memory.add_conversation_turn(
            session_id,
            output.get('to_user', '')
        )
    
    async def _execute_actions(self, actions: list):
        """执行系统动作"""
        for action in actions:
            if action['action'] == 'update_memory':
                await self.memory.update(
                    action['target'],
                    action['value']
                )
            elif action['action'] == 'log':
                print(f"[ACP LOG] {action['message']}")
```

### 5.2 使用示例

```python
# 使用示例
async def main():
    agent = ACPAgent(llm_client, memory_service)
    
    # 第一轮对话
    response = await agent.process_message(
        session_id="sess_789012",
        user_id="u_123456",
        user_message="我想在墨尔本大学附近租个两室一厅"
    )
    print(f"Agent: {response['response']}")
    
    # 第二轮对话
    response = await agent.process_message(
        session_id="sess_789012",
        user_id="u_123456",
        user_message="预算600左右"
    )
    print(f"Agent: {response['response']}")
    
    # 第三轮对话
    response = await agent.process_message(
        session_id="sess_789012",
        user_id="u_123456",
        user_message="提高到700吧"
    )
    print(f"Agent: {response['response']}")
```

---

## 六、协议优势总结

### 6.1 主要优势

| 特性 | 优势 |
|------|------|
| **结构化输入** | 清晰区分用户输入、系统指令、记忆上下文 |
| **多目标输出** | 同时包含对用户响应、系统状态更新、执行动作 |
| **状态感知** | 包含需求进展、完成度等元信息 |
| **易于解析** | 基于XML风格的标记，易于正则解析 |
| **可扩展** | 可添加新标签、新字段而不破坏兼容性 |
| **调试友好** | 完整的元数据帮助追踪模型行为 |

### 6.2 与项目设计的对应

| 项目组件 | ACP协议支持 |
|----------|------------|
| 需求定义模块 | `<context>`中的pending_fields、completion_ratio |
| 记忆模块 | `<memory>`区块包含短期和长期记忆 |
| 智能体系统 | `<to_system>`中的actions、extracted |
| 用户交互 | `<to_user>`包含响应和suggestions |
| 系统控制 | `<system>`中的instructions、constraints |

这个**AgentComm Protocol (ACP)** 为智能体交互提供了标准化的通信格式，确保了多源信息的有序传递和输出的准确解析，是构建可靠智能体系统的基础设施。