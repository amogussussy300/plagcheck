from marshmallow import Schema, fields, ValidationError
from flask import current_app

def validate_archive(file):
    """
    фунцкия нужна для проверки соответствия формата архива
    :param file: получает значение fields.Raw из ArchiveUploadSchema
    """
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS')
    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        raise ValidationError("допустимые форматы: '.zip', '.rar'")

class ArchiveUploadSchema(Schema):
    """
    проверяет, передан ли файл, и если передан, то проверяет его расширение при помощи функции выше
    """
    file = fields.Raw(
        required=True,
        type="file",
        validate=validate_archive,
        metadata={"description": "загрузить архив в формате '.zip', '.rar' с кодом "}
    )

class ArchiveResponseSchema(Schema):
    """
    нужен для стандартизации структуры ответов апи; определяет, какие данные будут возвращаться клиенту после отправки архива на обработку
    """
    task_id = fields.String(required=True, description="id для данного task'а")
    status = fields.String(required=True, description="статус обработки")
    message = fields.String(description="пояснение")
    results = fields.Dict(description="результат обработки", required=False)

class ProcessArgsSchema(Schema):
    process_type = fields.String(required=True, description="какой метод обработки использовать")