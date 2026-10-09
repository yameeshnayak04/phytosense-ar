# PhytoSense AR – runs on any Docker host (Render, Koyeb, a college server…). Needs < 512 MB RAM.
#   docker build -t phytosense-ar .
#   docker run -p 7860:7860 -e GEMINI_API_KEY=... phytosense-ar
FROM python:3.11-slim
# No apt packages needed: opencv-python-headless and onnxruntime wheels are self-contained.

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /home/user/app

COPY --chown=user backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --user -r backend/requirements.txt

COPY --chown=user backend/app backend/app
COPY --chown=user backend/data backend/data
COPY --chown=user backend/model backend/model
COPY --chown=user frontend frontend

WORKDIR /home/user/app/backend
EXPOSE 7860
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
