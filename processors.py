import os
import re
import zipfile
import tarfile
from abc import ABC, abstractmethod
from collections import defaultdict
from tempfile import TemporaryDirectory
from typing import Any
from pathlib import Path
import copydetect
import rarfile
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from itertools import combinations
import matplotlib
matplotlib.use('Agg') # нужен чтобы избавиться от warning


class BaseArchiveProcessor(ABC):
    """
    класс базового процессора, от которого будут наследоваться другие
    """
    @staticmethod
    def _read_file(file: str, strip=True, encoding="utf-8") -> str:
        """
        нужна для чтения и обработки получаемых файлов с кодом
        :param file: путь до файла с кодом
        :param strip: определяет, будут ли форматироваться получаемые файлы
        :return: возвращает код файла строкой
        """
        with open(file, encoding=encoding) as f:
            text = f.read()
            text = re.sub(r'#.*', '', text, flags=re.MULTILINE)
            text = re.sub(r'[ \t]+', ' ', text)
            lines = text.split('\n')
            if strip:
                lines = [line.strip() for line in lines]
            return '\n'.join(lines)

    @staticmethod
    def _common_extraction(archive_path: str, extract_dir: str) -> dict:
        """
        :param archive_path: указывается путь до архива с файлами с кодом (поддерживаемые форматы архива: .zip, .rar, .tar.gz, .tgz)
        :param extract_dir: указывается путь до папки, куда распаковывается содержимое архива (путь будет заполняться автоматом до папки, создаваемой в %temp%)
        метод распаковывает архив по решениям определённых задач и распределяет по расширениям решения

        данные решений:
        {'A': {'cpp': ['C:\\...\\A_solutions\\cpp_solutions\\A-Unknown_idas-OK.cpp', ... ]}}

        :return метод возвращает словарь с данными решений
        """

        def _extract(arc: zipfile.ZipFile | tarfile.TarFile | rarfile.RarFile):
            for file_info in archive.infolist():
                if "-OK" not in file_info.filename:
                    continue

                parts = file_info.filename.split('/')
                if len(parts) != 2:
                    continue

                dir_part, file_part = parts

                student_name = dir_part.split('-', 1)[0]
                name_parts = student_name.split()
                surname = name_parts[0] if len(name_parts) >= 1 else "Unknown"
                name = name_parts[1] if len(name_parts) >= 2 else "Unknown"

                letter = file_part[0]
                file_path = Path(file_part)

                extension = file_path.suffix
                if not extension:
                    extension = '.txt'
                    extension_clean = 'txt'
                else:
                    extension_clean = extension.lstrip('.')

                new_filename = f"{letter}-{name}_{surname}-OK{extension}"

                target_dir = os.path.join(
                    extract_dir,
                    f"{letter}_solutions",
                    f"{extension_clean}_solutions"
                )
                os.makedirs(target_dir, exist_ok=True)

                target_path = os.path.join(target_dir, new_filename)
                with archive.open(file_info) as source, open(target_path, 'wb') as target:
                    target.write(source.read())

            target.close()

        archive_path = Path(archive_path)
        suffix = archive_path.suffix.lower()
        main_suffix = "".join(archive_path.suffixes[-2:]).lower()

        try:
            if suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as archive:
                    _extract(archive)
            elif suffix == ".rar":
                with rarfile.RarFile(archive_path, "r") as archive:
                    _extract(archive)
            elif main_suffix == ".tar.gz" or main_suffix == ".tgz":
                with tarfile.TarFile(archive_path, "r") as archive:
                    _extract(archive)
            else:
                raise ValueError(f"формат {suffix} архива не поддерживается")
        except (zipfile.BadZipFile, rarfile.BadRarFile) as e:
            raise ValueError(f"неверный архив (повреждённый): {str(e)}")

        solutions = {}
        extract_path = Path(extract_dir)

        for letter_dir in extract_path.iterdir():
            if letter_dir.is_dir() and letter_dir.name.endswith('_solutions'):
                letter = letter_dir.name[0].upper()
                extensions_dict = defaultdict(list)

                for file_path in letter_dir.rglob('*'):
                    if file_path.is_file():
                        extension = file_path.suffix[1:] if file_path.suffix else 'none'
                        extensions_dict[extension].append(str(file_path.resolve()))

                solutions[letter] = dict(extensions_dict)

        return solutions

    @classmethod
    def process_archive(cls, archive_path: str) -> Any:
        """
        :param archive_path: указывается путь до архива
        :return: возвращает результат анализа на плагиат (поскольку это базовый класс, то в данном случае ничего не будет возвращаться, см. наследников)
        """
        with TemporaryDirectory() as extract_dir:
            try:
                data = cls._common_extraction(archive_path, extract_dir)
            except (zipfile.BadZipFile, rarfile.BadRarFile) as e:
                raise ValueError(f"неверный архив (повреждённый): {str(e)}")

            return cls.analyze_files(data)

    @staticmethod
    @abstractmethod
    def analyze_files(data: dict) -> Any:
        """метод будет определён в наследующихся процессорах"""
        pass


