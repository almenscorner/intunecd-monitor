#Use the nginx Image and create the container from the Image
FROM --platform=linux/amd64 nginx

RUN rm /etc/nginx/conf.d/default.conf
COPY ./nginx/nginx.conf.template /etc/nginx/conf.d
RUN mkdir /var/html
COPY ./nginx/error502.html /var/html
ENV ESC='$'
