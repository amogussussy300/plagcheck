import json
import logging
import tempfile
from flask_smorest import Blueprint, abort
from werkzeug.utils import secure_filename
import os
from application import limiter
from extensions import db
from processors import CopydetectProcessor, VectorProcessor
from flask import current_app
from schemas import ArchiveUploadSchema, ArchiveResponseSchema, ProcessArgsSchema
from concurrent.futures import ThreadPoolExecutor
import uuid
from models import Task


# сетапим логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# нужен, чтобы алгоритм проверки на плагиат выполнялся параллельно с request-response циклом (я бы вообще написал весь проект на fastapi или quart т.к. они не завязаны на синхронности, как фласк)
# имхо фласк в этом плане хуже, т.к. синхронность приводит к следующим ситуациям: если запрос пользователя будет обрабатываться так, что нужно будет обращаться к базам данных и т.п., то весь поток (канал) блокируется (становится в очередь), пока не выполнится это обращение к базе данных (а в моем случае вообще рофл, т.к. один из методов определения на плагиат - это использование большой языоковой модели deepseek, которая очень долго думает и обрабатывает коды). это, в свою очередь, ведёт к неэффективности при большом числе запросов.
# есть способ как сделать эффективнее синхронный подход - это использовать специальные wsg интерфейсы (web service gateway interface) как waitress (что я и использую) или gunicorn (работающий только на linux). что самое главное, эти интерфейсы дают возможность выставляет определённое чилсо worker'ов, что позволяет обойти ограничение фласка в один поток и немного приблизиться к эффективности асинхронного fastapi
executor = ThreadPoolExecutor()

# чертеж, при этом путь выглядит так: доменноеимя:порт/archives/
blp = Blueprint(
    "archive_processor",
    __name__,
    url_prefix="/archives",
    description="проверка архивов с кодом на плагиат"
)

def convert_sets(obj):
    """
    нужна для того, чтобы избавиться от TypeError: Object of type set is not JSON serializable, т.к. некоторые процессоры возвращают множества (превращает множества в списки)
    :param obj: объект для перевода
    :return: переведённый объект
    """
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        return {k: convert_sets(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_sets(x) for x in obj]
    return obj



@blp.route("/", methods=["POST"])  # /archives/
@blp.arguments(ProcessArgsSchema, location="query")  # archives/?process_type=...
@blp.arguments(ArchiveUploadSchema, location="files")  # endpoint принимает аргумент (архив) в формате по схеме в schemas.py
@blp.response(202, ArchiveResponseSchema)  # endpoint возвращает в формате по схеме в schemas.py
@limiter.limit("4 per minute")  # на пятый реквест в пределах минуты вернёт {'code': 429, 'status': 'Too Many Requests'}
def process_archive(query_args, args):
    """
    функция принимает архив, проверяет, валидное ли у него название, имеет ли он верное расширение, потом сохраняет его в папку в %temp% и выполняет на нём process_archive_background, по endpoint'у возвращает начало работы над архивом
    функция также записывает в базу данных task и ставит его на обработку
    :param query_args: какой метод при обработке использовать: copydetect, vector (нужные пишутся через пробел маленькими буквами)
    :param args: сам архив в bytes
    :return: 202 response о том, что началась обработка архива
    """
    process_type: str = query_args["process_type"]

    if 'file' not in args:
        abort(400, message="архив не загружен")

    file = args['file']
    if file.filename == '':
        abort(400, message="пустое имя архива")

    filename = secure_filename(file.filename)
    if not any(filename.lower().endswith(ext) for ext in current_app.config['ALLOWED_EXTENSIONS']):
        abort(400, message="неверный формат архива")

    tempdir = tempfile.mkdtemp()
    filepath = os.path.join(tempdir, filename)
    file.save(filepath)

    task_id = str(uuid.uuid4())
    new_task = Task(id=task_id, status="processing")
    db.session.add(new_task)
    db.session.commit()

    app = current_app._get_current_object()

    # !
    future = executor.submit(
        process_archive_background,
        app,
        filepath,
        task_id,
        process_type
    )

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "обработка архива началась"
    }, 202


def process_archive_background(app, filepath, task_id, methods="copydetect vector"):
    """
    запускает проверку на плагиат для файлов архива и заполняет task в базе данных с нужным id
    :param app: объект текущего instance'а flask'а
    :param filepath: путь до архива
    :param task_id: случайно генерируемый id (см. _process_archive)
    :param methods: позволяет выбрать метод обработки архива
    """
    methods = methods.split()
    if "copydetect" not in methods and "vector" not in methods:
        abort(400, message="вы выбрали неверный метод обработки архива (выбирайте из 'vector copydetect')")
    with app.app_context():
        try:
            db.session.remove()
            results = {
                "copydetect": convert_sets(CopydetectProcessor.process_archive(filepath)) if "copydetect" in methods else None,
                "vector": convert_sets(VectorProcessor.process_archive(filepath)) if "vector" in methods else None
            }

            task = db.session.query(Task).get(task_id)
            task.status = "completed"
            task.results = json.dumps(results, indent=4, default=str)  # str чтобы не было object of type int64 is not json serializable
            db.session.commit()

        except Exception as e:
            current_app.logger.error(f"ошибка обработки: {str(e)}")
            task = Task.query.get(task_id)
            task.status = "failed"
            task.results = json.dumps({"error": str(e)}, indent=4)
            db.session.commit()

        finally:
            try:
                os.remove(filepath)
                os.rmdir(os.path.dirname(filepath))
            except Exception as cleanup_error:
                current_app.logger.error(f"не удалось очистить папки: {cleanup_error}")


@limiter.limit("1 per second")
@blp.route("/status/<string:task_id>", methods=["GET"])  # /archives/status/<task_id>
@blp.response(200, ArchiveResponseSchema)  # endpoint возвращает в формате по схеме в schemas.py
def check_status(task_id):
    """
    функция нужна для получения данных обработки процессорами загруженного архива по созданному ранее id
    :param task_id: полученный ранее id
    :return: словарь с задачей, её id, статусом и данными обработки
    """
    task = Task.query.get(task_id)
    return {
        "task": task,
        "task_id": task.id,
        "status": task.status,
        "results": json.loads(task.results) if task.results else None
    }