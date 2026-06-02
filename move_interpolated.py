import time
import math
import asyncio
from sdk.commands.move_coordinates_command import MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation, PlannerType
from sdk.manipulators.m13 import M13

host = "10.100.21.86" # IP манипулятора
client_id = "client_id" # ID клиента
login = "login" # Логин
password = "password" # Пароль
manipulator = M13(host, client_id, login, password)

orientation = MoveCoordinatesParamsOrientation(0, 0, 0, 1.0)


h = 0.15
x = 0.75
y = 0.0
vMove = 0.1
vWrite = 0.4
af = 0.1
p = [MoveCoordinatesParamsPosition(x, y, h), 
     MoveCoordinatesParamsPosition(x + 0.01, y, h), 
     MoveCoordinatesParamsPosition(x + 0.01, y - 0.01, h), 
     MoveCoordinatesParamsPosition(x, y - 0.01, h)]

pf = MoveCoordinatesParamsPosition(x, y, h+0.1)

def interpolate_circle(R: float, xc: float, yc: float, z: float, delta: float):
    pos = []
    for i in range(int(360/delta)):
        pos.append((round(xc + R*math.cos(math.radians(delta*i)), 4), round(yc + R*math.sin(math.radians(delta*i)), 4), z))
    return pos

def interpolate_spiral(alpha: float, Rmax: float, xc: float, yc: float, z: float, delta: float):
    pos = []
    for i in range(2*int(360/delta)):
        angle = delta*i
        R = alpha * angle/360
        pos.append((round(xc + R*math.cos(math.radians(angle)), 4), round(yc + R*math.sin(math.radians(angle)), 4), z))
    return pos

async def make_manipulator_connection():
    try:
        manipulator.connect()
        manipulator.get_control()
        # poses = interpolate_spiral(0.025, 0.1, x, y, h, 1)
        poses = interpolate_circle(0.05, x, y, h, 1)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0][:2], h+0.1), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
        manipulator.set_servo_pose_mode()
        for pos in poses[1:]:
            manipulator.stream_coordinates(MoveCoordinatesParamsPosition(*pos), orientation)
            time.sleep(0.04)
        manipulator.move_to_coordinates(pf, orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
    except Exception as e:
        print("Error: ", e)

        
time.sleep(3)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncio.get_event_loop().run_until_complete(make_manipulator_connection())