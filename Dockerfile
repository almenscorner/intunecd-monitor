# base image
FROM --platform=linux/amd64 python:3.11-slim-buster
WORKDIR /intunecd
COPY requirements.txt .
COPY server-entrypoint.sh .
COPY worker-entrypoint.sh .
RUN chmod u+x ./server-entrypoint.sh
RUN chmod u+x ./worker-entrypoint.sh

RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

# adding custom MS repository
RUN apt-get update \
    && apt-get install -y --reinstall build-essential \
    && apt-get install -y gnupg \
    && apt-get install -y curl apt-transport-https \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev \
    && apt-get install -y git \
    && apt-get install -y sqlite3

# CONFIGURE ENV FOR /bin/bash TO USE MSODBCSQL17
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile 
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc 

# CONFIGURE GIT
RUN git config --global user.email "inteuncdmonitor@intunecd.local"
RUN git config --global user.name "IntuneCD Monitor"

RUN pip3 install pyodbc

# copy all files
ADD . /intunecd

# create db folder
RUN mkdir /intunecd/db

ENTRYPOINT ["/bin/bash", "-c", "./server-entrypoint.sh"]