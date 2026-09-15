FROM python:3.12-slim
WORKDIR /app
COPY ["要求2.txt","requirements.txt"]
RUN pip install --no-cache-dir -r requirements.txt
COPY ["应用程序2.py","app.py"]
COPY ["索引2.html","index.html"]
COPY ["清单2.json","manifest.json"]
EXPOSE 8080
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8080"]
