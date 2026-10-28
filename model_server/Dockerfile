FROM python:3.12-slim AS build

LABEL maintainer="HK Technologies"

ARG NAME=mdt-model-server
ARG HOME_DIR=/usr/src/${NAME}

# Single HuggingFace cache location, shared by the bake step below and the
# runtime container. Without this, weights baked as one user/path would be
# re-downloaded over the network at every container start.
ENV HF_HOME=/opt/hf-cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir -r /requirements.txt

COPY . ${HOME_DIR}

# Bake the model weights into the image layer (${HF_HOME}).
# Deliberately NOT a build cache mount: cache mounts are not committed to image
# layers, so weights downloaded into one would vanish from the final image and
# be re-downloaded over the network at every container start.
ARG EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5
ARG CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RUN python -c "from sentence_transformers import CrossEncoder, SentenceTransformer; \
    SentenceTransformer('${EMBEDDING_MODEL_NAME}', trust_remote_code=True); \
    CrossEncoder('${CROSS_ENCODER_MODEL}')"

FROM python:3.12-slim

ARG NAME=mdt-model-server
ARG PORT=8000
ARG HOME_DIR=/usr/src/${NAME}

# Runtime defaults match the baked weights. Compose passes the same values
# as build args (from .env), so baked weights and runtime config can't diverge.
ARG EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5
ARG CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME} \
    CROSS_ENCODER_MODEL=${CROSS_ENCODER_MODEL} \
    HF_HOME=/opt/hf-cache \
    PORT=${PORT}

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build ${HOME_DIR} ${HOME_DIR}
COPY --from=build /opt/hf-cache /opt/hf-cache

ENV PYTHONPATH="${PYTHONPATH}:${HOME_DIR}"

RUN useradd -ms /bin/bash container_user \
    && chown -R container_user: ${HOME_DIR} /opt/hf-cache
USER container_user

WORKDIR ${HOME_DIR}
EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