class CopydetectProcessor(BaseArchiveProcessor):
    """
    процессор, использующий библиотеку copydetect.
    токенизирует код файла, сравнивает уникальные пары токенизированных кодов и имен их файлов, возвращает значения совпадения токенов, похожесть, а также предпологаемые части сплагиаченного кода (отмечены SUS_FROM_HERE--> <--TO_HERE)
    """
    @staticmethod
    def analyze_files(data: dict) -> dict:
        """
        :param data: указывается словарь с данными о решениях учеников (заполняется автоматом, см. BaseArchiveProcessor)
        :return возвращает словарь как результат обработки copydetect'а, где ключи - разделённые имена файлов, а значения - значения совпадения токенов, похожесть, а также сами коды с отмеченными частями предположительно сплагиаченного кода
        """
        report = {}

        for letter in data:
            for extension in data[letter]:
                fingerprints = [(Path(file).name, copydetect.CodeFingerprint(file, 25, 1)) for file in data[letter][extension]]
                for (name1, fp1), (name2, fp2) in combinations(fingerprints, 2):
                    token_overlap, similarities, slices = copydetect.compare_files(fp1, fp2)
                    code1, _ = copydetect.utils.highlight_overlap(fp1.raw_code, slices[0], "~~SFH~~", "~~SFH~~")
                    code2, _ = copydetect.utils.highlight_overlap(fp2.raw_code, slices[1], "~~SFH~~", "~~SFH~~")
                    report[f"{letter}___{name1}___{name2}"] = (token_overlap, similarities, (code1, code2))
        if not report:
            raise ValueError(f"возникла неожиданная ошибка: {report}")
        return report


class VectorProcessor(BaseArchiveProcessor):
    """
    процессор, использующий TF-IDF векторизацию для определения насколько один файл с кодом совпадает с другим.
    кратко, этот процессор рассчитывает TF-IDF векторы для каждого файла с кодом и сравнивает их направленность
    (косинусное сходство).
    если файлы идентичны, то векторы также направлены одинаково, а значит функция
    cosine_similarity вернёт 1 (см. static method _find_plagiarism).
    если файлы совершенно не схожи, то cosine_similarity вернёт 0.
    """

    @staticmethod
    def analyze_files(data: dict) -> dict:
        """
        :param data: указывается словарь с данными о решениях учеников (заполняется автоматом, см. BaseArchiveProcessor)
        :return: возвращает множество кортежей со значениями "похожести" пар указанных файлов
        """
        result = {}
        for letter, extensions in data.items():
            for ext, files in extensions.items():
                filenames = [Path(fp).name for fp in files]
                docs = [VectorProcessor._read_file(fp) for fp in files]

                if not docs:
                    continue

                tfidf_matrix = TfidfVectorizer().fit_transform(docs).toarray()

                doc_pairs = list(zip(filenames, tfidf_matrix))

                result[f"{letter}___{ext}"] = VectorProcessor._find_plagiarism(doc_pairs)

        return result


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
