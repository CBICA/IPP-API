FROM python:3.9
WORKDIR /opt
COPY requirements.txt .
RUN pip install -r requirements.txt
# install ssh server for backend
RUN apt-get update && apt-get install -y openssh-server && \
    printf "\nPermitRootLogin yes\nPasswordAuthentication yes\n" >> /etc/ssh/sshd_config && \
    echo "root:root" | chpasswd && \
    service ssh start
# some of the wrappers use jq
RUN apt-get update && apt-get install -y jq
COPY . .
EXPOSE 5000 22
CMD /opt/init.sh
