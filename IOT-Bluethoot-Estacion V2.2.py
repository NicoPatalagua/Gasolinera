import os 
import json
import time
import httplib2
import bluetooth
import threading
from sense_hat import SenseHat

'''
RaspberryA - B8:27:EB:61:92:70

Codigos usados para la comunicacion bluetooth:
    
- DgnV: Codigo usado para iniciar la comunicacion, es usado por el auto para 
        solicitar el id de la estacion, junto a este mensaje se envia el id del auto.
        
- sjC1: Codigo usado para responder a la solicitud de inicio de una comunicacion,
        es usado por la estacion para responder al codigo DgnV enviado por al auto,
        junto a este mensaje se envia el id de la estacion.
        
- 8ESt: Codigo usado por el auto para solicitar combustible, es acompañado de la
        cantidad y el tipo de combustible solicitado.
        
- R7d0: Codigo usado por la estacion para enviar combustible al auto, es acompañado
        de la cantidad solicitada.
        
- Ca5n: Codigo usado por la estacion para denegar la solicitud del auto por fondos
        insuficientes.   
        
- QD1F: Codigo usado por el auto para finalizar la comunicacion.
        
'''

idEstacion = 123456789
servidor = "be415def.ngrok.io"

http = httplib2.Http()
httplib2.debuglevel = 0
url1 = "http://" + servidor + "/myApp/rest/estacion/"
url0 = "http://" + servidor + "/myApp/rest/estacion/deposito/"
headers = {'Content-Type': "application/json"}

sense = SenseHat()
lock = threading.Lock()

nivelcombustible = 192


def comprobar_deposito(idEstacion, idAuto):
    url2 = url0 + str(idEstacion) + "/" + str(idAuto)
    resp_headers, datos = http.request(url2, 'GET')
    datos = json.loads(datos.decode('utf-8'))['value']
    return datos


def finalizar_transaccion(idEstacion, idAuto, tipoCombustible, cantidadConsumida):
    url3 = "http://"+ servidor +"/myApp/rest/estacion/terminarTransaccion"
    info = {
    "idEstacion": idEstacion,
    "idCarro": idAuto,
    "fuel": tipoCombustible,
    "cantidad": cantidadConsumida,
    "valor": "0"
    }
    http.request(url3, 'POST', json.dumps(info), headers=headers)


def registrar_estacion():
    global idEstacion
    info = {
    "direccion": "",
    "id": idEstacion,
    "Deposit": "30",
    "fuels": [
        {
            "TipoGas": "0",
            "price": "4",
            "cantidadDisponible": "400"
        },
        {
            "TipoGas": "1",
            "price": "2",
            "cantidadDisponible": "600"
        }
    ]
    }
    http.request(url1, 'POST', json.dumps(info), headers=headers)


registrar_estacion()


def configurar_conexion():
    os.system("sudo hciconfig 0 up")
    os.system("sudo hciconfig 0 reset")
    os.system("sudo hciconfig 0 piscan")
    os.system("sudo hciconfig 0 sspmode 0")


configurar_conexion()
datosRecividos = ""


def recivir_datos_bluetooth_de_auto():
    while True:
        global datosRecividos
        try:
            server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            server_sock.bind(("", 1))
            while True:
                server_sock.listen(1)
                client_sock, address = server_sock.accept()
                data = client_sock.recv(1024)
                datos = json.loads(data.decode('utf8'))
                lock.acquire()
                datosRecividos = datos
                lock.release()
        except:
            configurar_conexion()


hilo_servidor_bluetooth = threading.Thread(target = recivir_datos_bluetooth_de_auto)
hilo_servidor_bluetooth.start()


def establecer_conexion_con_auto():
    while True:
        try:
            bd_addr = str("B8:27:EB:61:92:70")
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((bd_addr, 2))
            return sock
            break
        except:
            configurar_conexion()


sock = ""


def enviar_datos_bluetooth_hacia_auto(info):
    global sock
    while True:
        try:
            sock.send(json.dumps(info))
            break
        except:
            sock = establecer_conexion_con_auto()


idAuto = ""


def animacion_vaciar_tanque(nivelCombustible):
    nivelCombustible = int(nivelCombustible/3)
    tupla = [(0, 0, 0) for i in range(64)]
    if nivelCombustible <= 14:
        for i in range (nivelCombustible):
            tupla[i] = (204, 0, 0)
    elif nivelCombustible > 14:
        for i in range (nivelCombustible):
            tupla[i] = (0, 128, 0)
    sense.set_pixels(tuple(tupla))
    

def vaciar_tanque(menos):
    global nivelcombustible
    for i in range(0,menos):
        nivelcombustible -= 1
        animacion_vaciar_tanque(nivelcombustible)
        time.sleep(2)


def recivir_solicitudes():
    while True:
        try:
            global idAuto
            global datosRecividos
            global nivelcombustible
            if datosRecividos['Codigo'] == "DgnV":
                idAuto = datosRecividos['ID']
                time.sleep(2)
                enviar_datos_bluetooth_hacia_auto({'Codigo': "sjC1", 'ID': idEstacion})
                datosRecividos = ""
            if datosRecividos['Codigo'] == "8ESt":
                deposito = comprobar_deposito(idEstacion, idAuto)
                if deposito == "true":
                    tipoSolicitado = int(datosRecividos['Tipo'])
                    cantidadSolicitada = int(datosRecividos['Cantidad'])
                    time.sleep(2)
                    enviar_datos_bluetooth_hacia_auto({'Codigo': "R7d0", 'Cantidad': cantidadSolicitada})
                    vaciar_tanque(30)
                    datosRecividos = ""
            if datosRecividos['Codigo'] == "QD1F":
                finalizar_transaccion(idEstacion, idAuto, tipoSolicitado, cantidadSolicitada)
                idAuto = ""
                tipoSolicitado = ""
                datosRecividos = ""
                cantidadSolicitada = ""
        except: pass


tupla = [(0, 128, 0) for i in range(64)]    
sense.set_pixels(tuple(tupla))
    
hilo_recivir_solicitudes = threading.Thread(target = recivir_solicitudes)
hilo_recivir_solicitudes.start()
    