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


h = 0.1585
# h = 0.175
x = 0.65
y = 0.00
vMove = 0.1
vWrite = 0.4
af = 0.1

import csv
import glob
import os
import re

def load_trajectories(folder="trajectory"):
    trajectories = []
    base = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(base, folder, "*.csv")),
               key=lambda f: int(re.search(r'\d+', os.path.basename(f)).group()))
    print(files)
    for filename in files:
        trajectory = []
        with open(filename, "r") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                trajectory.append([
                    float(row[0]),
                    float(row[1])
                ])
        trajectories.append(trajectory)
    return trajectories

def interpolate_circle(R: float, xc: float, yc: float, z: float, delta: float):
    pos = []
    for i in range(int(360/delta)):
        pos.append((xc + R*math.cos(math.radians(delta*i)), yc + R*math.sin(math.radians(delta*i)), z))
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
        poseses = load_trajectories()
        for poss in poseses:
            poses = []
            for i in range(len(poss)):
                poses.append([poss[i][0] + x, -poss[i][1] + y, h])
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0][:2], h+0.015), orientation, velocity_scaling_factor=vWrite, acceleration_scaling_factor=af)
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[0]), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
            manipulator.set_servo_pose_mode()
            for pos in poses[1:]:
                await manipulator.stream_coordinates_async(MoveCoordinatesParamsPosition(*pos), orientation)
                time.sleep(0.02)
            manipulator.move_to_coordinates(MoveCoordinatesParamsPosition(*poses[-1][:2], h+0.015), orientation, velocity_scaling_factor=vMove, acceleration_scaling_factor=af)
    except Exception as e:
        print("Error: ", e)

        
time.sleep(3)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncio.get_event_loop().run_until_complete(make_manipulator_connection())