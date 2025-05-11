
########################################################################################################################
# app_build
########################################################################################################################

FROM public.ecr.aws/debian/debian:bookworm-20241111-slim AS app_build

ENV DEBIAN_FRONTEND=noninteractive
RUN set -e && \
    apt-get update && \
    apt-get install -y curl g++ python-dev-is-python3 && \
    rm -rf /var/lib/apt/lists/*

# uv のインストール
RUN curl -LsSf https://astral.sh/uv/0.7.2/install.sh | env UV_UNMANAGED_INSTALL="/usr/local/bin" sh

COPY . /app
WORKDIR /app
RUN uv sync


########################################################################################################################
# app
########################################################################################################################
FROM public.ecr.aws/debian/debian:bookworm-20241111-slim AS app

ENV DEBIAN_FRONTEND=noninteractive
RUN set -e && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y tzdata locales && \
    sed -i -E 's/# (ja_JP.UTF-8)/\1/' /etc/locale.gen && \
    locale-gen && \
    update-locale LANG=ja_JP.UTF-8 && \
    apt-get remove -y git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Tokyo \
    LANG=ja_JP.UTF-8 \
    LANGUAGE=ja_JP:ja \
    LC_ALL=ja_JP.UTF-8 \
    UV_NO_SYNC=1

COPY --from=app_build /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/
COPY --from=app_build /root/.local /root/.local
COPY --from=app_build /app /app
WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
