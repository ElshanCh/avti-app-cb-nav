ARG PY_V
FROM python:${PY_V} as base
WORKDIR /lunalabs/src
RUN apt update \
    && apt install -y \
	tzdata \
	&& ln -fs /usr/share/zoneinfo/Europe/Rome /etc/localtime \
	&& apt clean \
	&& rm -rf /var/lib/apt/lists \
	&& python3 -m venv /lunalabs/src \
	&& chmod +x /lunalabs/src/bin/* 



FROM base as deps
COPY requirements.txt ./
RUN ./bin/activate \
    && ./bin/python3 -m pip install -r requirements.txt



ARG PY_V
FROM python:${PY_V} as deploy
ARG _USER
ARG _GROUP
ARG UID
ARG GID
ARG WORKDIR
ENV WORKDIR=${WORKDIR}
ENV VENV_BIN=${WORKDIR}/bin
RUN apt update \
    && apt install -y \
	tzdata \
	&& ln -fs /usr/share/zoneinfo/Europe/Rome /etc/localtime \
	&& apt clean \
	&& rm -rf /var/lib/apt/lists \
	&& groupadd -g ${GID} ${_GROUP} \
	&& useradd -u ${UID} -g ${GID} -s /bin/bash -m -b ${WORKDIR} ${_USER} 
WORKDIR ${WORKDIR}
COPY container/entrypoint /entrypoint
COPY --chown=${_USER}:${_GROUP} . ./
COPY --from=deps --chown=${_USER}:${_GROUP} /lunalabs/src ./
# SYSTEMWIDE ENVS
RUN printenv > /etc/environment \
	&& chown ${_USER}.${_GROUP} ${WORKDIR} \
	&& chmod +x /entrypoint \
	&& rm -rf container requirements.txt \
	&& sed -i s./lunalabs/src.${WORKDIR}.g $(grep -rnw "/lunalabs/src" 2> /dev/null | tr -s ":" | cut -d":" -f 1)
USER ${_USER}
ENTRYPOINT [ "/entrypoint" ]
CMD [ "--debug" ]

