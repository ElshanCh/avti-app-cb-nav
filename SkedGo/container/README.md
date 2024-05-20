# LunaLabs backend 

## Development server
To run the server, make sure to install deno first, then 
```
$ deno run --allow-net --allow-env server.ts
```
# DOCKER

## info

richiede:
| sw | ver | scope
| :--- | :--- | :---
| docker | 20.10.21 | container runtime
| docker-compose | 2.11.0+ | docker cli wrapper && conf provider (yml standard)
| buildx | 0.9+ | docker plugin for deployment

si può effettuare l'override dei .env ridefinendo le var nella shell locale:
<br><br>
esempio:
<br>
```bash
cat .env
> DEPLOY_VERSION=latest
> DEPLOY_ENV=dev
```

```bash
cat docker-compose.yml
...
> image: ${BE_IMAGE}-${DEPLOY_VERSION}-${DEPLOY_ENV}
```

in shell:
```bash
export DEPLOY_VERSION=1.0
export DEPLOY_ENV=test
```

il risultato:
```bash
docker-compose config
...
> image: ...-1.0-test
```

invece di:
```bash
docker-compose config
...
> image: ...-latest-dev
```

## build

```bash
docker buildx create --use
docker buildx bake -f docker-compose.build.yml 
docker buildx rm
```

## rebuild

```bash
docker-compose -p easycode-${DEPLOY_ENV} down
docker rmi $(docker images | grep "sitolunalabs.*backend" | tr -s " " | cut -d" " -f 3)
docker buildx create --use
docker buildx bake -f docker-compose.build.yml
docker buildx rm
```

## up

```bash
docker-compose -p easycode-${DEPLOY_ENV} up
```

## down 

> <span style="color:yellow">WARNING</span>: CAREFUL! destroys all managed resources!

```bash
docker-compose -p easycode-${DEPLOY_ENV} down
```