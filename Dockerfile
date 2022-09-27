# base image
FROM --platform=linux/amd64 python:3.8.3-slim-buster
WORKDIR /intunecd
COPY requirements.txt .

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
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# CONFIGURE ENV FOR /bin/bash TO USE MSODBCSQL17
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile 
RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc 

RUN pip3 install pyodbc

# copy all files
ADD . /intunecd