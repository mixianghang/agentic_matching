import os
from pydantic_settings import BaseSettings
from typing import Dict, Any


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    BASE_URL: str = "https://api.deepseek.com/v1"
    MODEL: str = "deepseek-chat"
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 1000

    STORAGE_TYPE: str = "in_memory"
    DATABASE_URL: str = "./agentic_matching.db"

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "agentic_matching"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


class TaskType:
    DATING = "dating"
    RENTAL = "rental"
    GAMING = "gaming"


TASK_TYPE_NAMES = {
    TaskType.DATING: "相亲",
    TaskType.RENTAL: "租房",
    TaskType.GAMING: "游戏",
}


TASK_TYPE_DESCRIPTIONS = {
    TaskType.DATING: "寻找合适的交友或相亲对象",
    TaskType.RENTAL: "寻找住房或出租房屋",
    TaskType.GAMING: "寻找游戏伙伴或组队",
}


class TaskWorkflow:
    @staticmethod
    def get_system_prompt(task_type: str, username: str) -> str:
        if task_type == TaskType.DATING:
            return f"""
            你是一个专业的相亲交友助手，正在帮助用户 {username} 寻找合适的对象。
            
            你的目标：
            1. 通过对话帮助用户明确交友需求
            2. 了解用户的兴趣爱好和择偶标准
            3. 提供友好的建议和引导
            
            请用友好、自然的中文回复，每次回复2-4句话。
            """
        elif task_type == TaskType.RENTAL:
            return f"""
            你是一个专业的租房助手，正在帮助用户 {username} 寻找合适的住房。
            
            你的目标：
            1. 通过对话了解用户的租房需求（预算、区域、房型等）
            2. 询问是否有特殊要求（宠物、车位等）
            3. 提供实用的建议
            
            请用友好、自然的中文回复，每次回复2-4句话。
            """
        elif task_type == TaskType.GAMING:
            return f"""
            你是一个专业的游戏伙伴助手，正在帮助用户 {username} 寻找一起玩游戏的朋友。
            
            你的目标：
            1. 了解用户玩什么游戏
            2. 了解用户的在线时间和游戏习惯
            3. 帮助用户找到志同道合的游戏伙伴
            
            请用友好、自然的中文回复，每次回复2-4句话。
            """
        else:
            return f"""
            你是一个友好、专业的智能助手，正在帮助用户 {username} 完成需求匹配。
            
            你的目标：
            1. 通过对话帮助用户澄清和完善需求
            2. 用自然、友好的中文回复
            3. 适时提供一些建议
            
            回复要简洁、有帮助，每次回复2-4句话。
            """
