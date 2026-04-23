import os
import Configuracores
import DataBase.DB_PostGres
from datetime import datetime

class Controller_Master():

    def __init__(self):
        super().__init__()
        if not os.path.exists(Configuracores.caminhologs):
            os.makedirs(Configuracores.caminhologs, exist_ok = True) 
        self.logFileName = self.returnNameFileLog()
        self.makePath(self.logFileName)
        self.objDB = DataBase.DB_PostGres.PostgresPool()
        print('Log iniciado com sucesso.')

    def makePath(self, path):
        blocos = str(path).split('/')
        parcial = ''
        for part in blocos:
            if('.' not in part):
                parcial += part + '/'
                if not os.path.isdir(parcial):
                    os.makedirs(parcial)

    def logText(self, msg):
        f1 = open(self.logFileName, 'a')
        f1.write(datetime.now().strftime('%m-%d-%Y') + ' ==> ' + msg + "\n")
        f1.close()
            
    def returnNameFileLog(self):
        nome = datetime.now().strftime('%m-%d-%Y') + '.log'
        nome = Configuracores.caminhologs + Configuracores.barraDirSO + nome
        return(nome)

    def log(self, msg):
        print('msg = ', msg)
        self.logText(msg)
        sql = "INSERT INTO logGeral (mensagem, dataHora) VALUES (%s, %s)"
        #self.objDB.insert(sql, (msg, datetime.now()))
