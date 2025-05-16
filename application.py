from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_smorest import Api
from flask_migrate import Migrate
from extensions import db
from models import Task
import logging


# сетапим логгер
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


# инициализация фласка с конфигом + сваггером
app = Flask(__name__)
app.config.from_mapping(
    API_TITLE="Archive Processing API",
    API_VERSION="v1",
    OPENAPI_VERSION="3.0.3",
    OPENAPI_URL_PREFIX="/",
    OPENAPI_SWAGGER_UI_PATH="/swagger-ui",
    OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
    ALLOWED_EXTENSIONS={"rar", "zip", "tgz", "tar.gz"},
    MAX_CONTENT_LENGTH=100 * 2**20,  # 100 MB
    SQLALCHEMY_DATABASE_URI="sqlite:///tasksdb.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)


# создание объекта ограничителя по использованию api и его инициализация
limiter = Limiter(
    get_remote_address,
    app=app,  # вот тут инициализируется
    default_limits=["1 per 1 second"],
    storage_uri="memory://"
)

# инициализация sqlalchemy + api через smorest + ограничителя
migrate = Migrate(app, db)
api = Api(app)
db.init_app(app)

# загрузка чертежа и его инициализация
from upload import blp as upload_blp
api.register_blueprint(upload_blp)

# инициализация базы данных
with app.app_context():
    db.create_all()

#  запуск
if __name__ == "__main__":
    app.run(debug=True)