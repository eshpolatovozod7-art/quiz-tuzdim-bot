FROM python:3.11-slim

WORKDIR /app

# Tizim kutubxonalari (Ovoz, rasm va PDF qayta ishlash uchun)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python kutubxonalarini o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha kodini nusxalash
COPY . .

# Ma'lumotlar papkasi
RUN mkdir -p data/exports data/uploads

EXPOSE 10000

# Botni ishga tushirish
CMD ["python", "main.py"]
