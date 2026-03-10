# 需求定义模块详细设计

## 一、需求定义模块概述

需求定义模块是用户与平台的第一个交互环节，通过大模型驱动的多轮对话，将用户的自然语言表达转化为结构化的需求数据，为后续的智能匹配奠定基础。

### 1.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **对话优先** | 全程通过自然语言对话完成，无需用户学习复杂表单 |
| **渐进式定义** | 需求逐步明确，支持中途修改和迭代 |
| **模板驱动** | 基于需求类型预设模板，确保关键信息不遗漏 |
| **智能填充** | 利用用户画像和历史数据预填已知信息 |
| **灵活扩展** | 支持任意个性化需求元素，不局限于预设字段 |

---

## 二、需求定义流程设计

### 2.1 整体流程

```
用户输入自然语言需求
        ↓
[阶段1：需求类型识别]
   └→ 识别需求大类（租房/相亲/二手交易等）
        ↓
[阶段2：模板加载]
   └→ 根据需求类型和用户角色加载对应模板
        ↓
[阶段3：智能预填充]
   └→ 从用户画像/历史记录中提取已知信息填充模板
        ↓
[阶段4：对话式补全]
   └→ 识别已填字段 → 确定必填缺失项 → 生成追问 → 用户回答 → 更新需求
        ↓
[阶段5：完成判定]
   └→ 判断是否满足进入匹配阶段的条件
        ↓
进入需求匹配阶段 / 继续对话
```

### 2.2 状态流转图

```
[初始状态] → [类型识别中] → [模板加载完成] → [填充中] → [已完成] → [匹配中]
      ↑            ↓              ↓              ↓            ↓
      └────[用户修改类型]───────┘              └──[用户主动完成]─┘
                                                     ↓
                                              [返回补充/确认]
```

---

## 三、需求类型与模板设计

### 3.1 需求类型体系

```json
{
  "demand_types": {
    "dating": {
      "name": "婚恋交友",
      "roles": ["seeker"],  // 只有寻求方
      "templates": ["dating_basic"]
    },
    "rental": {
      "name": "房屋租赁",
      "roles": ["tenant", "landlord"],  // 承租方和出租方
      "templates": {
        "tenant": "rental_tenant",
        "landlord": "rental_landlord"
      }
    },
    "property_trade": {
      "name": "房屋买卖",
      "roles": ["buyer", "seller"],
      "templates": {
        "buyer": "property_buyer",
        "seller": "property_seller"
      }
    },
    "second_hand": {
      "name": "二手交易",
      "roles": ["buyer", "seller"],
      "templates": {
        "buyer": "secondhand_buyer",
        "seller": "secondhand_seller"
      }
    },
    "carpool": {
      "name": "拼车出行",
      "roles": ["driver", "passenger"],
      "templates": {
        "driver": "carpool_driver",
        "passenger": "carpool_passenger"
      }
    },
    "group_activity": {
      "name": "组队娱乐",
      "roles": ["organizer", "participant"],
      "templates": {
        "organizer": "group_organizer",
        "participant": "group_participant"
      }
    },
    "service": {
      "name": "生活服务",
      "roles": ["provider", "customer"],
      "templates": {
        "provider": "service_provider",
        "customer": "service_customer"
      }
    }
  }
}
```

### 3.2 模板定义示例

#### 3.2.1 相亲模板 (dating_basic)

