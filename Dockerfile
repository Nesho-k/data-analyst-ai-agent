FROM python:3.13-slim

# Librairies systeme requises par kaleido (rendu Chromium headless utilise
# pour convertir les graphiques Plotly en PNG dans le rapport PDF).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src/ src/

EXPOSE 8501

# Cloud Run fournit le port d'ecoute via la variable PORT (8080 par defaut) :
# le serveur doit s'y adapter dynamiquement plutot que d'utiliser un port fixe.
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
