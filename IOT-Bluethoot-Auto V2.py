import os 
import json
import time
import random
import httplib2
import bluetooth
import threading
from sense_hat import SenseHat

'''
RaspberryJ - B8:27:EB:14:B2:5F

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

idAuto = 789456123
servidor = "be415def.ngrok.io"

http = httplib2.Http()
httplib2.debuglevel = 0
url1 = "http://" + servidor + "/myApp/rest/estacion/"
url0 = "http://" + servidor + "/myApp/rest/vehiculo/enviarDeposito/"
headers = {'Content-Type': "application/json"}

sense = SenseHat()
lock = threading.Lock()
sem = threading.Semaphore()

nivelCombustible = 26


def consultar_estacion(idEstacion):
    url2 = url1 + str(idEstacion)
    resp_headers, datos = http.request(url2, 'GET')
    datos = json.loads(datos.decode('utf-8'))
    return datos
        
        
def realizar_deposito(idEstacion, idAuto, fuel, cantidad, valor):
    info = {
    "idEstacion": idEstacion,
    "idCarro": idAuto,
    "fuel": fuel,
    "cantidad": cantidad,
    "valor": valor
    }
    http.request(url0, 'POST', json.dumps(info), headers=headers)
    
    
def configurar_conexion():
    os.system("sudo hciconfig 0 up")
    os.system("sudo hciconfig 0 reset")
    os.system("sudo hciconfig 0 piscan")
    os.system("sudo hciconfig 0 sspmode 0")


configurar_conexion()
datosRecividos = ""


def recivir_datos_bluetooth_de_estacion():
    while True:
        global datosRecividos
        try:
            server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            server_sock.bind(("", 2))
            while True:
                server_sock.listen(2)
                client_sock, address = server_sock.accept()
                data = client_sock.recv(1024)
                datos = json.loads(data.decode('utf8'))
                lock.acquire()
                datosRecividos = datos
                lock.release()
        except:
            configurar_conexion()


hilo_servidor_bluetooth = threading.Thread(target = recivir_datos_bluetooth_de_estacion)
hilo_servidor_bluetooth.start()


def establecer_conexion_con_estacion():
    while True:
        try:
            bd_addr = str("B8:27:EB:14:B2:5F")
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((bd_addr, 1))
            return sock
            break
        except:
            configurar_conexion()


sock = ""


def enviar_datos_bluetooth_hacia_estacion(info):
    global sock
    while True:
        try:
            sock.send(json.dumps(info))
            break
        except:
            sock = establecer_conexion_con_estacion()
    
    
def animacion_llenar_tanque(nivelCombustible, nivelCombustiblei):
    tupla = [(0, 0, 0) for i in range(64)]
    for nivel in range(nivelCombustiblei, nivelCombustible + 1):
        if nivel <= 14:
            for i in range (nivel):
                tupla[i] = (204, 0, 0)
        elif nivel > 14:
            for i in range (nivel):
                tupla[i] = (0, 128, 0)
        sense.set_pixels(tuple(tupla))
        time.sleep(0.8)

    
def animacion_vaciar_tanque(nivelCombustible):
    tupla = [(0, 0, 0) for i in range(64)]
    if nivelCombustible <= 14:
        for i in range (nivelCombustible):
            tupla[i] = (204, 0, 0)
    elif nivelCombustible > 14:
        for i in range (nivelCombustible):
            tupla[i] = (0, 128, 0)
    sense.set_pixels(tuple(tupla))


idEstacion = ""


def llenar_tanque():
    global saldo
    enviar_datos_bluetooth_hacia_estacion({'Codigo': "DgnV", 'ID': idAuto})
    time.sleep(2)
    while True:
        try:
            if datosRecividos['Codigo'] == "sjC1":
                global idEstacion
                idEstacion = datosRecividos['ID']
                break
        except: pass
    time.sleep(2)
    datosEstacion = consultar_estacion(idEstacion)
    valor = datosEstacion['Deposit']
    seleccionCombustible = random.choice(datosEstacion['fuels'])
    tipoCombustible = seleccionCombustible["TipoGas"]
    cantidad = 7
    time.sleep(2)
    realizar_deposito(idEstacion, idAuto, tipoCombustible, cantidad, valor)
    time.sleep(2)
    enviar_datos_bluetooth_hacia_estacion({'Codigo': "8ESt", 'Tipo': tipoCombustible, 'Cantidad': cantidad})
    time.sleep(2)
    while True:
        try:
            if datosRecividos['Codigo'] == "R7d0":
                sem.acquire()
                global nivelCombustible
                nivelCombustiblei = nivelCombustible
                nivelCombustible = int(datosRecividos['Cantidad']) + 30
                animacion_llenar_tanque(nivelCombustible, nivelCombustiblei)
                time.sleep(4)
                sem.release()
                break
        except: pass
    enviar_datos_bluetooth_hacia_estacion({'Codigo': "QD1F"})


def vaciar_tanque():
    while True:
        global nivelCombustible
        if nivelCombustible > 0:
            sem.acquire()
            nivelCombustible -= 1
            animacion_vaciar_tanque(nivelCombustible)
            sem.release()
            if nivelCombustible == 14:
                hilo_llenar_tanque = threading.Thread(target = llenar_tanque)
                hilo_llenar_tanque.start()
            time.sleep(4)
        
        
hilo_vaciar_tanque = threading.Thread(target = vaciar_tanque)
hilo_vaciar_tanque.start()
    