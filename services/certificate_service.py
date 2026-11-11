import io
import os
import time
import qrcode
from PIL import Image, ImageDraw, ImageFont


def _get_font(font_names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Mavjud shriftdan mosini tanlash yoki standart shrift qaytarish."""
    search_dirs = [
        "/usr/share/fonts/TTF",
        "/usr/share/fonts/noto",
        "/usr/share/fonts/truetype",
        "/usr/share/fonts",
    ]
    for name in font_names:
        for d in search_dirs:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def generate_certificate(
    user_name: str,
    quiz_title: str,
    correct: int,
    total: int,
    percentage: int,
    cert_id: str | None = None,
    bot_username: str = "quiz_tuzdimbot",
) -> bytes:
    """
    O'quvchi uchun yuqori sifatli (1600x1130) professional sertifikat tasviri (PNG baytlar).
    """
    width = 1600
    height = 1130
    cert_id = cert_id or f"QTZ-{int(time.time()) % 1000000:06d}"
    today_str = time.strftime("%d.%m.%Y")

    # Fon rangi: boy to'q ko'k gradient / elegant oq-krem
    # Oltin va to'q ko'k uslubdagi premium diplom
    bg_color = (252, 253, 255)  # Yumshoq oppoq
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Tashqi ramkalar (Oltin va to'q ko'k)
    gold = (212, 175, 55)
    deep_blue = (20, 35, 60)
    light_blue = (235, 242, 250)
    dark_gray = (70, 75, 85)

    # Tashqi hoshiya
    draw.rectangle([30, 30, width - 30, height - 30], outline=gold, width=6)
    draw.rectangle([45, 45, width - 45, height - 45], outline=deep_blue, width=3)
    draw.rectangle([55, 55, width - 55, height - 55], outline=gold, width=1)

    # Burchak bezaklari
    corner_size = 50
    for cx, cy in [(45, 45), (width - 45, 45), (45, height - 45), (width - 45, height - 45)]:
        draw.rectangle([cx - 8, cy - 8, cx + 8, cy + 8], fill=gold)

    # Shriftlar
    font_bold_names = ["DejaVuSerif-Bold.ttf", "DejaVuSans-Bold.ttf", "NotoSans-Bold.ttf"]
    font_regular_names = ["DejaVuSerif.ttf", "DejaVuSans.ttf", "NotoSans-Regular.ttf"]

    f_title = _get_font(font_bold_names, 58)
    f_sub = _get_font(font_regular_names, 24)
    f_presents = _get_font(font_regular_names, 22)
    f_name = _get_font(font_bold_names, 52)
    f_body = _get_font(font_regular_names, 24)
    f_score = _get_font(font_bold_names, 34)
    f_footer = _get_font(font_regular_names, 18)
    f_stamp = _get_font(font_bold_names, 16)

    # Yuqori sarlavha: "CERTIFICATE OF ACHIEVEMENT"
    title_text = "SERTIFIKAT"
    draw.text((width // 2, 130), title_text, fill=deep_blue, font=f_title, anchor="mm")

    sub_text = "CERTIFICATE OF ACHIEVEMENT & EXCELLENCE"
    draw.text((width // 2, 185), sub_text, fill=gold, font=f_sub, anchor="mm")

    # Oltin chiziq
    draw.line([width // 2 - 250, 215, width // 2 + 250, 215], fill=gold, width=3)

    # "Ushbu sertifikat tasdiqlaydiki:"
    presents_text = "Ushbu sertifikat muvaffaqiyat bilan taqdirlanadi:"
    draw.text((width // 2, 280), presents_text, fill=dark_gray, font=f_presents, anchor="mm")

    # O'quvchi ismi
    display_name = (user_name or "Foydalanuvchi")[:35]
    draw.text((width // 2, 360), display_name, fill=deep_blue, font=f_name, anchor="mm")
    name_bbox = draw.textbbox((width // 2, 360), display_name, font=f_name, anchor="mm")
    draw.line([name_bbox[0] - 30, name_bbox[3] + 8, name_bbox[2] + 30, name_bbox[3] + 8], fill=gold, width=2)

    # Test mavzusi
    clean_topic = quiz_title[:45]
    body_text_1 = f"Sun'iy intellekt asosidagi «{clean_topic}» bo'yicha"
    body_text_2 = "viktorina testini a'lo natijalar bilan topshirganligi uchun."
    draw.text((width // 2, 450), body_text_1, fill=deep_blue, font=f_body, anchor="mm")
    draw.text((width // 2, 490), body_text_2, fill=dark_gray, font=f_body, anchor="mm")

    # Natija kartochkasi (badge)
    badge_w, badge_h = 560, 110
    badge_x1 = width // 2 - badge_w // 2
    badge_y1 = 550
    draw.rounded_rectangle(
        [badge_x1, badge_y1, badge_x1 + badge_w, badge_y1 + badge_h],
        radius=16,
        fill=light_blue,
        outline=gold,
        width=2,
    )
    score_text = f"NATIJA: {correct} / {total}  ({percentage}%)"
    draw.text((width // 2, badge_y1 + 40), score_text, fill=deep_blue, font=f_score, anchor="mm")
    grade_text = "🏆 A'lo daraja / Mastered" if percentage >= 85 else "🎖 Yaxshi natija / Certified"
    draw.text((width // 2, badge_y1 + 80), grade_text, fill=gold, font=f_sub, anchor="mm")

    # Pastki qism: QR Kod, Muhr va Sana
    # 1. QR Kod (Botga havola)
    qr = qrcode.QRCode(box_size=3, border=2)
    qr.add_data(f"https://t.me/{bot_username}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=deep_blue, back_color="white").convert("RGB")
    qr_w, qr_h = qr_img.size
    img.paste(qr_img, (140, height - 250, 140 + qr_w, height - 250 + qr_h))
    draw.text((140 + qr_w // 2, height - 125), f"@{bot_username}", fill=dark_gray, font=f_footer, anchor="mm")

    # 2. Markaz: Muhr (Official Stamp)
    stamp_cx, stamp_cy = width // 2, height - 210
    stamp_r = 70
    draw.ellipse([stamp_cx - stamp_r, stamp_cy - stamp_r, stamp_cx + stamp_r, stamp_cy + stamp_r], outline=gold, width=3)
    draw.ellipse([stamp_cx - stamp_r + 6, stamp_cy - stamp_r + 6, stamp_cx + stamp_r - 6, stamp_cy + stamp_r - 6], outline=gold, width=1)
    draw.text((stamp_cx, stamp_cy - 20), "★ VERIFIED ★", fill=gold, font=f_stamp, anchor="mm")
    draw.text((stamp_cx, stamp_cy + 5), "QUIZ TUZDIM", fill=deep_blue, font=f_stamp, anchor="mm")
    draw.text((stamp_cx, stamp_cy + 25), "AI CERTIFIED", fill=gold, font=f_stamp, anchor="mm")

    # 3. O'ng tomon: Sana va Sertifikat ID
    draw.text((width - 240, height - 230), f"Sana: {today_str}", fill=deep_blue, font=f_footer, anchor="mm")
    draw.text((width - 240, height - 195), f"ID: {cert_id}", fill=dark_gray, font=f_footer, anchor="mm")
    draw.line([width - 340, height - 165, width - 140, height - 165], fill=gold, width=2)
    draw.text((width - 240, height - 140), "Metodist imzosi", fill=dark_gray, font=f_footer, anchor="mm")

    # PNG baytlarga o'tkazish
    output = io.BytesIO()
    img.save(output, format="PNG", quality=95)
    return output.getvalue()
