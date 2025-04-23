#
#
#
#
# этот .py файл не относится к проекту и нужен просто для примера показа работы api


import time
import requests
import json
import pprint


def get_response(process_type: str, path2archive="sample_yandex_contest.zip"):
    response = requests.post("http://localhost:5000/api/archives/", files={"file": open(path2archive, "rb")}, params={"process_type": process_type})
    print(json.loads(response.content))
    return json.loads(response.content)["task_id"]

task_id = get_response("copydetect vector")
print(task_id)

attempts = int(input("введите число попыток получения ответа от api: "))
for i in range(attempts):
    print(f'{i + 1} attempt to respond')
    status_response = requests.get(f"http://localhost:5000/api/status/{task_id}")
    pprint.pprint(json.loads(status_response.content))
    print('---------------\n')
    time.sleep(1.5)