FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tải trước các model AI (isnet-general-use và u2net) để tích hợp sẵn vào Image, loại bỏ hoàn toàn việc bị treo do tải model lúc đang chạy
ENV U2NET_HOME=/app/.u2net
RUN mkdir -p /app/.u2net \
    && python -c "import urllib.request; print('Tải model isnet-general-use.onnx...'); urllib.request.urlretrieve('https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx', '/app/.u2net/isnet-general-use.onnx'); print('Tải xong!')" \
    && python -c "import urllib.request; print('Tải model u2net.onnx...'); urllib.request.urlretrieve('https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx', '/app/.u2net/u2net.onnx'); print('Tải xong!')"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
