# meme-games
Random social games to have fun with friends

## How to run
1. Run locally
```sh
git clone https://github.com/ssslakter/meme-games
pixi run app
```
2. Run with docker compose
```sh
docker compose up -d
```

## Contributing

For more info on used stack read [fasthtml](https://fastht.ml/docs) docs.

Part of this project is developed using [nbdev](https://nbdev.fast.ai/).

Run the following commands to install and then enable pre-commit hooks
```sh
git clone https://github.com/ssslakter/meme-games
cd meme-games
pixi shell -e dev
pre-commit install
```