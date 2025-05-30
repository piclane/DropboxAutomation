#!/bin/sh -ex

export AWS_PROFILE=piclane_ecr

aws ecr-public get-login-password --region us-east-1 \
| docker login --username AWS --password-stdin public.ecr.aws/x9j4t0a2

TAG='public.ecr.aws/x9j4t0a2/dropbox-automation:1.0.1'

docker buildx rm amd-arm || true
docker buildx create --name amd-arm --driver docker-container --platform linux/arm64,linux/amd64

docker manifest rm "${TAG}" || true
docker rmi "${TAG}-amd64" || true
docker rmi "${TAG}-arm64" || true
docker rmi "${TAG}" || true

docker buildx build \
  --load \
  --builder amd-arm \
  --target app \
  --platform linux/amd64 \
  -t "${TAG}-amd64" \
  -f Dockerfile \
  .

docker buildx build \
  --load \
  --builder amd-arm \
  --target app \
  --platform linux/arm64 \
  -t "${TAG}-arm64" \
  -f Dockerfile \
  .

docker push "${TAG}-amd64"
docker push "${TAG}-arm64"

docker manifest create "${TAG}" "${TAG}-amd64" "${TAG}-arm64"
docker manifest push "${TAG}"

docker buildx rm amd-arm || true
