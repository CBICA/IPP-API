# FROM rockie/centos6-pyinstaller
FROM centos:6.8
# install python3
USER root
COPY CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo
RUN yum -y install gcc openssl-devel bzip2-devel git sqlite-devel
RUN curl -LO https://ftp.gnu.org/gnu/libc/glibc-2.14.tar.gz && tar -xzf glibc-2.14.tar.gz && cd glibc-2.14 && mkdir build && cd build && ../configure --prefix=/opt/glibc-2.14 && make && make install && cd .. && rm -rf glibc-2.14.tar.gz
ENV LD_LIBRARY_PATH=/opt/glibc-2.14/lib:/usr/local/lib:$LD_LIBRARY_PATH
RUN cd /tmp && \
    curl -LO https://www.python.org/ftp/python/3.6.6/Python-3.6.6.tgz && \
    tar xzf Python-3.6.6.tgz && cd Python-3.6.6 && \
    ./configure --enable-loadable-sqlite-extensions --prefix=/usr/local --enable-shared LDFLAGS="-Wl,-rpath /usr/local/lib" && \
    make altinstall && \
    ln -sfn /usr/local/bin/python3.6 /usr/bin/python3.6
ARG requirements=""
RUN python3.6 -m pip install ${requirements}
RUN python3.6 -m pip install wheel
RUN git clone https://github.com/pyinstaller/pyinstaller.git && \
    cd pyinstaller && \
    git checkout v4.5.1 && \
    python3.6 setup.py install
ENTRYPOINT [ "/usr/local/bin/pyinstaller" ]