```json
{
  "template_id": "dating_basic",
  "demand_type": "dating",
  "role": "seeker",
  "version": "1.0",
  "fields": {
    "required": [
      {
        "name": "gender_preference",
        "display_name": "对方性别",
        "type": "enum",
        "options": ["male", "female", "any"],
        "prompt": "您希望寻找的对方性别是？",
        "memory_mapping": "preferences.dating.gender"
      },
      {
        "name": "age_range",
        "display_name": "年龄范围",
        "type": "range",
        "min_name": "min_age",
        "max_name": "max_age",
        "prompt": "您希望对方的年龄范围是？",
        "memory_mapping": "preferences.dating.age_range"
      },
      {
        "name": "location",
        "display_name": "所在地区",
        "type": "location",
        "prompt": "您希望对方在哪个城市/区域？",
        "memory_mapping": "user.location"
      },
      {
        "name": "purpose",
        "display_name": "交友目的",
        "type": "enum",
        "options": ["marriage", "long_term", "short_term", "friendship"],
        "prompt": "您的交友目的是？",
        "memory_mapping": "preferences.dating.purpose"
      }
    ],
    "optional": [
      {
        "name": "education",
        "display_name": "学历要求",
        "type": "enum",
        "options": ["high_school", "bachelor", "master", "phd", "any"],
        "prompt": "您对对方的学历有要求吗？",
        "memory_mapping": "preferences.dating.education"
      },
      {
        "name": "occupation",
        "display_name": "职业偏好",
        "type": "text",
        "prompt": "您希望对方从事什么职业？",
        "memory_mapping": "preferences.dating.occupation"
      },
      {
        "name": "hobbies",
        "display_name": "兴趣爱好",
        "type": "tags",
        "prompt": "您希望对方有哪些共同兴趣爱好？",
        "memory_mapping": "preferences.dating.hobbies"
      },
      {
        "name": "has_children",
        "display_name": "子女情况",
        "type": "enum",
        "options": ["no", "yes_not_living_with", "yes_living_with", "any"],
        "prompt": "您对对方的子女情况有要求吗？"
      },
      {
        "name": "smoking",
        "display_name": "吸烟习惯",
        "type": "enum",
        "options": ["no", "occasional", "regular", "any"],
        "prompt": "您对对方的吸烟习惯有要求吗？"
      },
      {
        "name": "pets",
        "display_name": "宠物喜好",
        "type": "enum",
        "options": ["like", "dislike", "allergic", "any"],
        "prompt": "您对宠物的态度是？"
      }
    ],
    "custom_allowed": true,
    "custom_prompt": "除了以上条件，您还有其他特别的要求吗？比如对方必须喜欢宫崎骏动画、会弹钢琴等"
  }
}
```

#### 3.2.2 租房承租方模板 (rental_tenant)

```json
{
  "template_id": "rental_tenant",
  "demand_type": "rental",
  "role": "tenant",
  "version": "1.0",
  "fields": {
    "required": [
      {
        "name": "property_type",
        "display_name": "房源类型",
        "type": "enum",
        "options": ["apartment", "house", "studio", "room", "any"],
        "prompt": "您想租什么类型的房子？",
        "memory_mapping": "preferences.rental.property_type"
      },
      {
        "name": "bedrooms",
        "display_name": "卧室数量",
        "type": "integer",
        "prompt": "您需要几间卧室？",
        "memory_mapping": "preferences.rental.bedrooms"
      },
      {
        "name": "max_price",
        "display_name": "最高预算",
        "type": "price",
        "currency": "AUD",
        "period": "weekly",
        "prompt": "您的最高预算是多少（每周）？",
        "memory_mapping": "preferences.rental.max_price"
      },
      {
        "name": "location",
        "display_name": "位置要求",
        "type": "location_with_radius",
        "prompt": "您希望住在哪个区域？可以指定具体地点或区域",
        "memory_mapping": "user.location"
      },
      {
        "name": "move_in_date",
        "display_name": "入住时间",
        "type": "date",
        "prompt": "您计划什么时候入住？"
      }
    ],
    "optional": [
      {
        "name": "min_price",
        "display_name": "最低预算",
        "type": "price",
        "currency": "AUD",
        "period": "weekly",
        "prompt": "您的最低预算是多少？"
      },
      {
        "name": "furnished",
        "display_name": "家具要求",
        "type": "enum",
        "options": ["furnished", "unfurnished", "partial", "any"],
        "prompt": "您需要带家具的房子吗？"
      },
      {
        "name": "parking",
        "display_name": "停车位",
        "type": "boolean",
        "prompt": "您需要停车位吗？"
      },
      {
        "name": "pets_allowed",
        "display_name": "宠物政策",
        "type": "boolean",
        "prompt": "您需要允许养宠物的房子吗？"
      },
      {
        "name": "lease_term",
        "display_name": "租期",
        "type": "enum",
        "options": ["3_months", "6_months", "12_months", "flexible"],
        "prompt": "您希望的租期是？"
      },
      {
        "name": "amenities",
        "display_name": "设施要求",
        "type": "tags",
        "options": ["gym", "pool", "elevator", "aircon", "balcony", "yard"],
        "prompt": "您希望有哪些设施？"
      }
    ],
    "custom_allowed": true,
    "custom_prompt": "您还有其他特别的要求吗？比如必须朝北有阳台、需要落地窗等"
  }
}
```

