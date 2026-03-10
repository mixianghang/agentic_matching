"""
需求模板系统 - 定义各类需求的字段结构和收集流程
"""
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum


class FieldType(Enum):
    """字段类型"""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"
    RANGE = "range"
    PRICE = "price"
    DATE = "date"
    LOCATION = "location"
    TAGS = "tags"
    TEXT = "text"


@dataclass
class TemplateField:
    """模板字段定义"""
    name: str
    display_name: str
    field_type: FieldType
    required: bool = True
    prompt: str = ""
    options: Optional[List[str]] = None
    default: Any = None
    memory_mapping: Optional[str] = None  # 用户画像中的路径，如 "preferences.rental.max_price"
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    currency: Optional[str] = None  # 用于价格类型
    period: Optional[str] = None    # 用于价格类型 (weekly/monthly)


@dataclass
class DemandTemplate:
    """需求模板"""
    template_id: str
    demand_type: str
    role: str
    name: str
    fields: List[TemplateField] = field(default_factory=list)
    custom_allowed: bool = True
    custom_prompt: str = "您还有其他特别的要求吗？"


# ==================== 租房模板 ====================

RENTAL_TENANT_TEMPLATE = DemandTemplate(
    template_id="rental_tenant",
    demand_type="rental",
    role="tenant",
    name="租房-租客",
    fields=[
        TemplateField(
            name="property_type",
            display_name="房源类型",
            field_type=FieldType.ENUM,
            required=True,
            prompt="您想租什么类型的房子？",
            options=["apartment", "house", "studio", "room", "any"]
        ),
        TemplateField(
            name="bedrooms",
            display_name="卧室数量",
            field_type=FieldType.INTEGER,
            required=True,
            prompt="您需要几间卧室？",
            min_value=0,
            max_value=10,
            memory_mapping="preferences.rental.bedrooms"
        ),
        TemplateField(
            name="max_price",
            display_name="最高预算",
            field_type=FieldType.PRICE,
            required=True,
            prompt="您的最高预算是多少（每周）？",
            currency="AUD",
            period="weekly",
            memory_mapping="preferences.rental.max_price"
        ),
        TemplateField(
            name="location",
            display_name="位置要求",
            field_type=FieldType.LOCATION,
            required=True,
            prompt="您希望住在哪个区域？可以指定具体地点或区域",
            memory_mapping="user.location"
        ),
        TemplateField(
            name="move_in_date",
            display_name="入住时间",
            field_type=FieldType.DATE,
            required=True,
            prompt="您计划什么时候入住？"
        ),
        # 选填字段
        TemplateField(
            name="min_price",
            display_name="最低预算",
            field_type=FieldType.PRICE,
            required=False,
            prompt="您的最低预算是多少？",
            currency="AUD",
            period="weekly"
        ),
        TemplateField(
            name="furnished",
            display_name="家具要求",
            field_type=FieldType.ENUM,
            required=False,
            prompt="您需要带家具的房子吗？",
            options=["furnished", "unfurnished", "partial", "any"],
            memory_mapping="preferences.rental.furnished"
        ),
        TemplateField(
            name="parking",
            display_name="停车位",
            field_type=FieldType.BOOLEAN,
            required=False,
            prompt="您需要停车位吗？"
        ),
        TemplateField(
            name="pets_allowed",
            display_name="宠物政策",
            field_type=FieldType.BOOLEAN,
            required=False,
            prompt="您需要允许养宠物的房子吗？",
            memory_mapping="preferences.rental.pets_allowed"
        ),
        TemplateField(
            name="lease_term",
            display_name="租期",
            field_type=FieldType.ENUM,
            required=False,
            prompt="您希望的租期是？",
            options=["3_months", "6_months", "12_months", "flexible"]
        ),
        TemplateField(
            name="amenities",
            display_name="设施要求",
            field_type=FieldType.TAGS,
            required=False,
            prompt="您希望有哪些设施？",
            options=["gym", "pool", "elevator", "aircon", "balcony", "yard"],
            memory_mapping="preferences.rental.amenities"
        ),
    ],
    custom_allowed=True,
    custom_prompt="您还有其他特别的要求吗？比如必须朝北有阳台、需要落地窗等"
)

