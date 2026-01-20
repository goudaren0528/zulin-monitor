FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Set timezone to Shanghai
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port
EXPOSE 3000

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run Flask app
CMD ["python", "app.py"]