#### 3.2.3 租房出租方模板 (rental_landlord)

```json
{
  "template_id": "rental_landlord",
  "demand_type": "rental",
  "role": "landlord",
  "version": "1.0",
  "fields": {
    "required": [
      {
        "name": "property_type",
        "display_name": "房源类型",
        "type": "enum",
        "options": ["apartment", "house", "studio", "room"],
        "prompt": "您要出租什么类型的房子？"
      },
      {
        "name": "bedrooms",
        "display_name": "卧室数量",
        "type": "integer",
        "prompt": "房源有几间卧室？"
      },
      {
        "name": "price",
        "display_name": "租金",
        "type": "price",
        "currency": "AUD",
        "period": "weekly",
        "prompt": "您希望的租金是多少（每周）？"
      },
      {
        "name": "address",
        "display_name": "房源地址",
        "type": "address",
        "prompt": "房源的具体地址是？"
      },
      {
        "name": "available_from",
        "display_name": "可入住时间",
        "type": "date",
        "prompt": "房源从什么时候可以入住？"
      }
    ],
    "optional": [
      {
        "name": "price_negotiable",
        "display_name": "价格可议",
        "type": "boolean",
        "prompt": "价格可以协商吗？"
      },
      {
        "name": "furnished",
        "display_name": "家具情况",
        "type": "enum",
        "options": ["furnished", "unfurnished", "partial"],
        "prompt": "房源带家具吗？"
      },
      {
        "name": "parking_available",
        "display_name": "停车位",
        "type": "boolean",
        "prompt": "有停车位吗？"
      },
      {
        "name": "pets_allowed",
        "display_name": "允许宠物",
        "type": "boolean",
        "prompt": "允许养宠物吗？"
      },
      {
        "name": "min_lease_term",
        "display_name": "最短租期",
        "type": "enum",
        "options": ["3_months", "6_months", "12_months"],
        "prompt": "最短租期是多久？"
      },
      {
        "name": "preferred_tenant",
        "display_name": "偏好租客",
        "type": "tags",
        "options": ["student", "family", "professional", "couple"],
        "prompt": "您偏好哪类租客？"
      }
    ],
    "custom_allowed": true
  }
}
```

---

## 四、智能填充机制设计

### 4.1 记忆数据结构

#### 4.1.1 用户画像 (长期记忆)

```json
{
  "user_id": "u_123456",
  "basic_info": {
    "name": "张三",
    "gender": "male",
    "age": 28,
    "location": "墨尔本",
    "occupation": "软件工程师",
    "education": "master"
  },
  "preferences": {
    "dating": {
      "gender": "female",
      "age_range": {"min": 25, "max": 32},
      "purpose": "long_term",
      "education": "bachelor",
      "hobbies": ["movie", "travel", "anime"]
    },
    "rental": {
      "property_type": "apartment",
      "max_price": 600,
      "bedrooms": 2,
      "furnished": true,
      "amenities": ["gym", "balcony"]
    },
    "second_hand": {
      "prefer_meetup": true,
      "max_travel_distance": 10
    }
  },
  "credit_info": {
    "score": 750,
    "verified": ["identity", "income"]
  },
  "behavior_patterns": {
    "response_time": "evening",
    "negotiation_style": "direct",
    "common_phrases": ["价格可以商量吗", "具体位置在哪"]
  }
}
```

#### 4.1.2 短期记忆 (当前对话上下文)

```json
{
  "session_id": "sess_789012",
  "current_demand_id": "d_345678",
  "conversation_history": [
    {
      "role": "user",
      "message": "我想找个女朋友，最好是在墨尔本的",
      "timestamp": "2026-03-10T10:30:00Z",
      "extracted_intent": "dating"
    },
    {
      "role": "assistant",
      "message": "好的，我来帮您寻找合适的伴侣。根据您的历史记录，您之前偏好25-32岁的女性，这次还是一样的年龄范围吗？",
      "timestamp": "2026-03-10T10:30:05Z"
    },
    {
      "role": "user",
      "message": "这次想找28-35的吧",
      "timestamp": "2026-03-10T10:30:20Z"
    }
  ],
  "extracted_info": {
    "gender_preference": "female",
    "age_range": {"min": 28, "max": 35},
    "location": "墨尔本"
  },
  "pending_fields": ["purpose", "education"],
  "mentioned_custom": ["喜欢宫崎骏动画"]
}
```

