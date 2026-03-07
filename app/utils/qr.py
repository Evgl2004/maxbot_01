import io
import qrcode


async def generate_qr_code(data: str) -> bytes:
    """
    Генерирует QR-код для переданной строки данных.

    Используется для создания QR-кодов бонусных карт. Результат возвращается в виде
    байтового представления PNG-изображения.

    Args:
        data (str): строка, которую нужно закодировать в QR-код (например, номер карты).

    Returns:
        bytes: байтовое содержимое PNG-изображения QR-кода.
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return bio.read()
