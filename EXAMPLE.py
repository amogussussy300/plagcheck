#
#
#
#
# этот .py файл не относится к проекту и нужен просто для примера показа работы api


import time
import requests
import json
import pprint


def get_response():
    response = requests.post("http://localhost:5000/archives/", files={"file": open("sample.zip", "rb")})
    print(json.loads(response.content)["task_id"])
    return json.loads(response.content)["task_id"]


task_id = get_response()
attempts = int(input("введите число попыток получения ответа от api: "))
for i in range(attempts):
    print(f'{i + 1} attempt to respond')
    status_response = requests.get(f"http://localhost:5000/archives/status/{task_id}")
    pprint.pprint(json.loads(status_response.content), compact=True)
    print('---------------\n')
    time.sleep(3)