### 4.2 智能填充逻辑

```python
class IntelligentFiller:
    def __init__(self, user_profile, session_memory):
        self.user_profile = user_profile
        self.session = session_memory
        self.template = None
    
    def prefill_from_memory(self, template):
        """从用户画像和会话历史预填充字段"""
        prefilled = {}
        
        for field in template["fields"]["required"] + template["fields"].get("optional", []):
            # 1. 检查当前会话是否已提取
            if field["name"] in self.session.get("extracted_info", {}):
                prefilled[field["name"]] = self.session["extracted_info"][field["name"]]
                continue
            
            # 2. 检查是否有记忆映射
            if "memory_mapping" in field:
                value = self.get_from_profile(field["memory_mapping"])
                if value is not None:
                    prefilled[field["name"]] = value
                    continue
            
            # 3. 检查是否有默认值
            if "default" in field:
                prefilled[field["name"]] = field["default"]
        
        return prefilled
    
    def get_from_profile(self, memory_path):
        """从用户画像中按路径获取值"""
        parts = memory_path.split(".")
        current = self.user_profile
        for part in parts:
            if part in current:
                current = current[part]
            else:
                return None
        return current
    
    def identify_missing_required(self, template, current_values):
        """识别缺失的必填字段"""
        missing = []
        for field in template["fields"]["required"]:
            if field["name"] not in current_values:
                missing.append(field)
        return missing
    
    def detect_custom_requirements(self, conversation_history):
        """从对话历史中检测自定义需求"""
        custom_requirements = []
        
        # 分析用户消息中的特殊要求
        for msg in conversation_history:
            if msg["role"] == "user":
                # 简单规则：检测"必须""一定要""需要"等关键词后的内容
                # 实际应用中可用NER或小模型识别
                text = msg["message"]
                if "必须" in text or "一定要" in text or "需要" in text:
                    # 提取自定义要求
                    custom_requirements.append({
                        "source": text,
                        "extracted": self.extract_custom_requirement(text)
                    })
        
        return custom_requirements
    
    def extract_custom_requirement(self, text):
        """提取自定义要求（简化版，实际可用LLM）"""
        # 示例：从"必须喜欢宫崎骏动画"提取"喜欢宫崎骏动画"
        for keyword in ["必须", "一定要", "需要"]:
            if keyword in text:
                return text.split(keyword)[-1].strip()
        return text
```

---

## 五、对话流程设计

### 5.1 对话状态机

```python
class DemandDefinitionStateMachine:
    def __init__(self):
        self.states = {
            "initial": InitialState(),
            "identifying_type": TypeIdentificationState(),
            "filling_required": RequiredFillingState(),
            "filling_optional": OptionalFillingState(),
            "custom_requirements": CustomRequirementsState(),
            "confirming": ConfirmingState(),
            "completed": CompletedState(),
            "modifying": ModifyingState()
        }
        self.current_state = "initial"
        self.demand_data = {}
    
    def process_message(self, user_message):
        """处理用户消息，决定下一状态"""
        
        # 1. 检查是否是修改需求类型
        if self.is_type_modification_request(user_message):
            return self.transition_to("identifying_type", {"modify": True})
        
        # 2. 根据当前状态处理
        next_state = self.states[self.current_state].process(
            user_message, self.demand_data
        )
        
        # 3. 判断是否可进入匹配阶段
        if next_state == "completed" and self.can_enter_matching():
            return {"status": "ready_for_matching", "demand": self.demand_data}
        
        return self.transition_to(next_state)
    
    def can_enter_matching(self):
        """判断是否可进入匹配阶段"""
        # 条件：所有必填字段已填
        if not self.demand_data.get("template"):
            return False
        
        required_fields = self.demand_data["template"]["fields"]["required"]
        for field in required_fields:
            if field["name"] not in self.demand_data.get("values", {}):
                return False
        
        return True
```

### 5.2 各状态对话示例

#### 5.2.1 初始状态 → 类型识别

```
用户: 我想在墨尔本找房子

助手: 好的，您是想租房还是买房呢？

用户: 租房

助手: 明白了，您是作为租客找房子，还是有房子要出租？

用户: 我是租客，想找个两室一厅
```

#### 5.2.2 必填项填充

