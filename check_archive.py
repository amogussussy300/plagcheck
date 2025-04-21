from zipfile import ZipFile
from rarfile import RarFile
from tarfile import TarFile


def check_archive(arc: ZipFile | RarFile | TarFile) -> bool:
    """
    проверяет, является ли архив архивом яндекс контеста
    :param arc: объект архива
    :return: True/False
    """
    paths = [i for i in arc.namelist()]
    folders = set()
    if len(paths) != 0:
        for path in paths:
            folders.add(path.split("/")[0])
        for d in folders:
            file = False
            for entry in arc.namelist():
                parts = entry.split("/")
                if parts[0] == d and len(parts) > 1:
                    if isinstance(arc, TarFile):
                        member = arc.getmember(entry)
                        if member.isfile():
                            file = True
                            break
                    else:
                        if not entry.endswith("/"):
                            file = True
                            break
            if not file:
                return False
        return True
    return False
