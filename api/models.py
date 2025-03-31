from datetime import datetime
from extensions import db

class Task(db.Model):
    """
    модель для хранения значений реквестов пользователей (уникальный id, результат проверки на плагиат загруженного пользователями архива, время создания и статус реквеста)
    """
    id = db.Column(db.String(35), primary_key=True)  # для уникальных id-ков
    status = db.Column(db.String(20), default='processing')
    results = db.Column(db.JSON)  # сохраняет результаты обработок
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"Task(id={self.id}, status={self.status})"