```
助手: 根据您的需求，我需要了解一些基本信息：

您想租什么类型的房子？(公寓/ house/ studio/ 单间)

用户: 公寓

助手: 需要几间卧室呢？

用户: 两间

助手: 您的最高预算是多少（每周）？根据您的职业和收入情况，我建议600-800的范围会比较合适

用户: 700吧

助手: 您希望住在哪个区域？您之前常活动在Caulfield附近，这次也在那边吗？

用户: 对，Caulfield附近，最好离火车站近点
```

#### 5.2.3 自定义需求捕获

```
助手: 您还有其他特别的要求吗？比如朝向、阳台、宠物等

用户: 必须要有北阳台，我喜欢养花

助手: 好的，已记录"必须有北阳台"。还有其他要求吗？

用户: 最好能养猫

助手: 已记录"允许养猫"。我确认一下您的全部需求：
   - 房源类型：公寓
   - 卧室：2间
   - 预算：$700/周
   - 位置：Caulfield附近，近火车站
   - 特殊要求：北阳台、允许养猫

这些信息准确吗？

用户: 对的
```

#### 5.2.4 需求修改

```
用户: 我想改一下预算，提高到800

助手: 好的，已将预算从$700改为$800。还有其他要修改的吗？

用户: 地点扩大到Glen Huntly也可以

助手: 已更新地点范围：Caulfield或Glen Huntly区域，近火车站。还有其他修改吗？

用户: 没有了

助手: 好的，您的租房需求已更新。现在可以开始为您匹配房源了吗？
```

---

## 六、数据库存储设计

### 6.1 整体ER图

```
┌─────────────┐       ┌─────────────┐
│   users     │       │  demands    │
├─────────────┤       ├─────────────┤
│ user_id(PK) │───────│ demand_id(PK)│
│ profile     │       │ user_id(FK) │
│ preferences │       │ type        │
│ credit_info │       │ role        │
│ created_at  │       │ status      │
└─────────────┘       │ template_id │
                      │ created_at  │
                      │ updated_at  │
                      └─────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
     ┌────────▼────────┐          ┌───────▼────────┐
     │demand_fields    │          │demand_custom   │
     ├─────────────────┤          ├────────────────┤
     │ field_id(PK)    │          │ custom_id(PK)  │
     │ demand_id(FK)   │          │ demand_id(FK)  │
     │ field_name      │          │ requirement    │
     │ field_value     │          │ importance     │
     │ value_type      │          │ created_at     │
     └─────────────────┘          └────────────────┘
```

### 6.2 表结构设计

#### 6.2.1 需求主表 (demands)

```sql
CREATE TABLE demands (
    demand_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    type VARCHAR(32) NOT NULL,  -- dating/rental/property_trade/second_hand/carpool/group_activity/service
    role VARCHAR(32) NOT NULL,   -- seeker/tenant/landlord/buyer/seller等
    template_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) DEFAULT 'defining',  -- defining/completed/matching/negotiating/closed
    title VARCHAR(255),  -- 需求标题（由LLM生成）
    description TEXT,    -- 需求描述（由LLM生成）
    
    -- 结构化需求（JSON格式，包含所有字段的完整快照）
    -- 优点：查询快，一次读取；缺点：部分字段查询需要解析JSON
    structured_demand JSONB NOT NULL,
    
    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,  -- 需求过期时间
    
    -- 索引
    INDEX idx_user_id (user_id),
    INDEX idx_type (type),
    INDEX idx_status (status),
    INDEX idx_created (created_at)
);
```

#### 6.2.2 需求字段表 (demand_fields) - 独立存储方案

```sql
CREATE TABLE demand_fields (
    field_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    demand_id VARCHAR(64) NOT NULL,
    field_name VARCHAR(64) NOT NULL,     -- 字段名，如：gender_preference
    field_value TEXT,                     -- 字段值（JSON格式，支持复杂类型）
    value_type VARCHAR(20) NOT NULL,       -- string/number/boolean/range/array/object
    is_required BOOLEAN DEFAULT FALSE,
    is_from_memory BOOLEAN DEFAULT FALSE,  -- 是否从记忆自动填充
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (demand_id) REFERENCES demands(demand_id) ON DELETE CASCADE,
    INDEX idx_demand_id (demand_id),
    INDEX idx_field_name (field_name),
    
    -- 针对常用字段的值索引（可根据需要动态创建）
    -- 例如：CREATE INDEX idx_rental_price ON demand_fields((field_value->>'max_price')) WHERE field_name='max_price';
    UNIQUE KEY uk_demand_field (demand_id, field_name)  -- 每个需求每个字段一条记录
);
```

