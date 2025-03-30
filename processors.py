import re
import zipfile
from abc import ABC, abstractmethod
from tempfile import TemporaryDirectory
from typing import Any
from pathlib import Path
import copydetect
import rarfile
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from itertools import combinations
from llm import get_llm_response
import matplotlib
matplotlib.use('Agg') # нужен чтобы избавиться от warning


class BaseArchiveProcessor(ABC):
    """
    класс базового процессора, от которого будут наследоваться другие
    """
    @staticmethod
    def _read_file(file: str, strip=True) -> str:
        """
        нужна для чтения и обработки получаемых файлов с кодом
        :param file: путь до файла с кодом
        :param strip: определяет, будут ли форматироваться получаемые файлы
        :return: возвращает код файла строкой
        """
        with open(file) as f:
            text = f.read()
            text = re.sub(r'#.*', '', text, flags=re.MULTILINE)
            text = re.sub(r'[ \t]+', ' ', text)
            lines = text.split('\n')
            if strip:
                lines = [line.strip() for line in lines]
            return '\n'.join(lines)

    @staticmethod
    def _common_extraction(archive_path: str, extract_dir: str) -> None:
        """
        :param archive_path: указывается путь до архива с файлами с кодом (поддерживаемые форматы архива: .zip и .rar)
        :param extract_dir: указывается путь до папки, куда распаковывается содержимое архива (путь будет заполняться автоматом до папки, создаваемой в %temp%)
        метод распаковывает архив в определённой папке (см. метод класса process_archive)
        """

        archive_path = Path(archive_path)
        suffix = archive_path.suffix.lower()

        try:
            if suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as archive:
                    archive.extractall(extract_dir)
            elif suffix == ".rar":
                with rarfile.RarFile(archive_path, "r") as archive:
                    archive.extractall(extract_dir)
            else:
                raise ValueError(f"формат {suffix} архива не поддерживается")
        except (zipfile.BadZipFile, rarfile.BadRarFile) as e:
            raise ValueError(f"неверный архив (повреждённый): {str(e)}")

    @classmethod
    def process_archive(cls, archive_path: str, extension=".py") -> Any:
        """
        :param archive_path: указывается путь до архива
        :param extension: указывается расширение файлов с кодом в архиве, дефолтно .py
        :return: возвращает результат анализа на плагиат (поскольку это базовый класс, то в данном случае ничего не будет возвращаться, см. наследников)
        """
        with TemporaryDirectory() as extract_dir:
            try:
                cls._common_extraction(archive_path, extract_dir)
            except (zipfile.BadZipFile, rarfile.BadRarFile) as e:
                raise ValueError(f"неверный архив (повреждённый): {str(e)}")

            return cls._analyze_files(extract_dir, extension)

    @staticmethod
    @abstractmethod
    def _analyze_files(extract_dir: str, extension: str) -> None:
        """метод будет определён в наследующихся процессорах"""
        pass


class CopydetectProcessor(BaseArchiveProcessor):
    """
    процессор, использующий библиотеку copydetect.
    токенизирует код файла, сравнивает уникальные пары токенизированных кодов и имен их файлов, возвращает значения совпадения токенов, похожесть, а также предпологаемые части сплагиаченного кода (отмечены SUS_FROM_HERE--> <--TO_HERE)
    """
    @staticmethod
    def _analyze_files(extract_dir: str, extension: str) -> dict:
        """
        :param extract_dir: указывается папка, куда распаковались файлы с кодом (заполняется автоматом, см. BaseArchiveProcessor)
        :param extension: указывается расширение файлов с кодом (заполняется автоматом, см. BaseArchiveProcessor)
        :return возвращает словарь как результат обработки copydetect'а, где ключи - разделённые имена файлов, а значения - значения совпадения токенов, похожесть, а также сами коды с отмеченными частями предположительно сплагиаченного кода
        """

        report = {}

        files = [
            f for f in Path(extract_dir).iterdir()
            if f.suffix == (extension if extension.startswith('.') else f'.{extension}')
        ]

        if not files:
            raise ValueError(f"файлов с данным расширением {extension} в папке {extract_dir} не было найдено")
        elif len(files) < 2:
            raise ValueError(f"был найден только один файл с расширением {extension} в папке {extract_dir}")

        fingerprints = [(file.name, copydetect.CodeFingerprint(file, 25, 1)) for file in files]
        for (name1, fp1), (name2, fp2) in combinations(fingerprints, 2):
            token_overlap, similarities, slices = copydetect.compare_files(fp1, fp2)
            code1, _ = copydetect.utils.highlight_overlap(fp1.raw_code, slices[0], "SUS_FROM_HERE-->", "<--TO_HERE")
            code2, _ = copydetect.utils.highlight_overlap(fp2.raw_code, slices[1], "SUS_FROM_HERE-->", "<--TO_HERE")
            report[f"{name1}___{name2}"] = (token_overlap, similarities, (code1, code2))
        if not report:
            raise ValueError(f"возникла неожиданная ошибка: {report}")
        return report


