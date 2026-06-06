import time
import math
import asyncio
from sdk.commands.move_coordinates_command import MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation, PlannerType
from sdk.manipulators.m13 import M13

host = "192.168.123.21" # IP манипулятора
client_id = "client_id" # ID клиента
login = "login" # Логин
password = "password" # Пароль
manipulator = M13(host, client_id, login, password)

orientation = MoveCoordinatesParamsOrientation(0, 0, 0, 1)
orientation2 = MoveCoordinatesParamsOrientation(0, 0, 0.5, 0.5)

h = 0.153
# h = 0.175
x = 0.08
y = 0.64
x2 = -0.3
y2 = 0.3
h2 = 0.6
vMove = 0.1
vWrite = 0.4
af = 0.1

dx, dy = 0.004, 0.004

poseses = []
poseses.append([[dx, 0], 
                [4*dx, 0],
                [3*dx, dy],
                [dx, dy]])
poseses.append([[3*dx, dy],
                [4*dx, dy]])
#И
poseses.append([[2*dx, 2*dy],
                [4*dx, 2*dy]])
poseses.append([[2*dx, 3*dy],
                [4*dx, 3*dy]])
poseses.append([[3*dx, 2*dy],
                [3*dx, 3*dy]])
#Н
poseses.append([[2*dx, 4*dy],
                [4*dx, 4*dy]])
poseses.append([[2*dx, 5*dy],
                [4*dx, 5*dy]])
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

async def make_manipulator_connection():
    try:
        manipulator.connect()
        manipulator.get_control()
        manipulator.enable_servo_streaming()
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x2, y, h2), orientation2, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x, y, h2), orientation2, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x, y, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        for poss in poseses:
            poses = []
            for i in range(len(poss)):
                poses.append([poss[i][0] + x, poss[i][1] + y, h])
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0][:2], h+0.007), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
            manipulator.set_servo_pose_mode()
            for pos in poses:
                manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*pos), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[-1][:2], h+0.007), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x, y, h2), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x, y, h2), orientation2, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x2, y, h2), orientation2, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(x2, y2, h2), orientation2, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
        manipulator.stop_movement()
    except Exception as e:
        print("Error: ", e)

        
time.sleep(3)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncio.get_event_loop().run_until_complete(make_manipulator_connection())