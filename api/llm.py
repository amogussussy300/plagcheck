from ollama import chat
from ollama import ChatResponse


def get_llm_response(message: str, mode="8"):
    """
    запускает локальную языковую модель и создаёт запрос с определённым промптом пользователя
    :param message: сообщение (промпт) для нейросети
    :param mode: 8 или 32, 8 стандартно, отвечает за качество ответа от нейросети, качество пропорционально затратам ресурсов
    :return: возвращает ответ модели
    """
    try:
        response: ChatResponse = chat(model=f"deepseek-r1:{mode}b", messages=[
          {
            "role": "user",
            "content": f"{message}",
          },
        ])

    except Exception as e:
        return f"произошла непредвиденная ошибка при получении ответа от нейросети: {e}"
    return response.message.content
