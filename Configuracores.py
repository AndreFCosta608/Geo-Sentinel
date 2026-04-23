import os
import socket
from os import environ
from dotenv import find_dotenv
from dotenv import load_dotenv

load_dotenv(find_dotenv())

print(type(os.environ))

barraDirSO = '/'

enderecoSistema = 'http://127.0.0.1:8001/'

maximoTentativasLogin = 3
horasBloqueio = 2

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM")

INPE_Access_Token = os.environ.get("INPE_Access_Token")

maxPoolSize = 32
MariaDB_Host = os.environ.get("MariaDB_Host")
MariaDB_Database = os.environ.get("MariaDB_Database")
MariaDB_User = os.environ.get("MariaDB_User")
MariaDB_Password = os.environ.get("MariaDB_Password")

caminhoRaiz = str(os.path.dirname(os.path.realpath(__file__))) #.replace('fontes', '')
caminhologs = caminhoRaiz + 'logs'


caminhoArquivosTemporarios = caminhoRaiz + '/Public_Files/Interno/temporarios/'

caminhoImagens = caminhoRaiz + '/static/imagens/'