RENTAL_LANDLORD_TEMPLATE = DemandTemplate(
    template_id="rental_landlord",
    demand_type="rental",
    role="landlord",
    name="租房-房东",
    fields=[
        TemplateField(
            name="property_type",
            display_name="房源类型",
            field_type=FieldType.ENUM,
            required=True,
            prompt="您要出租什么类型的房子？",
            options=["apartment", "house", "studio", "room"]
        ),
        TemplateField(
            name="bedrooms",
            display_name="卧室数量",
            field_type=FieldType.INTEGER,
            required=True,
            prompt="房源有几间卧室？",
            min_value=0,
            max_value=10
        ),
        TemplateField(
            name="price",
            display_name="租金",
            field_type=FieldType.PRICE,
            required=True,
            prompt="您希望的租金是多少（每周）？",
            currency="AUD",
            period="weekly"
        ),
        TemplateField(
            name="address",
            display_name="房源地址",
            field_type=FieldType.LOCATION,
            required=True,
            prompt="房源的具体地址是？"
        ),
        TemplateField(
            name="available_from",
            display_name="可入住时间",
            field_type=FieldType.DATE,
            required=True,
            prompt="房源从什么时候可以入住？"
        ),
        # 选填字段
        TemplateField(
            name="price_negotiable",
            display_name="价格可议",
            field_type=FieldType.BOOLEAN,
            required=False,
            prompt="价格可以协商吗？"
        ),
        TemplateField(
            name="furnished",
            display_name="家具情况",
            field_type=FieldType.ENUM,
            required=False,
            prompt="房源带家具吗？",
            options=["furnished", "unfurnished", "partial"]
        ),
        TemplateField(
            name="parking_available",
            display_name="停车位",
            field_type=FieldType.BOOLEAN,
            required=False,
            prompt="有停车位吗？"
        ),
        TemplateField(
            name="pets_allowed",
            display_name="允许宠物",
            field_type=FieldType.BOOLEAN,
            required=False,
            prompt="允许养宠物吗？"
        ),
        TemplateField(
            name="min_lease_term",
            display_name="最短租期",
            field_type=FieldType.ENUM,
            required=False,
            prompt="最短租期是多久？",
            options=["3_months", "6_months", "12_months"]
        ),
        TemplateField(
            name="preferred_tenant",
            display_name="偏好租客",
            field_type=FieldType.TAGS,
            required=False,
            prompt="您偏好哪类租客？",
            options=["student", "family", "professional", "couple"]
        ),
    ],
    custom_allowed=True,
    custom_prompt="您还有其他特别的说明吗？比如对租客的要求、房屋特色等"
)


# ==================== 相亲模板 ====================

DATING_TEMPLATE = DemandTemplate(
    template_id="dating_basic",
    demand_type="dating",
    role="seeker",
    name="婚恋交友",
    fields=[
        TemplateField(
            name="gender_preference",
            display_name="对方性别",
            field_type=FieldType.ENUM,
            required=True,
            prompt="您希望寻找的对方性别是？",
            options=["male", "female", "any"],
            memory_mapping="preferences.dating.gender"
        ),
        TemplateField(
            name="age_range",
            display_name="年龄范围",
            field_type=FieldType.RANGE,
            required=True,
            prompt="您希望对方的年龄范围是？",
            memory_mapping="preferences.dating.age_range"
        ),
        TemplateField(
            name="location",
            display_name="所在地区",
            field_type=FieldType.LOCATION,
            required=True,
            prompt="您希望对方在哪个城市/区域？",
            memory_mapping="user.location"
        ),
        TemplateField(
            name="purpose",
            display_name="交友目的",
            field_type=FieldType.ENUM,
            required=True,
            prompt="您的交友目的是？",
            options=["marriage", "long_term", "short_term", "friendship"],
            memory_mapping="preferences.dating.purpose"
        ),
        # 选填字段
        TemplateField(
            name="education",
            display_name="学历要求",
            field_type=FieldType.ENUM,
            required=False,
            prompt="您对对方的学历有要求吗？",
            options=["high_school", "bachelor", "master", "phd", "any"],
            memory_mapping="preferences.dating.education"
        ),
        TemplateField(
            name="occupation",
            display_name="职业偏好",
            field_type=FieldType.TEXT,
            required=False,
            prompt="您希望对方从事什么职业？",
            memory_mapping="preferences.dating.occupation"
        ),
        TemplateField(
            name="hobbies",
            display_name="兴趣爱好",
            field_type=FieldType.TAGS,
            required=False,
            prompt="您希望对方有哪些共同兴趣爱好？",
            memory_mapping="preferences.dating.hobbies"
        ),
        TemplateField(
            name="has_children",
            display_name="子女情况",
            field_type=FieldType.ENUM,
            required=False,
            prompt="您对对方的子女情况有要求吗？",
            options=["no", "yes_not_living_with", "yes_living_with", "any"]
        ),
        TemplateField(
            name="smoking",
            display_name="吸烟习惯",
            field_type=FieldType.ENUM,
            required=False,
            prompt="您对对方的吸烟习惯有要求吗？",
            options=["no", "occasional", "regular", "any"]
        ),
        TemplateField(
            name="pets",
            display_name="宠物喜好",
            field_type=FieldType.ENUM,
            required=False,
            prompt="您对宠物的态度是？",
            options=["like", "dislike", "allergic", "any"]
        ),
    ],
    custom_allowed=True,
    custom_prompt="除了以上条件，您还有其他特别的要求吗？比如对方必须喜欢宫崎骏动画、会弹钢琴等"
)


# ==================== 模板注册表 ====================

TEMPLATE_REGISTRY: Dict[str, DemandTemplate] = {
    "rental_tenant": RENTAL_TENANT_TEMPLATE,
    "rental_landlord": RENTAL_LANDLORD_TEMPLATE,
    "dating_basic": DATING_TEMPLATE,
}


def get_template(template_id: str) -> Optional[DemandTemplate]:
    """获取模板"""
    return TEMPLATE_REGISTRY.get(template_id)


def get_templates_by_type(demand_type: str) -> List[DemandTemplate]:
    """获取某类型的所有模板"""
    return [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == demand_type]


def get_template_for_role(demand_type: str, role: str) -> Optional[DemandTemplate]:
    """获取特定类型和角色的模板"""
    for template in TEMPLATE_REGISTRY.values():
        if template.demand_type == demand_type and template.role == role:
            return template
    return None


def list_all_templates() -> Dict[str, Dict[str, str]]:
    """列出所有可用模板"""
    return {
        template_id: {
            "name": template.name,
            "type": template.demand_type,
            "role": template.role
        }
        for template_id, template in TEMPLATE_REGISTRY.items()
    }
