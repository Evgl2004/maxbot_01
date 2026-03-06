import re

def extract_phone_from_vcf(vcf: str) -> str | None:
    """
    Извлекает номер телефона из VCF-строки.
    Ищет паттерн TEL;TYPE=cell: и захватывает цифры.
    """
    match = re.search(r'TEL;TYPE=cell:(\d+)', vcf)
    return match.group(1) if match else None
