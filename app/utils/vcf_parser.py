import re


def extract_phone_from_vcf(vcf: str) -> str | None:
    """
    Извлекает номер телефона из VCF-строки, полученной при отправке контакта в MAX.

    Ищет паттерн 'TEL;TYPE=cell:' и захватывает следующие за ним цифры.

    Args:
        vcf (str): содержимое поля vcf_info вложения типа contact.

    Returns:
        str | None: номер телефона (только цифры) или None, если не удалось найти.
    """
    match = re.search(r'TEL;TYPE=cell:(\d+)', vcf)
    return match.group(1) if match else None
