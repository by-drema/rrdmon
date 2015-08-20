# rrdmon (Monitoring tool based on Round Robin Database)

rrdmon - это мониторинг количества сообщений в очередях брокера сообщений RabbitMQ (для работы необходимо активировать плагин rabbitmq_management), написанный на python3.

Информация по сообщениям каждой очереди хранится в отдельных .rrd файлах, рассчитанных на хранение данных за последние 28 дней.
Так же для определения отклонений в поведении очереди используется встроенная в возможности RRDTool [мультипликативная модель краткосрочного прогнозирования Хольта-Уинтерса](https://www.usenix.org/legacy/publications/library/proceedings/lisa2000/full_papers/brutlag/brutlag_html/index.html). Она характеризуется "сезонностью" (задается вручную) и "трендом" (высчитывается автоматически на основании данных временного ряда).

Определенные настройки модели задаются в конфигурационном файле, в отдельности для каждого монитора:

- шаг измерений "step" (задается в секундах);
- сезон "season_in_steps" (задается в шагах);

Наиболее подходящими являются значения шага в 1 минуту (step=60) и сезона в 24 часа (season_in_steps=1440). 
Параметры alpha и beta выбраны 0.1 и 0.0035 соответственно, как оптимальные для заданных шага и сезона (изменение этих параметров влияет на адаптивные свойства модели).

Отклонения в поведении наблюдаемых объектов (аберрации) определяются как допустимое кол-во выходов за рамки предсказаний в заданном плавающем окне, а именно: 5 из 7.
Это означает, что, если среди последних 7ми значений (плавающее окно) - 5 не попали в прогнозируемый коридор, то в соответствующий временной ряд будет занесено значение "1", являющееся индикатором аберрации на данном временном интервале. В соответствии с этим можно генерировать предупреждение.
> В настоящее время реализована возможность отправки уведомлений по почте (секция "Email" в конфигурационном файле).
> Для этого мониторинг должен быть запущен с ключами " --mon --chk".
> Однако, в настоящее время такой запуск нежелателен, т.к. радикально влияет на производительность мониторинга (улучшение в разработке).

Аберрация считается завершенной только в случае, когда в плавающем окне будет меньше 5 единичных значений.

За визуальное представление статистической информации, собранной в .rrd файлах, отвечает web-интерфейс, настройки которого находятся в секции "webserv" конфигурационного файла.
Информация может быть предоставлена в виде png-графиков, генерируемых средствами rrdtool (работает на любых заданных интервалах), и в виде интерактивных графиков, отрисованных средствами javascript (работает ограничение на интервал в 7 дней, в силу объемного количества данных, непригодных для отрисовки на стороне клиента).

### Install custom python (for the moment supporting python ver. 3.4+ ):

```sh
        $ wget https://www.python.org/ftp/python/3.4.0/Python-3.4.0.tgz -O /tmp/Python-3.4.0.tgz
        $ tar xzvf /tmp/Python-3.4.0.tgz -C /tmp/
        $ pushd /tmp/Python-3.4.0/
        $ mkdir /opt/python3
        $ ./configure --prefix=/opt/python3
        $ make && make install
        $ ln -s /opt/python3/bin/python3 /usr/bin/python3
        $ ln -s /opt/python3/bin/python3.4 /usr/bin/python3.4
```

[Installing python3.x without registering and SMS (RHEL/CentOS)](http://linuxsysconfig.com/2013/03/running-multiple-python-versions-on-centos6rhel6sl6/)


##  Setup working environment:

* Install rrdtool in system:
```sh
    $ sudo apt-get install rrdtool librrd-dev 
    $ sudo apt-get install python3-dev  ### may be no needed (because we've installed python3 "from scratch")
 ```
     
* Install pip & virtualenv:
```sh    
    $ wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
    $ sudo python3 /tmp/get-pip.py
    $ sudo pip install -U virtualenv
```

* Setup our virtual environment:
```sh
    $ virtualenv -p python3 --no-site-packages /opt/venv
    $ source /opt/venv/bin/activate
    $ pip install requests bottle lockfile
    $ mkdir /opt/venv/{installed-by-hands,proj}
    $ pushd /opt/venv/installed-by-hands
    $ git clone https://github.com/commx/python-rrdtool.git
    $ pushd python-rrdtool
    $ python setup.py install
```   

* Run (stop) application.
```sh
    $ git clone https://github.com/by-drema/rrdmon.git /opt/venv/proj
    $ pushd /opt/venv/proj
    $ python main.py start (stop) --mon [--chk] && tail -f var/log/daemon.log    # запуск мониторинга [с проверкой]
    $ python main.py start (stop) --web && tail -f var/log/webserv.log           # запуск web-интерфейса
```


=== TODO

* aliases
* autodeploy
* re-write ui
* queues filtering
* webui demonization
* processing .rrd files in separate thread/process
* extended and formatted logging (via logging module)
* replace self-written daemon with standart modules
* split solid application into separate independent tools
