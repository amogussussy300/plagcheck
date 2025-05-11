import time
from concurrent.futures import ThreadPoolExecutor

from requests import RequestException
from requests.adapters import HTTPAdapter
import requests


API_BASE = 'http://localhost:8000/api'
SESSION = requests.Session()
SESSION.mount('http://', HTTPAdapter(
    pool_connections=50,
    pool_maxsize=100,
    max_retries=3
))


def send_archive(file_obj):
    """Send archive to external processing API"""
    try:
        url = f"{API_BASE}/archives/"

        files = {'file': file_obj}
        params = {'process_type': 'copydetect vector'}

        with SESSION.post(url, files=files, params=params, timeout=30) as response:
            response.raise_for_status()
            return response.json()['task_id']

    except KeyError:
        raise RequestException("Missing task_id in API response")
    except RequestException as e:
        raise RequestException(f"API request failed: {str(e)}")


def get_status(task_id):
    """Check processing status with timeout"""
    try:
        status_url = f"{API_BASE}/status/{task_id}"
        with SESSION.get(status_url, timeout=10) as response:
            response.raise_for_status()
            return response.json()
    except RequestException as e:
        return {'status': 'error', 'message': str(e)}