#### 6.2.3 自定义需求表 (demand_custom) - 存储个性化需求

```sql
CREATE TABLE demand_custom (
    custom_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    demand_id VARCHAR(64) NOT NULL,
    requirement TEXT NOT NULL,            -- 自定义要求原文，如："必须有北阳台"
    importance VARCHAR(20) DEFAULT 'medium',  -- high/medium/low
    is_negotiable BOOLEAN DEFAULT TRUE,   -- 是否可协商
    embedding VECTOR(384),                 -- 向量化表示，用于语义匹配
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (demand_id) REFERENCES demands(demand_id) ON DELETE CASCADE,
    INDEX idx_demand_id (demand_id)
    -- 向量索引：需根据数据库支持，如pgvector的IVFFLAT索引
);
```

#### 6.2.4 需求模板表 (templates)

```sql
CREATE TABLE templates (
    template_id VARCHAR(64) PRIMARY KEY,
    demand_type VARCHAR(32) NOT NULL,
    role VARCHAR(32) NOT NULL,
    version VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- 模板定义（JSON格式，包含字段定义）
    definition JSONB NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_type_role_version (demand_type, role, version),
    INDEX idx_type (demand_type),
    INDEX idx_active (is_active)
);
```

### 6.3 存储方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **JSON单表存储** (structured_demand) | - 一次读取所有需求<br>- 写入简单<br>- 结构灵活 | - 部分字段查询慢<br>- 更新部分字段需重写整个JSON | 快速原型、读多写少、查询条件简单 |
| **字段独立存储** (demand_fields) | - 可单独查询/更新字段<br>- 可对特定字段建索引<br>- 便于统计分析 | - 查询需多次JOIN<br>- 写入操作多 | 需要复杂查询、频繁更新部分字段 |
| **混合存储** | - 兼顾查询灵活性和性能<br>- 常用字段独立，其他存JSON | - 实现复杂<br>- 数据一致性维护成本高 | 生产环境推荐 |

### 6.4 推荐方案：混合存储

```sql
-- 方案：需求主表存储完整JSON + 关键字段冗余列 + 自定义需求独立表

-- 在demands表中添加关键字段的冗余列（用于高频查询）
ALTER TABLE demands ADD COLUMN
    location_geography GEOGRAPHY(POINT),  -- 地理位置（PostGIS）
    price_min NUMERIC(10,2),
    price_max NUMERIC(10,2),
    date_from DATE,
    date_to DATE;

-- 创建空间索引
CREATE INDEX idx_location ON demands USING GIST (location_geography);

-- 价格范围索引
CREATE INDEX idx_price_range ON demands (price_min, price_max);

-- 示例：查询Caulfield附近、预算$500-800的租房需求
SELECT d.demand_id, d.structured_demand
FROM demands d
WHERE d.type = 'rental'
  AND d.role = 'tenant'
  AND ST_DWithin(
      d.location_geography,
      ST_GeographyFromText('POINT(145.0 -37.88)'),  -- Caulfield坐标
      5000  -- 5公里范围内
  )
  AND d.price_max <= 800
  AND d.price_min >= 500;
```

### 6.5 自定义需求的匹配支持

为了支持"必须喜欢宫崎骏动画"这类个性化需求的匹配，采用向量检索：

```sql
-- 1. 存储时生成向量
INSERT INTO demand_custom (demand_id, requirement, embedding)
VALUES (
    'd_123456',
    '必须喜欢宫崎骏动画',
    embedding_model.encode('喜欢宫崎骏动画')  -- 生成384维向量
);

-- 2. 匹配时进行向量相似度检索
SELECT dc.demand_id, dc.requirement, 
       1 - (dc.embedding <=> ?) AS similarity  -- 余弦相似度
FROM demand_custom dc
JOIN demands d ON dc.demand_id = d.demand_id
WHERE d.type = 'dating'
  AND d.status = 'matching'
  AND dc.importance = 'high'
ORDER BY similarity DESC
LIMIT 10;
```

---

## 七、完成判定机制

### 7.1 判定条件

