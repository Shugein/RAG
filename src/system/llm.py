# need test for torch and cuda
# import unsloth
# import torch
# if torch.cuda.is_available():
#     device = torch.device("cuda")
# elif torch.backends.mps.is_available():
#     # Apple Silicon
#     device = torch.device("mps")
# else:
#     device = torch.device("cpu")
# print("using device", device)


import groq
from groq import Groq    
from openai import OpenAI

from dotenv import load_dotenv
import os
import requests
import json

# Загружаем переменные окружения
load_dotenv()
API_KEY = os.environ.get('API_KEY')
MODEL_LLM_ID = "openai/gpt-oss-20b:free"

#==== API model openrouter ====

def generate_llm_response(text, reasoning_level="low"):
    """
    Улучшенная функция генерации ответа LLM с поддержкой Harmony format
    
    Args:
        text (str): Запрос пользователя
        reasoning_level (str): Уровень рассуждений ('low', 'medium', 'high')
    """
    global API_KEY
    
    if not API_KEY:
        return None, "LLM не настроен или API ключ не установлен"

    client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
    )

    completion = client.chat.completions.create(
    #   extra_headers={
    #     "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
    #     "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
    #   },
    extra_body={},
    model="openai/gpt-oss-20b:free",
    max_completion_tokens=1000,
    messages=[
        {
        "role": "user",
        "content": "What is the meaning of life?"
        }
    ]
    )
    return completion.choices[0].message.content

# test
text = 'Оспа обезьян характеризуется более высокой летальностью'
reasoning_l = 'low'
print(generate_llm_response(text, reasoning_l))


## // TODO
#==== local model ====