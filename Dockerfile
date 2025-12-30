FROM ghcr.io/prefix-dev/pixi:latest AS build

WORKDIR /app

COPY pyproject.toml pixi.lock ./

RUN mkdir -p meme_games && touch meme_games/__init__.py

RUN pixi install --locked

COPY . .

RUN pixi shell-hook -s bash > /shell-hook
RUN echo "#!/bin/bash" > /app/entrypoint.sh
RUN cat /shell-hook >> /app/entrypoint.sh
RUN echo 'exec "$@"' >> /app/entrypoint.sh

FROM ubuntu:24.04 AS production

WORKDIR /app

COPY --from=build /app/.pixi/envs/default /app/.pixi/envs/default
COPY --from=build --chmod=0755 /app/entrypoint.sh /app/entrypoint.sh

COPY ./meme_games /app/meme_games
COPY ./run.py /app/run.py
COPY ./media /app/media
COPY ./static /app/static
COPY ./settings.ini /app/settings.ini

EXPOSE 8000

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "python", "run.py" ]