```python
class CompletionJudger:
    def __init__(self):
        self.completion_criteria = {
            "min_required_ratio": 1.0,  # 必填项必须100%完成
            "min_optional_threshold": 0.3,  # 可选填项完成30%即可
            "max_consecutive_unknowns": 3,  # 最多连续3次用户不知道/不想填
            "min_conversation_turns": 2,  # 最少对话轮次
            "user_explicit_completion": True  # 用户明确表示完成
        }
    
    def should_complete(self, demand_state, conversation_context):
        """判断是否应该结束需求定义，进入匹配阶段"""
        
        # 1. 用户明确要求完成
        if conversation_context.get("user_explicit_complete"):
            return True, "user_requested"
        
        # 2. 所有必填项已完成
        required_fields = demand_state["template"]["fields"]["required"]
        completed_required = [
            f for f in required_fields 
            if f["name"] in demand_state["values"]
        ]
        
        if len(completed_required) < len(required_fields):
            return False, f"missing_required: {len(required_fields) - len(completed_required)}"
        
        # 3. 对话已进行足够轮次
        if conversation_context.get("turn_count", 0) < self.completion_criteria["min_conversation_turns"]:
            return False, "insufficient_conversation"
        
        # 4. 可选填项达到一定比例
        optional_fields = demand_state["template"]["fields"].get("optional", [])
        if optional_fields:
            completed_optional = [
                f for f in optional_fields 
                if f["name"] in demand_state["values"]
            ]
            optional_ratio = len(completed_optional) / len(optional_fields)
            if optional_ratio < self.completion_criteria["min_optional_threshold"]:
                # 但可以询问用户是否愿意继续
                return self.ask_continue_or_complete(demand_state, conversation_context)
        
        # 5. 连续未知回答检测
        if conversation_context.get("consecutive_unknowns", 0) >= self.completion_criteria["max_consecutive_unknowns"]:
            return True, "max_unknowns_reached"
        
        # 6. 默认：可以完成，但询问用户是否继续添加可选信息
        return self.ask_continue_or_complete(demand_state, conversation_context)
    
    def ask_continue_or_complete(self, demand_state, conversation_context):
        """询问用户是继续添加可选信息还是直接完成"""
        # 这里返回一个特殊状态，让对话系统询问用户
        return "pending_user_choice", "ask_continue_or_complete"
```

### 7.2 对话示例：完成判定

```
助手: 我已经记录了您的核心需求：
   - 房源类型：公寓
   - 卧室：2间
   - 预算：$700/周
   - 位置：Caulfield附近

   您还有一些可选信息可以补充，比如：
   - 是否需要有家具？
   - 是否需要停车位？
   - 是否允许宠物？

   您想继续补充这些信息，还是直接开始为您匹配房源？

用户: 直接匹配吧，这些都可以商量

助手: 好的，您的租房需求已设置完成，现在开始为您匹配合适的房源。匹配到合适的房源后我会及时通知您。
```

---

## 八、异常处理与边缘情况

### 8.1 常见异常处理

| 场景 | 处理策略 |
|------|----------|
| 用户需求模糊 | 引导式提问，提供选项参考 |
| 用户多次修改 | 记录修改历史，避免重复提问 |
| 用户放弃定义 | 保存草稿，下次继续 |
| 需求冲突 | 提示用户矛盾点，要求澄清 |
| 超出范围的需求 | 提示不可行，提供替代建议 |

### 8.2 对话示例：模糊需求处理

```
用户: 我想找个条件好的

助手: 为了更好地帮您匹配，能否具体说明一下您指的"条件好"是哪些方面？
比如：
- 经济条件（收入、房产等）
- 外在条件（身高、相貌等）
- 内在条件（学历、性格等）

用户: 主要是要有稳定工作，最好有房

助手: 明白了，您看重对方的经济稳定性。
```

---

## 九、技术实现要点

### 9.1 LLM提示词设计

```python
demand_definition_prompt = """
你是一个智能需求定义助手，负责通过对话帮助用户明确他们的需求。

当前用户信息：
{user_profile}

当前对话历史：
{conversation_history}

当前需求模板：
{template}

已提取的需求信息：
{extracted_info}

你的任务：
1. 理解用户的上一条消息，提取新的需求信息
2. 判断哪些必填项还未完成
3. 生成合适的追问，引导用户补充信息
4. 检测用户是否想修