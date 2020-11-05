# Install PsyNet/Dallinger on Ubuntu 20.04

## Optionally install Ubuntu 20.04.1 inside Virtual Machine Manager / QEMU/KVM

```bash
sudo apt install virt-manager
```
Get the Ubuntu iso image from here: 
https://releases.ubuntu.com/20.04/ubuntu-20.04.1-desktop-amd64.iso

Select 'Minimal installation' when asked otherwise choose default settings

## Prepare system and database

### Install system packages
```bash
sudo apt update
sudo apt upgrade
sudo apt install vim python3-dev python3-pip redis-server git libenchant1c2a postgresql postgresql-contrib libpq-dev
```

### Setup postgresql
```bash
sudo service postgresql start
sudo -u postgres -i
```
```bash
createuser -P dallinger --createdb 
```

Password: dallinger

```bash
createdb -O dallinger dallinger
createdb -O dallinger dallinger-import
exit
```

```bash
sudo service postgresql reload
```
### Install heroku client
```bash
sudo snap install heroku --classic
```

# Install Python virtualenv
```bash
sudo pip3 install virtualenv
sudo pip3 install virtualenvwrapper
```

### Setup system environment
```bash
export WORKON_HOME=$HOME/.virtualenvs
mkdir -p $WORKON_HOME
export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
source /usr/local/bin/virtualenvwrapper.sh
mkvirtualenv dlgr_env --python /usr/bin/python3
workon dlgr_env
echo "export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3" >> ~/.bashrc
echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
```

### Git clone Dallinger (in your home directory)
```bash
cd ~
git clone https://github.com/Dallinger/Dallinger
cd Dallinger
```

### IMPORTANT: Modify following files in Dallinger

#### In build-requirements.txt add
```bash
'cython' package
```

#### In constraints-deps.txt use
```bash
'numpy==1.17.4'
'packaging==20.4'
'psycopg2==2.8.6'
'pyyaml==5.3.1'
'virtualenv==20.1.0'
```

## Continue installation
```bash
pip install -r dev-requirements.txt
```
## IMPORTANT: Be sure numpy==1.17.4 is installed
```bash
pip3 install numpy==1.17.4
```
```bash
pip install --editable .[data]
```

## Verify successful installation
```bash
dallinger --version
```

# Install PsyNet (in your home directory) using your GitLab username and password
```bash
cd ~
git clone https://gitlab.com/computational-audition-lab/psynet
cd psynet
pip3 install -e .
```

## Verify successful installation
```bash
psynet --version
```

