import time
import math
import asyncio
from sdk.commands.move_coordinates_command import MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation, PlannerType
from sdk.manipulators.m13 import M13
import threading
import serial
from voice_active.voice_activation import VoiceActivator

dx, dy = 0.004, 0.005

poseses = []
poseses.append([[dx, 0], 
                [4*dx, 0],
                [3*dx, dy]])
poseses.append([[dx, dy],
                [4*dx, dy]])
#И
poseses.append([[2*dx, 2*dy],
                [4*dx, 2*dy]])
poseses.append([[4*dx, 3*dy],
                [2*dx, 3*dy]])
poseses.append([[3*dx, 2*dy],
                [3*dx, 3*dy]])
#Н
poseses.append([[2*dx, 4*dy],
                [4*dx, 4*dy]])
poseses.append([[4*dx, 5*dy],
                [2*dx, 5*dy]])
poseses.append([[3*dx, 4*dy],
                [3*dx, 5*dy]])
# #Н
poseses.append([[2*dx, 6*dy],
                [4*dx, 6*dy],
                [4*dx, 7*dy],
                [2*dx, 7*dy],
                [2*dx, 6*dy]])

poseses.append([[2*dx, 8*dy],
                [3*dx, 8*dy]])
#'
poseses.append([[2*dx, 9*dy],
                [2*dx, 10*dy],
                [3*dx, 10*dy],
                [3*dx, 9*dy],
                [4*dx, 9*dy],
                [4*dx, 10*dy]])
#2
poseses.append([[2*dx, 12*dy],
                [2*dx, 11*dy],
                [4*dx, 11*dy],
                [4*dx, 12*dy],
                [3*dx, 12*dy],
                [3*dx, 11*dy]])
#6

def setup_robot():
    global manipulator
    host = "192.168.123.21" # IP манипулятора
    client_id = "client_id" # ID клиента
    login = "login" # Логин
    password = "password" # Пароль
    manipulator = M13(host, client_id, login, password)
    manipulator.connect()
    manipulator.get_control()

orientation = MoveCoordinatesParamsOrientation(0, 0, 0, 1)

h = 0.144
# h = 0.175
x = 0.05
y = 0.76
x2 = -0.2
y2 = 0.3
h2 = 0.6
vMove = 0.1
vWrite = 0.4
af = 0.1

def move_robot():
    manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x2, y, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
    manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x, y, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
    for poss in poseses:
        poses = []
        for i in range(len(poss)):
            poses.append([-poss[i][1] + x, poss[i][0] + y, h])
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0][:2], h+0.007), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        for pos in poses:
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*pos), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[-1][:2], h+0.007), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
    manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x, y, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
    manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x2, y, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
    manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x2, y2, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)

path = "/dev/ttyACM0"
baud = 115200

if __name__ == "__main__":
    try:
        setup_robot()
        ser = serial.Serial(path, baud)
        activator = VoiceActivator()
        activation_event = threading.Event()
    except Exception as e:
        print("Error: ", e)

    def terminal_trigger():
        while True:
            input()
            activation_event.set()

    def serial_trigger():
        while True:
            ser.readline()
            activation_event.set()

    def voice_trigger():
        while True:
            ok, transcript = activator.listen()
            activation_event.set()

    try:
        threading.Thread(target=terminal_trigger, daemon=True).start()
        threading.Thread(target=serial_trigger, daemon=True).start()
        threading.Thread(target=voice_trigger, daemon=True).start()
        while True:    
            activation_event.clear()
            print("Ready")
            activation_event.wait()
            print("Activated")
            move_robot()

    except KeyboardInterrupt:
        ser.close()
        exit(0)    