class VectorProcessor(BaseArchiveProcessor):
    """
    процессор, использующий TF-IDF векторизацию для определения насколько один файл с кодом совпадает с другим.
    кратко, этот процессор рассчитывает TF-IDF векторы для каждого файла с кодом и сравнивает их направленность
    (косинусное сходство).
    если файлы идентичны, то векторы также направлены одинаково, а значит функция
    cosine_similarity вернёт 1 (см. статический метод _find_plagiarism).
    если файлы совершенно не схожи, то cosine_similarity вернёт 0.
    """

    @staticmethod
    def _analyze_files(extract_dir: str, extension: str) -> set[tuple]:
        """
        :param extract_dir: указывается папка, куда распаковались файлы с кодом (заполняется автоматом, см. BaseArchiveProcessor)
        :param extension: указывается расширение файлов с кодом (заполняется автоматом, см. BaseArchiveProcessor)
        :return: возвращает множество кортежей со значениями "похожести" пар указанных файлов
        """

        files = list(Path(extract_dir).rglob(f"*{extension}"))
        if not files:
            raise ValueError(f"файлов с данным расширением {extension} в папке {extract_dir} не было найдено")

        docs = [VectorProcessor._read_file(file) for file in files]
        transformed_docs = TfidfVectorizer().fit_transform(docs).toarray()
        doc_pairs = list(zip([path.name for path in files], transformed_docs))

        return VectorProcessor._find_plagiarism(doc_pairs)

    @staticmethod
    def _find_plagiarism(pairs: list[tuple]) -> set[tuple]:
        """
        рассчитывает косинусное сходство векторов каждого файла и записывает их во множество
        :param pairs: принимает пары для каждого файла в формате списка, первым элементом является - имя файла, а вторым - векторизованный текст кода файла
        :return: возвращает результаты сравнения в формате множества кортежей, первый элемент которых - имя файла, второй - косинусное сходство
        """
        results = set()

        for (file_a, vec_a), (file_b, vec_b) in combinations(pairs, 2):
            similarity = cosine_similarity([vec_a], [vec_b])[0][0]
            sorted_files = sorted((file_a, file_b))

            results.add((sorted_files[0], sorted_files[1], similarity))

        return results


class LlmProcessor(BaseArchiveProcessor):
    """
    процессор, использующий локально запущенную большую языковую модель deepseek-r1
    """
    @staticmethod
    def _analyze_files(extract_dir: str, extension: str) -> str:
        """
        :param extract_dir: указывается папка, куда распаковались файлы с кодом (заполняется автоматом, см. BaseArchiveProcessor)
        :param extension: указывается расширение файлов с кодом (заполняется автоматом, см. BaseArchiveProcessor)
        :return: возвращает ответ от нейросети
        """
        files = list(Path(extract_dir).rglob(f"*{extension}"))
        if not files:
            raise ValueError(f"файлов с данным расширением {extension} в папке {extract_dir} не было найдено")

        data = [(file.name, VectorProcessor._read_file(file, strip=False)) for file in files]
        prompt = f"""
        Analyze the following Python codes for potential plagiarism. Compare each pair of files and provide:
        A similarity score from 1-10 (10 = highly likely plagiarized)
        A concise reason focusing on variable/function naming, structural patterns, algorithm logic, and unique code overlaps.
        Data:
        {data}
        
        Respond strictly in this format (without any additional clarifications, "final answers" etc.):
        ```
        LLM:  
        1) Files (X.py and Y.py). Similarity score: N/10. Reason: [Concise 1-2-sentence explanation].  
        2) Files (X.py and Y.py). Similarity score: N/10. Reason: [...]  
        3) Files (X.py and Y.py). Similarity score: N/10. Reason: [...]  
        ...
        
        ```
        """
        return (get_llm_response(prompt).split('</think>'))[1]
