base:
	docker build -f base.dockerfile -t dsu:latest .
	docker image prune -f

build:
	rm -rf ./.build-context
	mkdir -p ./.build-context
	cp -r ../../../dx-streaming-upload/* ./.build-context/
	docker build --no-cache -f ${name}.dockerfile -t dsu-${name}:latest .
	docker image prune -f

run:
	docker run -it -d dsu-${name}:latest --extra-vars "dx_token=${dx_token}"
	echo "Docker container list"
	docker container ls -a

.NOTPARALLEL:
.SILENT: