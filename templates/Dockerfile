FROM node:latest
RUN echo deb http://dl.google.com/linux/chrome/deb/ stable main >> /etc/apt/sources.list
RUN wget https://dl-ssl.google.com/linux/linux_signing_key.pub
RUN apt-key add linux_signing_key.pub
RUN apt-get update && apt-get install python3 python3-pip google-chrome-stable -y
RUN yarn global add node-sass-chokidar
COPY requirements.txt /
RUN pip3 install -r /requirements.txt
RUN mkdir /templates
WORKDIR /templates
